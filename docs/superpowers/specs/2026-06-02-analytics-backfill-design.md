# 设计：分析补全 ⑤（Atlas parity backfill · group 5）

- 日期：2026-06-02
- 范围：后端只读分析聚合补全，一轮交付 8 项分析 + 2 处工单 schema 前置
- 依赖：第 2 组工单补全 2A（工时成本）已完成并合并入 main，labor/additional 成本数据源就绪
- 基线约束：净室原创（仅参照通用 CMMS 分析功能行为，绝不复制 Atlas 代码/DDL/文案/命名；产品不出现 "Atlas"；GPL 合规根本前提）；仅中文、不做 i18n；后端解释器统一 `backend/.venv/bin/python`；门禁 ruff 0.15 + mypy 1.20；pytest 用 SQLite `Base.metadata.create_all`（conftest engine fixture，非 alembic）

## 1. 背景与目标

现有分析模块（`/api/v1/analytics`，只读，需 `analytics.view`）覆盖约 70%：

- `/work-orders`：total、by_status、by_priority、completion_rate、avg_cycle_time、avg_response_time、overdue
- `/costs`：parts 消耗成本（by_part / by_asset）+ PO 承诺采购额（by_vendor）
- `/asset-reliability`：可用率、MTTR、MTBF（区间裁剪、车队级汇总）
- `/inventory`：库存价值（by_category）、低库存、窗内 top 消耗
- `/{dashboard}/export`：四面板 CSV 导出

对照通用 CMMS 分析功能基线，缺口集中在：成本（缺 labor/additional，2A 已解锁）、工单多维分布、时间序列、请求独立分析、人员分析、备件 Pareto/ABC、资产维护成本。本轮一次补齐 8 项，达成分析模块功能完整。

**目标**：让分析模块功能完整可用（消费已就绪后端数据），全部新增字段对现有响应**增量、不破坏兼容**（前端尚未建，加字段安全）。

## 2. 两处工单 schema 前置

两项分析（工单 `by_category`、人员"创建数"）所需底层字段在当前 schema 中缺失，本轮最小补齐。

### 2.1 WorkOrderCategory（新表，复刻 2A TimeCategory 模式）

- 表 `tb_work_order_category`
- 列：`name` String(300) NOT NULL；`description` Text server_default=""；外加 `UUIDMixin`/`TimestampMixin`/`SoftDeleteMixin`/`TenantMixin`（与 TimeCategory 完全对称）
- 唯一约束：`uq_work_order_category_company_name(company_id, name)`
- 排序：list 按 `name, id`
- 软删除：`delete` 置 `is_active=False` + `deleted_at=utcnow()`；`get`/`list` 跳过软删

