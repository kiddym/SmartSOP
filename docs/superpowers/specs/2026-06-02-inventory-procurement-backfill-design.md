# 设计：库存采购补全 ④（Atlas parity backfill · group 4）

- 日期：2026-06-02
- 范围：后端净室原创。补齐库存/采购缺失关联（6 张 M:N）+ PurchaseOrderCategory + PurchaseOrder 扩展元数据字段
- 分支：feat/inventory-backfill（独立 worktree，基于 main 104c3a2；与 analytics/asset 补全并行设计）
- 基线约束：净室原创（仅参照通用 CMMS 库存采购功能行为，绝不复制 Atlas 代码/DDL/文案/命名；产品不出现 "Atlas"；GPL 合规）；仅中文、不做 i18n；后端解释器统一 `backend/.venv/bin/python`；门禁 ruff 0.15 + mypy 1.20；pytest 用 SQLite `Base.metadata.create_all`

## 1. 背景与目标

现状（核实于本 worktree）：

- **已存在**（非 gap）：`PartAssignee`(Part↔user) / `PartTeam`(Part↔team) / `PartAsset`(Part↔asset)；`VendorPart`(Vendor↔part)；`CustomerPart`(Customer↔part)；`PurchaseOrder`（vendor_id/status/notes/resolution + `PurchaseOrderLine` + `PurchaseOrderActivity`）；`PartCategory`。
- **M:N 管理模式**（既定）：关联**不走独立 set 端点**，而是 ID 列表内嵌实体 schema —— Create 有 `*_ids: list[str] = []`、Update 有 `*_ids: list[str] | None = None`（None=不动）、Read 暴露 `*_ids`；service 提供 `xxx_ids(db, id)` reader，create 时 add join 行，update 时若列表非 None 则 `delete` 全部再 re-add（全量替换）；list 经 join 子查询过滤。

**确缺（本轮全补 A+B+C）**：

- **A. 6 张关联表**：Part↔location、Part↔PM、Vendor↔asset、Vendor↔location、Customer↔asset、Customer↔location（Part 当前**完全无 location 关联**）。
- **B. PurchaseOrderCategory**：新分类表 + CRUD + `PurchaseOrder.category_id`。
- **C. PurchaseOrder 扩展元数据字段**：shipping/terms/预计交期。

**不补（留后续）**：Vendor 自定义字段（Phase6）；PO 级货币字段（additional_cost/tax/discount，见 §4 理由）。

## 2. A — 6 张关联表

每张关联**复刻现有 M:N 模式**，逐项含：join model + 实体 Create/Update/Read 加 `*_ids` 字段 + service（`xxx_ids` reader + create/update 同步）+ 可选 list 过滤 + 迁移片段。

| 关联 | join 表 | join 列（均挂 UUID/Timestamp/Tenant Mixin） | 暴露在 |
|---|---|---|---|
| Part↔location | `tb_part_location` | part_id FK→tb_part CASCADE、location_id FK→tb_location CASCADE，均 index | `Part.location_ids` |
| Part↔PM | `tb_part_pm` | part_id FK→tb_part CASCADE、pm_id FK→tb_preventive_maintenance CASCADE | `Part.pm_ids`（库存侧暴露，不改 PM 模块 schema/service） |
| Vendor↔asset | `tb_vendor_asset` | vendor_id FK→tb_vendor CASCADE、asset_id FK→tb_asset CASCADE | `Vendor.asset_ids` |
| Vendor↔location | `tb_vendor_location` | vendor_id FK→tb_vendor CASCADE、location_id FK→tb_location CASCADE | `Vendor.location_ids` |
| Customer↔asset | `tb_customer_asset` | customer_id FK→tb_customer CASCADE、asset_id FK→tb_asset CASCADE | `Customer.asset_ids` |
| Customer↔location | `tb_customer_location` | customer_id FK→tb_customer CASCADE、location_id FK→tb_location CASCADE | `Customer.location_ids` |

> 唯一约束：每张 join 表加 `UniqueConstraint(<owner>_id, <target>_id, name=uq_<table>)`（防重复关联），与现有 join 表（如 uq_work_order_assignee）一致。
> 实际表名/FK 目标以本 worktree 内模型为准：`tb_location`（位置）、`tb_preventive_maintenance`（PM）——实现期核对确切 `__tablename__`，如不同按实调整。

### 2.1 跨租户校验（改进点，守红线）

现有同步直接 `db.add(join(...))` 不校验目标 id 归属租户。**新关联在 create/update 同步时校验每个目标 id 属当前 company**（`db.get(Model, id)` 检 `company_id` 匹配且 active，否则 `not_found("<X>_NOT_FOUND")`）。跨租户对抗必测（A 公司不可把 B 的 location/asset/pm 关联进来）。

> 不回改既有 PartAsset/VendorPart 等旧关联的校验（避免越界改动既有测试）；仅新关联落实校验。

### 2.2 list 过滤（可选，低优先）

各实体 list 端点可加按新关联过滤的 query 参数（如 `parts?location_id=`），与现有 `parts?asset_id=` 对称。本轮**仅在低成本时附带**；不阻塞核心关联交付。

## 3. B — PurchaseOrderCategory

