# 工单补全 2A · WO3 工时成本 — 设计

**日期**：2026-06-02
**分支**：`feat/workorder-backfill`
**所属**：Atlas 复刻补全 · 第 2 组「工单补全」· 子轮 2A（最高优先，解锁第 5 组分析）
**范围**：纯后端、净室原创。前端 UI / 移动端逐步执行界面后移，不在本轮。

## 0. 净室声明（红线）

本设计参照通用 CMMS 工单「工时成本」的**功能行为**（计时/费率/额外成本/总成本聚合），全新原创实现。
绝不复制 Atlas 的代码 / DDL / 文案 / 命名 / 资源；命名一律自有（`tb_work_order_labor`、
`tb_work_order_additional_cost`、`tb_time_category`）；产品不出现 "Atlas"。GPL 合规为根本前提。

## 1. 子轮切分背景

第 2 组拆 3 子轮串行，本轮为 2A：

- **2A（本轮）**：WO3 工时成本 = Labor（计时器+手填）+ TimeCategory + AdditionalCost + 总成本实时聚合。
- 2B（后续）：完成字段族 + Relation 关联 + 按备件反查 + canBeEditedBy 谓词。
- 2C（后续）：工单 PDF 报告 + 看板/日历数据投影 + 执行签名/步骤照片后端。

## 2. 现状核实结论（落地依据）

- `WorkOrder`(`tb_work_order`) 已是 `TenantMixin`；状态机 OPEN/IN_PROGRESS/ON_HOLD/COMPLETE/CANCELED；
  已有 `completed_at`、活动时间线 `WorkOrderActivity`、SOP 执行行 `WorkOrderStepResult`。
- **`CostCategory`(`tb_cost_category`) 已是完整特性**：model + `cost_category_service` + router
  `/api/v1/cost-categories` + 权限 `cost_category.view/manage` + schema（在 `app/schemas/partner.py`），
  per-company（`TenantMixin`+`SoftDeleteMixin`），唯一约束 `uq_cost_category_company_name`。
  → **AdditionalCost 复用它做分类，不重造。**
- **备件成本已有现成数据源**：`PartConsumption`(`tb_part_consumption`)，字段 `quantity`/`unit_cost`
  均 `Numeric(18,4)`，挂 `work_order_id`。总成本聚合直接 SUM 它。
- `User` **当前无 hourly_rate 字段** → 费率不走 User，走 TimeCategory 默认 + Labor 行快照。
- 单号 `sequence_service.next_value(db, scope, company_id)` + `format_custom_id` 已就绪
  （Labor/AdditionalCost 为子资源，**不需要 customId**）。
- 权限码现有 `work_order.view/create/edit/delete/execute`；TimeCategory 主数据按 cost_category 模式
  新增 `time_category.view/manage`。
- TimeCategory router 镜像 `cost_categories.py`（VIEW→list/get、MANAGE→create/patch/delete，204 删除）。

## 3. 数据模型（3 张新表，均挂 `TenantMixin`）

所有表继承 `Base, UUIDMixin, TimestampMixin, TenantMixin`（`company_id` NOT NULL，
ORM 事件自动 scope + before_flush stamp）。

### 3.1 `TimeCategory` — `tb_time_category`（镜像 CostCategory）

| 字段 | 类型 | 约束/默认 |
|---|---|---|
| name | String(300) | NOT NULL |
| hourly_rate | Numeric(18, 4) | NOT NULL, default 0, server_default "0" |
| description | Text | default "", server_default "" |

- 额外继承 `SoftDeleteMixin`（同 CostCategory）。
- 唯一约束 `uq_time_category_company_name`("company_id", "name")。
- 主数据：完整 CRUD，软删（`is_active=False`）。

### 3.2 `Labor` — `tb_work_order_labor`（工时：计时器 + 手填二合一）

| 字段 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| work_order_id | String(36) FK→tb_work_order ondelete=CASCADE | NOT NULL, index | |
| user_id | String(36) FK→tb_user ondelete=SET NULL | nullable | 干活的人，默认操作者，可指定（代他人记） |
| time_category_id | String(36) FK→tb_time_category ondelete=RESTRICT | **nullable** | 可选；选了则费率默认取分类 |
| started_at | DATETIME6 | nullable | 计时器起点；手填时可空 |
| stopped_at | DATETIME6 | nullable | 计时器终点；手填时可空 |
| duration_seconds | Integer | NOT NULL, default 0, server_default "0" | **成本计算唯一依据** |
| hourly_rate | Numeric(18, 4) | NOT NULL | 创建时从分类默认值快照、可覆盖；快照后不随分类改动而变 |
| notes | Text | default "", server_default "" | |

