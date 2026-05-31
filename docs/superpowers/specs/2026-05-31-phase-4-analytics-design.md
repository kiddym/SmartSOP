# Phase 4 分析与报表（Analytics & Reports）设计 spec

- **日期**: 2026-05-31
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) Phase 4
- **前置**: Phase 0–3C 已完成（WorkOrder/Asset/Location/Request/PM/Meter/Part/Inventory/PurchaseOrder/Vendor/Customer），全量 945 pytest，alembic 单 head `phase3c_purchase_order`

---

## 1. 目标与范围

在已有 Phase 0–3C 数据之上提供**只读分析 API**：4 组运营仪表盘 KPI + 每盘 CSV 导出。

### 已确认决策

| 决策项 | 选择 |
|--------|------|
| 交付面 | **仅后端分析 API**（前端 Vue 仪表盘另起一期） |
| 数据范围 | **纯只读，零写路径，零新表，零迁移**（请求时实时聚合，方案 A） |
| 人工成本 | **延后**（当前无工时模型；属维护域写路径功能，应另起小阶段，不混入分析期） |
| 仪表盘 | **路线图点名的 4 组**：工单合规吞吐、成本、资产可靠性、库存（YAGNI，不纳入 PM/Request/Meter） |
| 报表导出 | **CSV**（每盘主分组明细表，流式输出；不做 PDF） |
| MTBF/MTTR | **计入全部停机记录**（现停机无故障分类），语义注明"基于窗内全部停机区间，未区分故障/计划" |

### 非目标（本期不做）

- 前端图表/仪表盘 UI
- 人工/工时成本、技师产能
- PDF 报表、物化/缓存事实表、预测/ML
- 故障分类、SLA 阈值表、库存持有成本等需新增字段/表的指标

---

## 2. 架构（方案 A：请求时实时聚合）

与 0–3C 同构分层，但**无 model、无 migration**。`analytics_service` 在请求时对既有表跑 SQLAlchemy 聚合查询（`func.count/sum/avg` + `group_by`），租户隔离沿用既有中间件（请求内 `company_id` 自动作用域，无需 bypass）。零侵入既有模块（只读引用其 ORM 模型）。

### 文件布局

```
app/services/analytics/                ← 新建包（每盘一个聚焦模块，避免单文件过大）
    __init__.py
    _common.py                         ← 日期窗口解析、窗口小时数、CSV 行构造等共享 helper
    work_order_analytics.py
    cost_analytics.py
    asset_reliability_analytics.py
    inventory_analytics.py
app/schemas/analytics.py               ← 4 盘 Pydantic 响应模型
app/routers/analytics.py               ← 4 JSON 端点 + 4 CSV 导出端点
app/permissions.py                     ← 追加 analytics.view（精确插入）
app/main.py                            ← 挂载 analytics.router（精确插入）
tests/unit/test_analytics_work_order.py
tests/unit/test_analytics_cost.py
tests/unit/test_analytics_asset_reliability.py
tests/unit/test_analytics_inventory.py
tests/test_analytics_api.py
```

### 性能注记

早期 SaaS 数据量小，实时聚合足够。海量租户/超长窗下聚合变慢时，再加短 TTL 缓存或物化事实表——本期不做（无证据前不引入缓存失效复杂度，YAGNI）。

---

## 3. 端点契约

前缀 `/api/v1/analytics`，全部 `GET`，均需权限 `analytics.view`。

| 端点 | 返回 |
|---|---|
| `GET /analytics/work-orders` | 工单合规吞吐 KPI（JSON） |
| `GET /analytics/costs` | 成本 KPI（JSON） |
| `GET /analytics/asset-reliability` | 资产可靠性 KPI（JSON） |
| `GET /analytics/inventory` | 库存 KPI（JSON） |
| `GET /analytics/{dashboard}/export` | 同盘主分组明细 CSV（`StreamingResponse`，`text/csv`） |

### 公共查询参数

- `date_from` / `date_to`（可选，`date` 型）。两者都省略时默认**最近 90 天**（含端点）。各盘取其语义时间键：WO 用 `created_at`；成本用 `PartConsumption.consumed_at` 与 PO `resolved_at`；停机用区间与窗口的重叠裁剪；库存为当前快照，库存量/价值不受时间窗影响（仅其窗内消耗子项受影响）。
- 维度过滤（按盘相关，缺省不过滤）：`location_id`、`asset_id`、`category_id`。
- 导出端点复用同一套参数；`{dashboard}` ∈ `work-orders|costs|asset-reliability|inventory`，非法值 → 404 `ANALYTICS_DASHBOARD_NOT_FOUND`。

