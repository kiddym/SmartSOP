# Phase 5A 站内通知（In-app Notifications）设计

> **状态**：已与用户头脑风暴定稿，待写实现计划（writing-plans）。
> **路线图归属**：Master Roadmap 的 Phase 5「通知与文件」拆分后的第一个子阶段。Phase 5B（邮件投递）、5C（文件存储）为后续独立子阶段。

## 1. 目标与范围

在已完成的 Phase 0–4 之上提供**后端站内通知**：领域事件（工单指派/状态变更、自动建单、审批待办）与调度轮询（到期提醒、低库存）生成 per-user 通知，提供 feed / 未读计数 / 标记已读 API。

**本期交付**：通知数据模型（2 张新表 + 1 迁移）、通知生成服务 + 接收人解析、在既有事件点附加的内联生成、到期提醒/低库存调度 tick（边沿触发去重）、`/api/v1/notifications` API。

**关键原则**：
- **附加式观察者**：在既有事件点插入 `notify(...)`，**不修改任何既有领域模型字段**（不给 Request 加 `created_by`、不给 Part/WorkOrder 加 arm 标志）。
- 通知为持久化数据，**本期新增 2 表 + 1 迁移**（与 Phase 4 零新表不同）。
- 多租户 SaaS：通知 `company_id` NOT NULL，feed 读取靠既有 `with_loader_criteria` ORM 事件自动作用域；调度 tick 无请求上下文，按源实体 `company_id` 显式落行（仿 PM/meter 任务）。
- clean-room：不出现 "Atlas" 字样、不抄第三方源码/DDL/文案。

## 2. 明确不在 5A 内（YAGNI）

- 邮件投递（Phase 5B）
- 文件/附件存储（Phase 5C）
- 通知偏好设置 / 按类型订阅退订
- 实时推送（WebSocket/SSE）——本期纯轮询拉取
- 前端渲染（本期纯后端，返回结构化负载供前端按 locale 渲染）
- 修改 Request 模型加提交人字段——故「审批后通知提交人」本期**不做**

## 3. 数据模型（2 张新表）

### 3.1 `tb_notification`
基类 `UUIDMixin + TimestampMixin + TenantMixin`（`company_id` NOT NULL）。append-only，无软删（同活动日志表）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | CHAR(36) PK | UUIDMixin |
| `company_id` | String(36) NOT NULL index | TenantMixin |
| `created_at` / `updated_at` | DATETIME6 | TimestampMixin |
| `recipient_user_id` | String(36) index | 收件人；广播事件=每收件人一行 |
| `type` | String(40) | 事件类型码（见 §4） |
| `entity_type` | String(40) nullable | 多态弱引用类型（如 `work_order`/`request`/`purchase_order`/`part`） |
| `entity_id` | String(36) nullable | 多态弱引用 id（**无 FK**，零侵入） |
| `params` | Text（存 `json.dumps` 字符串，读时 `json.loads`） | 结构化负载（custom_id/from_status/to_status 等）；用 Text 而非方言 JSON 类型以跨 SQLite/MySQL 确定 |
| `actor_user_id` | String(36) nullable | 触发者；调度产生时 null |
| `is_read` | Boolean default False index | 读状态 |
| `read_at` | DATETIME6 nullable | 标记已读时间 |
| `dedup_key` | String(120) nullable | 轮询类边沿去重键（内联事件留空） |

索引：`(company_id, recipient_user_id, is_read)`、`(company_id, dedup_key)`。

### 3.2 `tb_notification_arm`
基类 `UUIDMixin + TimestampMixin + TenantMixin`。边沿状态表，记录当前"已武装"的轮询条件，仿 meter `is_armed` 边沿模式，避免修改 Part/WorkOrder。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `company_id` / `created_at` / `updated_at` | | 同 mixin |
| `key` | String(120) | 武装条件键 |

约束：UNIQUE `(company_id, key)`。

**边沿语义**：调度 tick 中，对每个满足条件的实体，若无对应 arm 行 → 发通知 + 插 arm 行；对条件已消失的实体（WO 改期/进入终态、库存回升 ≥ min）→ 删对应 arm 行（re-arm，下次再触发可再发）。

## 4. 事件目录与接收人解析

| type | 触发点 | 接收人 | 机制 |
|---|---|---|---|
| `WO_ASSIGNED` | `work_order_service.set_assignees` / `set_teams` / primary_user_id 变更 | **新增**的被指派人（含团队成员展开） | 内联 |
| `WO_STATUS_CHANGED` | `work_order_service.transition()` | 该 WO 指派人 + primary_user_id | 内联 |
| `WO_DUE_SOON` | 调度 tick | WO 指派人 + primary_user_id | 轮询·边沿 |
| `WO_OVERDUE` | 调度 tick | 同上 | 轮询·边沿 |
| `WO_AUTO_GENERATED` | `pm_service.generate_once` / `meter_trigger_service.generate_from_trigger` | 新单指派人；若无→公司 admin（角色兜底，见 §4.2） | 内联 |
| `REQUEST_SUBMITTED` | `request_service.create_request`（提交即待批） | 有 `request.approve` 权限的活跃用户 | 内联 |
| `PO_SUBMITTED` | PO submit | 有 `purchase_order.approve` 权限的活跃用户 | 内联 |
| `PO_APPROVED` | PO approve | 有 `purchase_order.approve` 权限的活跃用户 | 内联 |
| `PART_LOW_STOCK` | 调度 tick | 有 `part.edit` 权限的活跃用户 | 轮询·边沿 |