CRUD 端点 `/api/v1/work-order-categories`（复刻 `time_categories.py` 结构）：

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/` | `work_order_category.view` | list（默认仅 is_active；可加 `include_inactive`，与 time_category 一致策略） |
| GET | `/{id}` | `work_order_category.view` | get，软删/不存在→404 `WORK_ORDER_CATEGORY_NOT_FOUND` |
| POST | `/` | `work_order_category.manage` | create，重名→409 `WORK_ORDER_CATEGORY_DUPLICATE` |
| PATCH | `/{id}` | `work_order_category.manage` | update（model_dump exclude_unset） |
| DELETE | `/{id}` | `work_order_category.manage` | 软删，204 |

权限新增 `WORK_ORDER_CATEGORY_VIEW="work_order_category.view"`、`WORK_ORDER_CATEGORY_MANAGE="work_order_category.manage"`，加入 `ALL_PERMISSIONS` 新分组；technician 仅获 view（与 time_category 对称）。

### 2.2 工单加列

在 `tb_work_order` 增两列：

- `category_id` String(36) nullable，FK→`tb_work_order_category.id` `ondelete=SET NULL`，index
- `created_by_user_id` String(36) nullable，index，**无 FK**（复刻 `WorkOrderAdditionalCost.created_by_user_id` 模式，避免 user 删除连锁）

接线：

- `WorkOrderCreate` 增可选 `category_id`；`create_work_order` 将 `actor_user_id` 落入 `created_by_user_id`（现有签名已有 `actor_user_id` 参数，无需改调用方）
- `WorkOrderUpdate` 增可选 `category_id`
- `WorkOrderRead`（或等价输出）暴露 `category_id`、`created_by_user_id`
- 若 `category_id` 指向他租户/不存在的分类，create/update 校验→404 `WORK_ORDER_CATEGORY_NOT_FOUND`（复刻 2A labor 对 time_category 的跨租户校验）

### 2.3 迁移

单个迁移文件，`down_revision="workorder_labor_cost"`（2A 的 revision）：

1. `create_table tb_work_order_category`（含索引 company_id / created_at / is_active，与 mixin 一致）
2. `add_column tb_work_order.category_id` + FK + index
3. `add_column tb_work_order.created_by_user_id` + index

downgrade 逆序：drop 两列 → drop category 表。MySQL 全链重放受既有 initial_schema 问题阻塞（与本迁移无关），DDL 以最小 fixture 单元测试验证，全链待生产手验（沿用 2A 迁移声明）。

## 3. 8 项分析

通用约定（沿用现有 `_common.py`）：时间窗 `resolve_window`（半开 `[start, end_excl)`，默认最近 90 天）；时长/金额一律 Python 计算（`hours_between`、Decimal），跨方言安全；金额量化沿用 2A —— 每小计 `ROUND_HALF_UP` 量化到 2dp 再求和，保证"明细之和==总计"。

### ① `/costs` 扩展 —— labor / additional 成本（2A 核心解锁）

现有响应保留。新增：

- `labor_cost` Decimal：Σ `labor.compute_cost(row)`，按 `labor.created_at ∈ 窗`，经 WO 关联支持 `asset_id`/`location_id` 过滤
- `additional_cost` Decimal：Σ `additional.amount`，按 `additional.created_at ∈ 窗`，同样支持过滤
- `total_maintenance_cost` Decimal = `_q(parts) + _q(labor) + _q(additional)`
- `maintenance_cost_by_asset` list[{asset_id: str|None, parts_cost, labor_cost, additional_cost, total}]，按 total 降序

**日期基准明确**：labor/additional 以各自 `created_at`（记录登记时刻）落窗——与 parts 的 `consumed_at` 语义对齐（成本发生时刻），文档化。

`compute_cost` 为 2A 纯函数：运行中计时器（无 `stopped_at`）计 0，不依赖 `now()`。

### ② `/work-orders` 扩展 —— 多维分布

现有响应保留。新增（窗口/过滤同现有 `/work-orders`）：

- `by_asset` list[{asset_id: str|None, count}]，按 count 降序，None 桶=未关联资产
- `by_user` list[{user_id: str|None, count}]，按 `primary_user_id`，None 桶=未指派
- `by_category` list[{category_id: str|None, count}]，按 `category_id`（2.2 新列），None 桶=未分类

### ③ `/inventory` 扩展 —— Pareto / ABC

现有响应保留。新增：

- `abc_classification` list[{part_id, custom_id, name, consumption_value: Decimal, cumulative_pct: float, abc_class: "A"|"B"|"C"}]
  - 排序：按窗内消耗价值 `Σ(qty × unit_cost)` 降序
  - `cumulative_pct`：累计消耗价值占总消耗价值的百分比（基于排序前缀）
  - 分级：`cumulative_pct ≤ 80 → A`；`≤ 95 → B`；其余 `C`（标准 ABC 80/15/5）
  - 总消耗价值为 0（无消耗）时返回空 list
- `abc_summary` {A: int, B: int, C: int} 各级零件数

注：消耗价值用 `PartConsumption.unit_cost`（消耗当时单价快照），与 `/costs` 一致；`/inventory` 现有 `top_consumed_parts` 按量、ABC 按价值，两者互补保留。

### ④ `/asset-reliability` 扩展 —— 维护总成本 / 价值比

现有每资产行保留。新增每行：

- `total_maintenance_cost` Decimal：该资产窗内 parts + labor + additional 成本（均经 WO `asset_id` 归属，量化求和）
- `acquisition_cost` Decimal|None：`asset.acquisition_cost`（价值基准，可空）
- `cost_to_value_ratio` float|None：`total_maintenance_cost / acquisition_cost`；`acquisition_cost` 为 None 或 ≤0 时为 None（即维护成本对资产价值比，RAV 比率）

车队级新增 `fleet_total_maintenance_cost` Decimal。

成本归属与 ① 共享同一聚合逻辑（抽公共纯函数 `maintenance_cost_by_asset(db, start, end_excl) -> dict[asset_id, {parts,labor,additional}]`，供 ① 与 ④ 复用，避免重复）。

### ⑤ `/requests`（新端点）

`GET /api/v1/analytics/requests`，权限 `analytics.view`，参数 `date_from`/`date_to`（按 `created_at` 落窗）/`asset_id`/`location_id`。响应：

- `date_from`/`date_to`
- `total` int（窗内 created）
- `by_status` dict[str, int]（覆盖 RequestStatus 全枚举 PENDING/APPROVED/REJECTED/CANCELED）
- `by_priority` dict[str, int]（覆盖 WorkOrderPriority 全枚举）
- `received` int（窗内 created，== total）
- `resolved` int（`resolved_at ∈ 窗`）
- `avg_resolution_cycle_hours` float|None（对 `resolved_at ∈ 窗` 的请求，`created_at → resolved_at` 均值）
- `converted` int（窗内 created 且 `work_order_id` 非空——已转工单）

### ⑥ `/personnel`（新端点）

`GET /api/v1/analytics/personnel`，权限 `analytics.view`，参数 `date_from`/`date_to`。响应 `users` list[{user_id, name, created_count, completed_count, assigned_count, labor_hours, labor_cost}]：

- `created_count`：WO `created_by_user_id == user`，`created_at ∈ 窗`（2.2 新列）
- `completed_count`：`WorkOrderActivity` `activity_type/to_status == COMPLETE` 的 `actor_user_id == user`，`created_at ∈ 窗`
- `assigned_count`：`WorkOrderAssignee` 该 user 关联、且 WO `created_at ∈ 窗`（assignee 行 created_at 与 WO 同期，取 WO 落窗）
- `labor_hours` float：Σ `duration_seconds / 3600`，`labor.user_id == user`，`created_at ∈ 窗`
- `labor_cost` Decimal：Σ `compute_cost`，同上集合

只列在窗内有任一活动的用户；`name` 取 `User.name`（或等价显示字段，实现时核对）。按 user_id 稳定排序。

### ⑦ `/trends`（新端点，时间序列）

`GET /api/v1/analytics/trends`，权限 `analytics.view`，参数 `date_from`/`date_to`/`granularity=day|week`（默认 `day`，非法值→400）。响应：

- `date_from`/`date_to`/`granularity`
- `buckets` list[{bucket_start: date, work_orders_created, work_orders_completed, requests_received, requests_resolved}]
  - 桶覆盖整个窗口（含计数为 0 的空桶，保证序列连续）
  - `day`：逐日；`week`：以 ISO 周一为起点的 7 天桶（首桶可能不满一周，从 `date_from` 起）
  - `work_orders_created`：WO `created_at` 落桶；`work_orders_completed`：`completed_at` 落桶
  - `requests_received`：Request `created_at` 落桶；`requests_resolved`：`resolved_at` 落桶
- 分桶为纯函数（输入窗口 + granularity → 桶边界列表），便于单测

**范围说明**：完整"按日期状态分布历史重建"（每个时点的工单状态快照）需对活动流做事件回放，超出本轮范围；trends 提供吞吐计数序列（创建/完成/收到/解决），即"周级时间序列"+"收到 vs 解决"的时间视图。文档化此简化。

## 4. 横切

### 4.1 权限

- 全部新分析端点（requests/personnel/trends）复用 `ANALYTICS_VIEW`
- 新增 `work_order_category.view/manage`（§2.1）

### 4.2 CSV 导出

`/{dashboard}/export` switch 补三新面板：`requests`、`personnel`、`trends`（机械对称现有 `_*_csv` 模式，各自 header + 扁平行）。未知面板仍 404 `ANALYTICS_DASHBOARD_NOT_FOUND`。

### 4.3 多租户

- `WorkOrderCategory` 挂 `TenantMixin`（company_id NOT NULL，ORM 事件自动 scope SELECT + before_flush 落戳）
- 现有分析查询已由 ORM `do_orm_execute` 事件按 company 自动隔离；新端点查询同样受益（确认查询对象均为 TenantScoped 子类）
- `created_by_user_id` 仅为列，非租户边界
- **跨租户对抗必测**：WorkOrderCategory CRUD（A 公司不可见/改/删 B 的分类；PATCH WO `category_id` 指向他租户→404）；各新分析端点（A 公司聚合不含 B 数据）

### 4.4 错误码

新增：`WORK_ORDER_CATEGORY_NOT_FOUND`(404)、`WORK_ORDER_CATEGORY_DUPLICATE`(409)、trends `granularity` 非法→400 `INVALID_GRANULARITY`（沿用 `app/errors.py` 的 not_found/conflict/bad_request 助手）。

## 5. 测试策略

沿用现有 analytics 测试 + 2A 模式（SQLite in-memory，conftest fixture）：

- **WorkOrderCategory**：CRUD + 软删 + 重名 409 + 权限矩阵 + 跨租户对抗（service + API 两层）
- **工单加列**：create 落 `created_by_user_id`、create/update 接受 `category_id`、跨租户 category 校验 404
- **迁移**：`tests/unit/` 单元测试（importlib + MigrationContext，最小父表 fixture 验证 DDL upgrade/downgrade）
- **① 成本**：labor/additional 求和、量化各小计再合、by_asset 归属、运行中计时器计 0、日期落窗边界、过滤
- **② 多维**：by_asset/user/category 计数 + None 桶
- **③ ABC**：排序/累计占比/分级边界（恰 80%/95%）、空消耗→空 list、summary 计数
- **④ 资产成本**：归属求和、acquisition_cost 空→ratio None、车队汇总
- **⑤ 请求**：by_status/priority 全枚举、resolved/received/converted、cycle 均值
- **⑥ 人员**：created/completed/assigned/labor_hours/labor_cost、仅列有活动用户
- **⑦ 趋势**：day/week 分桶、空桶连续、非法 granularity 400、落桶边界
- **跨租户**：各新分析端点 A/B 公司数据不串
- 纯函数（ABC 分级、分桶、成本归属）独立单测

全量回归 + `ruff check app/` + `mypy app/` 每任务绿后提交。

## 6. 任务切分（供 plan 细化）

1. **WorkOrderCategory**：model + 迁移片段预留 + service + router + 权限 + 注册 + 测试
2. **工单加列**：category_id + created_by_user_id model + create/update 接线 + schema 暴露 + 跨租户校验 + 测试
3. **成本聚合公共纯函数 + ① /costs 扩展**：`maintenance_cost_by_asset` 公共函数 + labor/additional/total + 测试
4. **② /work-orders 多维分布**：by_asset/user/category + 测试
5. **③ /inventory ABC**：abc_classification + summary + 测试
6. **④ /asset-reliability 成本**：复用公共函数 + ratio + 车队汇总 + 测试
7. **⑤ /requests 端点**：schema + service + router + CSV + 测试
8. **⑥ /personnel 端点**：schema + service + router + CSV + 测试
9. **⑦ /trends 端点**：分桶纯函数 + schema + service + router + CSV + 测试
10. **统一迁移**：3 表/列合并迁移 + unit 测试 + up/down/up 重放 + 零漂移验证（末位，复刻 2A T6）

> 任务 1–2 须在 3–9 之前（提供 category/created_by 字段）；3 在 4/6 之前（公共纯函数）；10 末位。

## 7. 不在本轮

- 估时 vs 实际工时：依赖 2B 的 `estimatedDuration` 字段，留 2B
- 工单状态分布的完整时点历史重建（事件回放）：留后续，trends 以吞吐序列替代
- 任何前端：分析仪表盘前端属 FE-6，本轮纯后端