### CSV 内容

每盘导出其**主分组明细表**（每组一行，见第 4 节各盘 CSV 定义），而非原始流水，保证有界、可读。表头行 + 数据行；金额/小时数/百分比按通用约定量化。

---

## 4. 指标口径（精确公式）

### 全盘通用约定

- 仅统计 `is_active=True`（排除软删，对无软删的 append-only 表如 PartConsumption/Activity 不适用该过滤）。
- 租户作用域由中间件自动加 `company_id`。
- 金额用 `Numeric` 量化 4 位；百分比、小时数四舍五入 2 位。
- 除零：计数率返回 `0`；无样本的均值返回 `null`。
- 时间窗 `[date_from, date_to]` 含端点；DATETIME6 按 naive UTC 比较（`date_to` 视为当日 23:59:59.999999 或次日零点开区间，实现时统一为 `< date_to + 1 day`）。
- 分组明细数组（`*_by_*`、`top_*`、`*_items`）返回**全部分组并排序**，本期不做 top-N 截断（无静默截断；分组数天然有界于备件/资产/供应商/状态数）。命名含 "top" 仅表排序方向，不表数量上限。

### 盘 1 · 工单合规吞吐 `/analytics/work-orders`

时间键 `WorkOrder.created_at`；过滤 `location_id`、`asset_id`。

- `total` = 窗内创建的 WO 数
- `by_status` = 按 status 分组计数（OPEN/IN_PROGRESS/ON_HOLD/COMPLETE/CANCELED，缺省补 0）
- `by_priority` = 按 priority 分组计数（NONE/LOW/MEDIUM/HIGH，缺省补 0）
- `completed` = status==COMPLETE 数
- `completion_rate` = completed / total（total==0 → 0）
- `overdue` = 窗内创建、`due_date < today` 且 status ∉ {COMPLETE,CANCELED} 的数
- `avg_cycle_time_hours` = AVG(`completed_at` − `created_at`)，仅 status==COMPLETE 且 `completed_at` 非空；无样本 → null
- `avg_response_time_hours` = AVG(首条 `to_status==IN_PROGRESS` 的 activity `created_at` − WO `created_at`)，取自 `tb_work_order_activity`（time-in-state 代表指标）；无样本 → null
- **CSV**：每 status 一行 `{status, count, pct}`

### 盘 2 · 成本 `/analytics/costs`（无人工）

- `parts_consumption_cost` = Σ(`quantity` × `unit_cost`)，`PartConsumption.consumed_at` 在窗内
- `consumption_by_part` = 按 part 分组 `{part_id, custom_id, name, qty, cost}`，按 cost 降序
- `consumption_by_asset` = 经 `PartConsumption → WorkOrder` 连接，按 `WorkOrder.asset_id` 分组的物料花费；`location_id`/`asset_id` 过滤在此生效
- `po_spend_approved` = Σ(line `quantity` × `unit_cost`)，仅 PO status==APPROVED 且 `resolved_at` 在窗内（真实承诺采购额）
- `po_spend_by_vendor` = 按 `vendor_id` 分组
- 说明：消耗成本与采购额是**两类不同口径，不相加**
- **CSV**：`consumption_by_part` 每备件一行

### 盘 3 · 资产可靠性 `/analytics/asset-reliability`

对每个活跃资产，取 `tb_asset_downtime` 中与窗口 `[date_from, date_to]` **有重叠**的停机区间，并裁剪到窗内（`ended_at` 为空＝进行中，裁到 `date_to`）；过滤 `location_id`、`category_id`、`asset_id`。

- `window_hours` = (date_to − date_from) 折算小时
- 每资产：`total_downtime_hours` = Σ裁剪区间时长；`downtime_count` = 与窗重叠的区间数
- `availability_pct` = (window_hours − total_downtime_hours) / window_hours × 100，clamp[0,100]
- `mttr_hours` = AVG(区间时长)，仅已结束（`ended_at` 非空）区间；无 → null
- `mtbf_hours` = (window_hours − total_downtime_hours) / downtime_count；downtime_count==0 → null
- 语义注："基于窗内全部停机区间，未区分故障/计划"
- 车队级汇总：平均可用率、总停机小时、整体 MTTR、整体 MTBF
- **CSV**：每资产一行 `{asset_custom_id, asset_name, availability_pct, downtime_count, total_downtime_hours, mttr_hours, mtbf_hours}`

