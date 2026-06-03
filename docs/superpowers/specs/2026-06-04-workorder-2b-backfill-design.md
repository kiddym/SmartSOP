# 工单 2B 后端补全 — 设计文档

**日期**：2026-06-04
**范围**：纯后端 Atlas parity 补全（工单子轮 2B）。承接 5 组补全已完成基线（见 `atlas-parity-backfill` 内存）。
**执行模式**：独立 git worktree、全程 TDD（SQLite）、净室原创（仅按 parity 功能对账，不碰 Atlas 代码）。

## 1. 目标与背景

工单后端核心（CRUD/指派/状态机/工时成本 WO3/SOP 执行）已就绪。2B 补齐 Atlas 工单的"完成字段族 + 工单间关联 + 按备件反查 + 对象级可编辑谓词"四块缺口，并为分析层"估时 vs 实际工时"解锁前置字段。

**现状关键点**（调研于 2026-06-04，`backend/app/`）：
- `WorkOrder`（`models/work_order.py:27-89`）已有 `TenantMixin/company_id`、`completed_at`、`priority`(NONE/LOW/MEDIUM/HIGH)、`created_by_user_id`、assignee/team M:N 关联。
- 状态机（`models/work_order_status.py`）：OPEN/IN_PROGRESS/ON_HOLD/COMPLETE/CANCELED，转移逻辑在 `work_order_service.transition()`（`services/work_order_service.py:231-264`），进入 COMPLETE 已自动戳 `completed_at`、重开清空。
- `PartConsumption`（`models/part_consumption.py`，表 `tb_part_consumption`）有 `work_order_id`/`part_id`，但**无按备件反查工单**的查询。
- 权限仅路由层全局 `require_permission`，**无对象级谓词**。
- 工单**无自关联/Relation**。

## 2. 数据模型变更

### 2.1 WorkOrder 加 8 列

迁移用 `batch_alter_table`（SQLite 兼容）。

| 列 | 类型 | 约束/默认 | 语义 |
|---|---|---|---|
| `completed_by_user_id` | String(36) | nullable，弱引用无 FK | 进入 COMPLETE 时戳记 actor，重开清空 |
| `feedback` | Text | nullable | 完成反馈文本 |
| `urgent` | Boolean | NOT NULL, default False | 独立紧急旗标，与 priority 正交 |
| `estimated_duration` | Integer | nullable | 预估工时，**单位：分钟** |
| `estimated_start_date` | Date | nullable | 预计开始日 |
| `first_responded_at` | DATETIME(6) | nullable | 首次离开 OPEN 时戳记，只记一次 |
| `archived` | Boolean | NOT NULL, default False | 归档维度，与 is_active 软删正交 |
| `is_compliant` | Boolean | nullable | 完成时自动判定的快照；未完成=NULL |

`completed_by_user_id` 采用弱引用（无 FK，String(36)），与现有 `created_by_user_id`/`request_id`/`procedure_id` 的弱引用约定一致。

### 2.2 新表 `tb_work_order_relation`

继承 `UUIDMixin + TimestampMixin + TenantMixin`。

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | String(36) | PK |
| `company_id` | String(36) | TenantMixin, FK→tb_company, NOT NULL |
| `source_work_order_id` | String(36) | FK→tb_work_order.id, CASCADE, 索引 |
| `target_work_order_id` | String(36) | FK→tb_work_order.id, CASCADE, 索引 |
| `relation_type` | Enum(WorkOrderRelationType) | NOT NULL |
| `created_by_user_id` | String(36) | nullable, 弱引用 |
| `created_at` / `updated_at` | DATETIME(6) | TimestampMixin |

约束：`UniqueConstraint(source_work_order_id, target_work_order_id, relation_type)`。

`WorkOrderRelationType` 枚举：`DUPLICATE` / `RELATED`（对称语义）、`SPLIT` / `BLOCKS`（有向语义）。

**跨租户校验**：建立 relation 时校验 `target_work_order` 与 source 同 `company_id`，否则 404（复刻库存补全 6 张 M:N 关联表的跨租户校验范式）。同时禁止 `source == target` 自指。

## 3. Service 钩子（`work_order_service.transition()` 内）

在现有转移逻辑基础上扩展：

- **进入 COMPLETE**：
  - 沿用现有 `completed_at = utcnow()`；
  - 加 `completed_by_user_id = actor_user_id`；
  - 计算并存快照 `is_compliant = (wo.due_date is None) or (completed_at.date() <= wo.due_date)`（无截止日视为合规）。
- **重开 COMPLETE→IN_PROGRESS**：沿用现有清 `completed_at`；增清 `completed_by_user_id = None`、`is_compliant = None`。
- **首次离开 OPEN**（OPEN → 任意非 OPEN 状态，含 IN_PROGRESS/CANCELED）：`if wo.first_responded_at is None: wo.first_responded_at = utcnow()`。只记一次，重开不覆盖。
  - MTTA = `first_responded_at - created_at`，计算归分析层，本轮只落原始时间戳。