### 4.1 接收人 helper
- `resolve_wo_recipients(db, wo, *, exclude_actor_id) -> set[str]`：合并 `primary_user_id` + `WorkOrderAssignee.user_id`（多人）+ `WorkOrderTeam` → `TeamUser.user_id`（团队成员展开），过滤 `User.status == 'active'`，去掉 `exclude_actor_id`。
- `resolve_permission_holders(db, company_id, code) -> set[str]`：复用 `app.permissions.effective_codes`，返回该公司内 effective 权限含 `code` 的活跃用户 id 集合。

### 4.2 自动建单接收人兜底
PM/meter 自动建单时新单通常尚无指派人；若 `resolve_wo_recipients` 为空，回退到「该公司 admin/super_admin 活跃用户」（按角色解析兜底；自动建单是系统行为，admin 角色兜底足够，无需按权限码）。

## 5. 生成机制

### 5.1 内联事件（同事务原子）
`notification_service.notify(db, *, recipient_ids, type, entity_type, entity_id, params, actor_user_id, company_id, dedup_key=None)`：仅向传入 session `add` 通知行，**由调用方所在事务提交**——与领域动作原子一致（动作回滚则无通知）。在既有 service 函数内、紧随活动日志写入处调用。

### 5.2 调度 tick（轮询·边沿）
`app/tasks/due_reminder.py::run(db)`，仿 `app/tasks/pm_generate.py` 在 `app/tasks/scheduler.py` 的 `build_scheduler()` 注册新 job（建议 `CronTrigger` 每日晨间）。

跨租户：tick 无请求上下文，按 PM/meter 任务同模式查全租户行、把源实体 `company_id` 写到通知与 arm 行。

**到期窗口**（`config.settings` 可调，默认 `notify_due_soon_days = 3`）：
- `WO_DUE_SOON`：`due_date` 在 `[today, today + N)` 且 `status` 非 COMPLETE/CANCELED
- `WO_OVERDUE`：`due_date < today` 且 `status` 非 COMPLETE/CANCELED
- 边沿键：`WO_DUE_SOON:{wo_id}:{due_date.isoformat()}`、`WO_OVERDUE:{wo_id}:{due_date.isoformat()}`（due_date 改变 → 键变 → 自然 re-arm；WO 进终态或改期后旧条件消失 → 删旧 arm）

**低库存**（轮询·边沿）：
- 条件：`Part.is_active` 且 `not non_stock` 且 `quantity < min_quantity`
- 边沿键：`PART_LOW_STOCK:{part_id}`
- 低于 min 且无 arm → 发通知（给 `part.edit` 持有者）+ 插 arm；回升 ≥ min 且有 arm → 删 arm

## 6. 自抑制

默认**不通知触发者本人**（自己指派给自己、自己改状态等），由 `exclude_actor_id` 实现。调度产生的通知无 actor，不抑制。

## 7. API（`/api/v1/notifications`）

个人数据，**不新增权限码**——任何已认证用户访问**自己**的通知（区别于 `analytics.view`）。所有端点双重作用域：租户（`with_loader_criteria`）+ `recipient_user_id == current_user.id`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | feed；`page`+`page_size`（仿 audit_logs，默认 20，≤200）；过滤 `is_read` / `type` / `date_from` / `date_to`；排序 `created_at DESC`；返回 `{items, total, page, page_size, total_pages}` |
| GET | `/unread-count` | `{count: int}` |
| POST | `/{id}/read` | 标记单条已读（非本人/不存在 → 404）；幂等 |
| POST | `/read-all` | 全部标记已读，返回 `{updated: int}` |

## 8. RBAC / 租户 / 跨方言

- **RBAC**：无新权限码；认证即可访问本人通知。生成端的接收人解析复用既有 `effective_codes`。
- **租户隔离**：feed/标记已读经 `with_loader_criteria` 自动作用域，且额外 `recipient_user_id` 过滤；跨租户隔离须 API 测断言（造两公司，A 用户看不到 B 的通知）。
- **跨方言**：无金额/时长聚合；`params` 用 Text 列存 `json.dumps` 字符串、读时 `json.loads`（不用方言 JSON 类型，SQLite/MySQL 行为确定）。`dedup_key` 字符串比较，方言无关。

## 9. 测试策略

- **notification_service 单测**：接收人解析（primary+assignee+team 展开、过滤非活跃、去重）、自抑制、`resolve_permission_holders`、`notify` 落行字段正确。
- **边沿去重单测**：arm/re-arm（条件消失删 arm、再触发再发；due_date 改变换键）。
- **内联生成测**：各事件在对应 service 函数被调用后正确生成通知（指派/状态/审批/自动建单）。
- **due_reminder tick 测**：DUE_SOON/OVERDUE 窗口边界（含 today、终态排除）、低库存边沿、跨租户落行 company_id 正确。
- **API 测**：feed 分页/过滤、未读数、标记已读（单条 + 全部、幂等、非本人 404）、跨租户隔离、只能见/改自己的通知。
- **全量回归**：基线 1040 + 本期新增，0 failed。
- **alembic**：本期 +1 迁移（2 表），迁移后单 head 推进。

## 10. 单元边界（isolation & clarity）

- `app/models/notification.py`：2 个 ORM 模型（Notification、NotificationArm），纯声明。
- `app/services/notification_service.py`：`notify(...)`（落行）、接收人 helper、arm/re-arm 边沿原语（`is_armed`/`arm`/`disarm` 或等价）。不含 HTTP/调度逻辑。
- `app/schemas/notification.py`：feed 响应 / 单条 / 未读数 / 分页包装。
- `app/routers/notifications.py`：4 端点，薄控制器，调 service。
- `app/tasks/due_reminder.py`：`run(db)` 编排，调 service 原语；scheduler 仅注册 job。
- 既有 service（work_order/request/purchase_order/pm/meter_trigger）：仅在事件点**追加** `notify(...)` 调用，不重构既有逻辑。