- 表 `tb_purchase_order_category`，复刻 TimeCategory/WorkOrderCategory：`name` String(300) + `description` Text + UUID/Timestamp/SoftDelete/Tenant Mixin；`UniqueConstraint(company_id, name, name="uq_purchase_order_category_company_name")`。
- CRUD `/api/v1/purchase-order-categories`：view→list/get、manage→create/patch/delete(204)；重名→409 `PURCHASE_ORDER_CATEGORY_DUPLICATE`；软删/不存在→404 `PURCHASE_ORDER_CATEGORY_NOT_FOUND`。
- 权限新增 `PURCHASE_ORDER_CATEGORY_VIEW="purchase_order_category.view"` / `PURCHASE_ORDER_CATEGORY_MANAGE="purchase_order_category.manage"`；加入 `ALL_PERMISSIONS` 新分组；technician 仅 view。
- `PurchaseOrder.category_id` FK→`tb_purchase_order_category.id` `ondelete=SET NULL`、nullable、index；PO Create/Update 接受 `category_id`（跨租户校验→404）；PO Read 暴露 `category_id`。

## 4. C — PurchaseOrder 扩展元数据字段

`PurchaseOrder` 加（均非货币、可空/有默认）：

- `shipping_address` String(500) server_default=""
- `shipping_method` String(120) server_default=""
- `terms_of_payment` String(200) server_default=""
- `expected_delivery_date` Date nullable
- `category_id`（见 §3）

PO Create/Update 接受、Read 暴露上述字段。

**刻意排除 PO 级货币字段**（additional_cost/tax/discount）：它们会改变并行的分析补全（group ⑤）所依赖的 `po_spend = Σ(line.quantity × line.unit_cost)` 口径，且涉及分析 agent 占用的 `cost_analytics.py`。货币扩展留后续，避免跨轮语义冲突与文件互踩。

## 5. 横切与并行协调

### 5.1 共享注册文件协调（重要）

本轮会修改 `app/permissions.py`、`app/models/__init__.py`、`app/main.py`（注册新模型/路由/权限）——这三个文件**也被 analytics（group ⑤）与 asset（group ③）轮触及**。

- 这些是"追加型"修改（各自加自己的行），git 多数能自动合并；但为稳妥：**④ 应在 analytics + asset 合入 main 后，从更新后的 main 重新分叉再执行**（④ 是最后一组、天然靠后），从根上消除注册文件三方并发。
- 若坚持并行执行，合并时按 backfill-merge-runbook 处理这三个文件的多方修改（不相交行自动合，相邻行人工核对）。

### 5.2 迁移

统一一个迁移（6 join 表 + tb_purchase_order_category + PurchaseOrder 5 列），末位任务。开发期 `down_revision="workorder_labor_cost"`；合入 main 时按 backfill-merge-runbook rebase 指向当时 main 的迁移 head，保持线性单 head。MySQL 全链重放受既有 initial_schema 问题阻塞（无关），以迁移 unit 测试验 DDL，全链待生产手验。

### 5.3 多租户与权限

- 所有 join 表挂 `TenantMixin`；新关联写入校验同租户（§2.1）。
- 权限：B 新增 `purchase_order_category.*`；A 复用各实体既有 edit 权限（part/vendor/customer 的 create/edit）。

## 6. 测试策略

SQLite in-memory（conftest）：

- **每张关联**：create 带 `*_ids` 落 join 行、Read 回显、update 全量替换（含清空）、list 过滤（若实现）、跨租户校验 404、唯一约束防重复。
- **PurchaseOrderCategory**：CRUD + 软删 + 重名 409 + 权限矩阵 + 跨租户对抗。
- **PO 加列**：create/update 接受并回显 5 字段；category_id 跨租户→404。
- **迁移**：`tests/unit/` 单测（importlib + MigrationContext，最小父表 fixture 验全部新表/列 up/down）。
- **跨租户**：A 公司关联/分类不泄漏给 B。
- 既有库存采购测试全绿（不破坏 PartAsset/VendorPart 等既有关联行为）。

全量回归 + `ruff check app/` + `mypy app/` 每任务绿后提交。

## 7. 任务切分（供 plan 细化，7 任务）

1. **Part↔location**：PartLocation 模型 + Part schema location_ids + service 同步+校验 + 测试。
2. **Part↔PM**：PartPM 模型 + Part schema pm_ids + service + 测试。
3. **Vendor↔asset + Vendor↔location**：VendorAsset/VendorLocation + Vendor schema asset_ids/location_ids + service + 测试。
4. **Customer↔asset + Customer↔location**：CustomerAsset/CustomerLocation + Customer schema asset_ids/location_ids + service + 测试。
5. **PurchaseOrderCategory**：模型 + CRUD（service/router/schema）+ 权限 + 注册 + PO.category_id 接线 + 测试。
6. **PO 扩展字段**：4 元数据列 + PO schema + service 接线 + 测试。
7. **统一迁移**：6 join 表 + 分类表 + PO 5 列 + unit 测试 + 零漂移（down_revision 见 §5.2）。

> T1–T6 各自独立（不同文件/不同 join 表），可任意顺序；T7 末位。T5/T6 同改 `purchase_order.py` 模型与 PO schema，注意先后（建议 T5 在 T6 前，category_id 先落）。

## 8. 不在本轮

- Vendor 自定义字段（Phase6）。
- PO 级货币字段（additional_cost/tax/discount，§4）。
- 既有旧关联（PartAsset/VendorPart/CustomerPart）的回溯校验加固（仅新关联落校验）。