判定均为纯函数 + 不依赖"当前时间"做条件分支（`is_compliant` 用已戳的 `completed_at`，避免测试对 now 的耦合）。

## 4. canBeEditedBy 对象级谓词

新增纯函数 `can_edit_work_order(db, user, wo) -> bool`，规则三条（短路顺序）：

1. user 角色为 `admin` / `super_admin` → True；
2. `wo.status ∈ {COMPLETE, CANCELED}` → False（**终态锁**）；
3. `user.id == wo.created_by_user_id`，或 `user.id ∈ {wo.primary_user_id} ∪ assignee_ids` → True；否则 False。

**作用边界（关键澄清）**：
- 该谓词**仅门控 PATCH 字段编辑**（`PATCH /work-orders/{id}`）。调用者无对象级编辑权 → 403。
- **状态流转 `transition` 不套终态锁**，仍走现有 `work_order.edit` 权限 + 状态机合法转移表。否则非 admin 无法 reopen 自己完成的工单（COMPLETE→IN_PROGRESS）。
- `WorkOrderRead` 附 `can_be_edited: bool`（对当前请求用户求值）供前端置灰按钮。

## 5. API 变更

### 5.1 Relation 端点（`routers/work_orders.py`）

- `GET /work-orders/{id}/relations` — 读=`work_order.view`。**双向展开**：
  - 对称类型（DUPLICATE/RELATED）：union 该工单作为 source 或 target 的记录，不分方向；
  - 有向类型（SPLIT/BLOCKS）：区分 source/target，响应标 `direction: outgoing|incoming`（如 `blocks` ↔ `blocked_by`、`split_into` ↔ `split_from`）。
- `POST /work-orders/{id}/relations` — 写=`work_order.edit`。body：`{target_work_order_id, relation_type}`。跨租户/自指/重复 → 对应 404/400/409。
- `DELETE /work-orders/{id}/relations/{relation_id}` — 写=`work_order.edit`。

### 5.2 按备件反查工单

- `GET /work-orders` LIST 加 `part_id` 过滤参数：JOIN `tb_part_consumption` 取消耗过该备件的工单。复用现有 LIST 过滤模式（已有 status/priority/asset_id/location_id/assignee_id/procedure_attached），**不新增端点**。租户隔离自动生效。

### 5.3 WorkOrderRead 扩展

按"加列改 4 处"约定改：
1. `models/work_order.py`（WorkOrder 类加列 + WorkOrderRelation/枚举新文件）；
2. `services/work_order_service.py` `to_read()`（映射新字段 + `can_be_edited` 求值 + relations 摘要计数）；
3. `schemas/work_order.py` `WorkOrderRead`（加 8 字段 + `can_be_edited` + relation 计数）+ 新增 Relation 读/写 schema；
4. `routers/work_orders.py`（Relation 3 端点 + LIST `part_id` 参 + PATCH 接 `can_edit_work_order` 守卫）。

## 6. 权限

复用现有工单权限码，无新增：
- Relation 读/反查 LIST = `work_order.view`；
- Relation 写、PATCH 字段编辑 = `work_order.edit`。

## 7. 迁移

单个 alembic 迁移 `workorder_2b_backfill`：
- `down_revision = "inventory_backfill"`（当前 head）；
- up：`batch_alter_table` 给 WorkOrder 加 8 列 + `create_table` 建 `tb_work_order_relation`（含枚举、唯一约束、索引）；
- down：drop 表 + drop 8 列；
- up/down/up 可重放、新对象零漂移（DB-diff 强验）。

## 8. 测试（TDD，SQLite）

每项先红后绿，覆盖：
- 8 字段加列 + 默认值 + `to_read` 映射；
- transition 钩子：COMPLETE 戳 completed_by/is_compliant（有/无 due_date 两分支、逾期/准时两分支）、重开清空、首次离开 OPEN 戳 first_responded_at 且重开不覆盖；
- `can_edit_work_order` 谓词：admin 全权、终态锁、创建者/指派者命中、无关用户 403；PATCH 终态 403 但 transition reopen 仍通；
- Relation：建立/双向展开查询/删除、对称 vs 有向方向标注、唯一约束 409、自指 400；
- **跨租户对抗**（复刻 `tests/test_sop_tenant.py` 范式）：Relation target 跨租户→404、LIST `part_id` 过滤跨租户隔离、can_edit 谓词不泄漏他租户工单。

## 9. 留作后续（非 2B 范围）

- 工单 PDF 报告、看板/日历视图、执行签名+步骤照片 = 工单 2C。
- 前端展示新字段/Relation = 后续前端轮次。
- 分析"估时 vs 实际工时"消费 `estimated_duration` = 分析后续轮次（本轮只落字段）。

## 附：已定默认（可在 review 调整）

- `estimated_duration` 单位 = 分钟；
- `is_compliant` 无 due_date 视为合规；
- canBeEditedBy 只锁 PATCH 字段编辑、不锁 reopen transition。