**行为约定**
- **运行中（running）判定**：`started_at IS NOT NULL AND stopped_at IS NULL`。
- 每 `(work_order_id, user_id)` **至多一个运行中计时器**；再次 start → 409 `LABOR_TIMER_RUNNING`。
- **运行中计时器对成本贡献 0**，直到 stop 才把 `duration_seconds = int((stopped_at - started_at).total_seconds())`
  落定 → 成本数学纯净、不依赖 `now()`（也利于 SQLite/MySQL 一致与测试确定性）。
- 单条 `cost`（**只读计算属性，不落库**）= `Decimal(duration_seconds) / 3600 * hourly_rate`。
- 列表/读取可附 `running_elapsed_seconds`（只读展示，运行中 = `now()-started_at` 取整，非运行中 = None）；
  **该字段不入成本账**。
- CRUD：支持 PATCH（改 duration_seconds / hourly_rate / time_category_id / notes / user_id）、
  **硬 DELETE**（改错即删，非 append-only）。

### 3.3 `AdditionalCost` — `tb_work_order_additional_cost`

| 字段 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| work_order_id | String(36) FK→tb_work_order ondelete=CASCADE | NOT NULL, index | |
| cost_category_id | String(36) FK→**tb_cost_category** ondelete=RESTRICT | nullable | **复用现有 CostCategory** |
| title | String(300) | NOT NULL | |
| amount | Numeric(18, 4) | NOT NULL | |
| description | Text | default "", server_default "" | |
| created_by_user_id | String(36) | nullable | 默认操作者 |

CRUD：PATCH + 硬 DELETE。

## 4. 总成本聚合（实时，不落字段）

新建 `app/services/work_order_cost_service.py`，纯函数计算，无缓存字段：

```
labor_total      = Σ (duration_seconds / 3600 * hourly_rate)   over tb_work_order_labor
additional_total = Σ amount                                    over tb_work_order_additional_cost
parts_total      = Σ (quantity * unit_cost)                    over tb_part_consumption
```

- 全程 `Decimal`；三个小计各自 `.quantize(Decimal("0.01"), ROUND_HALF_UP)`。
- `total = labor_total + additional_total + parts_total`（三个**已量化**小计之和），
  保证「明细之和 == 总计」一分不差。
- 仅按 `work_order_id` 过滤；company scope 由 `TenantMixin` 的 ORM 事件兜底（不手写 company 过滤，
  但路由层 `_ensure` 已校验 `wo.company_id == current_user.company_id`）。
- labor 行的 `cost` 用各行 `hourly_rate` 快照计算（非分类当前值）。

## 5. 端点

均在 `/api/v1/work-orders/{work_order_id}` 下；**写=`work_order.edit`，读=`work_order.view`**。
路由层 `_ensure` 校验工单归属当前租户；子资源行额外校验 `row.work_order_id == path` 且
`row.company_id == current_user.company_id`，否则 404。

### Labor
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/labor` | view | 列出该工单工时（按 created_at, id 序）|
| POST | `/labor` | edit | 手填一条（duration_seconds 必填；可带 started_at/stopped_at/time_category_id/hourly_rate/user_id/notes）|
| POST | `/labor/start` | edit | 开计时器（建运行中行；body 可选 time_category_id/user_id/hourly_rate）；同 (wo,user) 已有运行中 → 409 |
| POST | `/labor/{labor_id}/stop` | edit | 停计时器；落定 duration_seconds；非运行中 → 400 `LABOR_NOT_RUNNING` |
| PATCH | `/labor/{labor_id}` | edit | 改 duration_seconds/hourly_rate/time_category_id/notes/user_id |
| DELETE | `/labor/{labor_id}` | edit | 硬删，204 |

**费率默认解析（create/start 时）**：payload 给了 `hourly_rate` → 用之；否则若 `time_category_id`
非空 → 取该分类 `hourly_rate`；否则 → 0。落库为快照。

### AdditionalCost
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/additional-costs` | view | 列出 |
| POST | `/additional-costs` | edit | 建（title/amount 必填；cost_category_id/description 可选；created_by 默认操作者）|
| PATCH | `/additional-costs/{cost_id}` | edit | 改 title/amount/cost_category_id/description |
| DELETE | `/additional-costs/{cost_id}` | edit | 硬删，204 |

### 成本汇总
| 方法 | 路径 | 权限 | 返回 |
|---|---|---|---|
| GET | `/cost-summary` | view | `{labor_total, additional_total, parts_total, total}`（均 2dp 字符串/Decimal）|

### TimeCategory 主数据（新 router）
`/api/v1/time-categories` CRUD，镜像 `cost_categories.py`：
GET list/get→`time_category.view`；POST/PATCH/DELETE→`time_category.manage`；删除 204。

## 6. 权限