### 盘 4 · 库存 `/analytics/inventory`（当前快照）

库存量/价值为当前快照，不受时间窗影响；仅 `top_consumed_parts` 子项用窗口。过滤 `category_id`。

- `total_inventory_value` = Σ(`quantity` × `cost`)，仅 `non_stock=False` 的活跃备件
- `inventory_value_by_category` = 按 `category_id` 分组
- `low_stock_count` / `low_stock_items` = `non_stock=False` 且 `quantity < min_quantity`，列 `{part_id, custom_id, name, quantity, min_quantity, shortfall}`（shortfall = min_quantity − quantity）
- `top_consumed_parts`（窗内）= 按消耗量降序的备件 `{part_id, custom_id, name, qty}`
- **CSV**：每备件一行 `{custom_id, name, category, quantity, min_quantity, cost, value, is_low_stock}`

---

## 5. RBAC

- 新增单一权限码 **`analytics.view`**，守护全部 8 个端点（4 JSON + 4 CSV）。
- `permissions.py`：新增 `ANALYTICS_VIEW = "analytics.view"` 与组 `_ANALYTICS = [ANALYTICS_VIEW]`，追加到 `ALL_PERMISSIONS` 末尾（精确插入，不丢既有组、无重复）。
- 角色默认：
  - **admin / super_admin**：自动全含（`list(ALL_PERMISSIONS)`）。
  - **viewer**：经既有 `.endswith(".view")` 自动获得（只读角色看分析合理）。
  - **technician**：**不授予**（分析面向管理者，非其职责）。
  - **requester**：不变。
- 跨租户：所有聚合查询已被中间件按 `company_id` 作用域，天然无串户；维度过滤 id **不做跨租户校验**（沿用 3B/3C 模式，外租户 id 自然匹配不到任何行 → 空结果）。

---

## 6. 测试策略

### 单测（每盘一个，造数据断言精确口径）

`tests/unit/test_analytics_work_order.py` / `_cost.py` / `_asset_reliability.py` / `_inventory.py`，覆盖边界：

- 空数据 → 计数率 `0`、均值 `null`；除零安全。
- 停机**窗口裁剪**：进行中区间（`ended_at` 空）裁到 `date_to`；跨窗区间正确裁剪；`downtime_count==0` → MTBF `null`；`availability_pct` clamp。
- 库存价值排除 `non_stock=True` 与软删；`is_low_stock` 边界（`quantity < min_quantity`，等于不算低）。
- WO `avg_cycle_time`/`avg_response_time` 仅取有效样本；`overdue` 终态排除。
- PO 花费仅计 APPROVED 且 `resolved_at` 在窗。

### API 测（`tests/test_analytics_api.py`）

- 鉴权：无 `analytics.view` → 403。
- RBAC：viewer 200、technician 403、admin 200。
- **跨租户隔离**：造两公司数据，断言各自只见本租户数字、无泄漏。
- CSV：`content-type` 为 `text/csv`、含表头行、行数与分组一致。
- 时间窗过滤生效；省略参数时默认 90 天窗生效；非法 `{dashboard}` 导出 → 404。

### 收尾

- 全量 pytest（既有 945 + 新增）0 failed。
- ruff 干净；clean-room 无 "Atlas"。
- **无新迁移** → alembic 仍单 head `phase3c_purchase_order`（本期零新表）。

---

## 7. 净室重写合规护栏（不可妥协）

- 绝不复制 Atlas 源码/DDL/文案/图标；Atlas 仅作功能参考。
- 产品中不出现 "Atlas" 字样。
- 全新原创代码，依据领域理解编写。

---

## 8. 完成标准（Definition of Done）

- `/api/v1/analytics` 4 个 JSON 仪表盘端点 + 4 个 CSV 导出端点工作，全部受 `analytics.view` 守护。
- 4 盘 KPI 口径与本 spec 第 4 节一致；时间窗 + 维度过滤生效；默认 90 天窗。
- 跨租户隔离正确（聚合只见本租户）。
- CSV 流式输出、表头正确、`text/csv`。
- RBAC：admin/super_admin/viewer 可见，technician 不可见。
- 全量 pytest 0 failed；ruff 干净；无 "Atlas"；alembic 仍单 head `phase3c_purchase_order`（零新表零迁移）。