`app/permissions.py` 新增：
- `TIME_CATEGORY_VIEW = "time_category.view"`、`TIME_CATEGORY_MANAGE = "time_category.manage"`
- 新增分组 `_TIME_CATEGORY = [TIME_CATEGORY_VIEW, TIME_CATEGORY_MANAGE]`，并入 `ALL_PERMISSIONS`。
- `technician` 内置角色加 `TIME_CATEGORY_VIEW`（镜像 `COST_CATEGORY_VIEW`）；MANAGE 经 ALL_PERMISSIONS 归 admin/super_admin。
- Labor/AdditionalCost **不新增权限码**，写走 `WORK_ORDER_EDIT`、读走 `WORK_ORDER_VIEW`（technician 已具备）。

## 7. 与既有模块关系

- 与 `work_order_execution_service` / `WorkOrderStepResult` **完全解耦**：成本是独立子系统，
  不改执行服务、不改 step result。
- 不改 `WorkOrder` 表结构（总成本实时聚合、不落字段）。
- `to_read` / `WorkOrderRead` **不变**；成本经独立端点取，避免列表查询 N+1。
- 活动时间线（`WorkOrderActivity`）对 labor/cost 的记录**不在 2A**（避免膨胀，可后续补）。

## 8. 错误处理

| 码 | 触发 | HTTP |
|---|---|---|
| WORKORDER_NOT_FOUND | 工单不存在/跨租户 | 404 |
| LABOR_NOT_FOUND | 工时行不存在/不属该工单或租户 | 404 |
| ADDITIONAL_COST_NOT_FOUND | 额外成本行不存在/不属该工单或租户 | 404 |
| TIME_CATEGORY_NOT_FOUND | 分类不存在/跨租户 | 404 |
| LABOR_TIMER_RUNNING | 同 (wo,user) 已有运行中计时器再 start | 409 |
| LABOR_NOT_RUNNING | 对非运行中行调 stop | 400 |
| 校验类（amount<0、duration<0、title 空等）| pydantic / 业务校验 | 422/400 |

约定：金额/时长非负校验（`amount >= 0`、`duration_seconds >= 0`、`hourly_rate >= 0`）。

## 9. 测试策略

pytest 用 SQLite `Base.metadata.create_all`（conftest engine fixture，不依赖 alembic）。

- **TimeCategory**：CRUD、per-company 唯一、软删、跨租户隔离、无 manage 权限 403。
- **Labor 计时器**：start 建运行中行；stop 落定 duration_seconds 与 cost 正确；
  重复 start 同 (wo,user) → 409；对非运行中 stop → 400；running 行 cost=0、不入汇总。
- **Labor 手填**：duration_seconds + 费率 → cost 精度（Numeric/Decimal，含分位舍入）。
- **费率快照与覆盖**：选分类取默认费率；显式 hourly_rate 覆盖；改分类不动已有行快照。
- **AdditionalCost**：CRUD、cost_category 复用、负数 422。
- **总成本聚合**：labor + additional + parts（造 PartConsumption）三类小计与 total 精度，
  「小计之和 == total」；空工单全 0.00。
- **多租户对抗**：A 公司工单的 labor/additional 不出现在 B 的列表/汇总；跨租户取行 404。
- **权限**：无 `work_order.edit` 写 labor/cost → 403；无 `work_order.view` 读 → 403。
- **收口**：全量 `pytest -q` + `ruff check app/` + `mypy app/` 全绿。

## 10. 迁移

子轮**最后一个 task** 写 1 个 alembic 迁移，建 `tb_time_category`、`tb_work_order_labor`、
`tb_work_order_additional_cost` 三表（含索引/唯一约束/FK，含 `company_id` FK 与 TenantMixin 列）。

- 验 `up / down / up` 可重放 + `alembic check`（autogenerate）零漂移。
- MySQL：用最小 fixture 验 DDL（建表/索引/FK），全链重放受既有 `initial_schema` TEXT
  server_default 问题阻塞（与本迁移无关），全链待生产手验。
- 无数据平移（全新表）。

## 11. 实现单元划分（供 writing-plans 参考）

1. TimeCategory：model + schema + service + router + 权限码 + 测试。
2. Labor：model + schema（含 cost/running_elapsed 只读）+ service（费率解析/计时器/手填）+ 测试。
3. Labor 路由：start/stop/CRUD 端点 + 权限 + 跨租户 + 测试。
4. AdditionalCost：model + schema + service + 路由 + 测试。
5. 成本聚合：`work_order_cost_service` + `/cost-summary` 端点 + 精度/聚合测试。
6. alembic 迁移（末置）+ up/down/up + autogenerate 零漂移 + MySQL DDL 最小验证。

每 task 测试绿 + ruff + mypy 才提交。
