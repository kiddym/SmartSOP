# Phase 3A 备件 · 库存 · 消耗 · 套件 设计 spec

> Phase 3（库存与采购）拆为三个独立周期（3A 备件/库存/消耗/套件 · 3B 供应商/客户/成本分类 · 3C 采购单+审批→入库），各自走完整 spec→plan→implement。本文是 **3A**，承接 [2C Meter](2026-05-31-phase-2c-meter-design.md)，依据 [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) 与 [功能对照矩阵](2026-05-30-feature-parity-matrix.md) IN1。

- **日期**: 2026-05-31
- **状态**: 已批准（brainstorming 协作产出）

## 1. 目标与范围

实现备件库存的核心闭环：备件 CRUD + 库存量、**按工单消耗扣减**（不足报错 + 成本快照台账）、低库存标识、多备件套件分组。是 3B（供应商/客户）、3C（采购单）的基础。区别于触发源→生成工单的模块，本期是库存领域 + 与工单执行的消耗集成。

### 纳入范围
- `Part` 备件：cost / quantity / min_quantity / unit / barcode / non_stock；挂可选分类；M:N 关联 assignees(users) / teams / assets。
- `PartCategory` 备件分类（镜像既有 AssetCategory 模式）。
- `PartConsumption` 消耗台账：挂工单消耗，扣库存、不足报错、定格单价快照（append-only 审计）。
- `MultiParts` 多备件套件：纯分组（无自身库存、无消耗行为）。
- 低库存标识 `is_low_stock`（计算字段）+ 列表过滤；mini 下拉。
- RBAC：part.{view,create,edit,delete} + part.consume + part_category.{view,manage}。

### 不纳入范围（明确延后）
- **通知**：低库存告警的实际通知推到 Phase 5（系统尚无通知子系统）；3A 只暴露 `is_low_stock` 计算字段 + 列表过滤（同 2B PM / 2C Meter 的通知延后处理）。
- 供应商/客户关联（Vendor/Customer M:N）→ 3B；采购入库（PurchaseOrder→逐行入库）→ 3C。
- 工单备件成本**汇总**（工单总成本 = 人工 + 备件 + 附加）、人工/工时建模 → Phase 4 分析期。本期仅在 PartConsumption 存单价快照。
- 备件自定义字段 → Phase 6（复用 CustomFieldDef）。
- 消耗的冲销/更正（append-only，审计完整性；更正属后期）。

### 沿用既有不变约束
clean-room、零 GPL 风险（输出不出现 "Atlas" 字样、不抄源码/DDL/文案）、多租户隔离（中间件 + ORM 事件，读写在请求内无需 bypass）、`tb_` 前缀、UUID 字符串主键、软删 `is_active`/`deleted_at`、每租户 Sequence 编号、money 用 `Numeric` 裸金额（Currency 实体属 Phase 0/6，尚未建）。

## 2. 数据模型

共 **8 张表**（均 `tb_` 前缀、UUID 主键、TenantMixin 盖租户章）。

### ① `tb_part` 备件（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| custom_id | String(20) | 每租户 Sequence，前缀 `PRT`（PRT000001）|
| name | String(300) | 备件名 |
| description | Text, default "", server_default "" | |
| cost | Numeric(18,4), nullable=False, default 0, server_default "0" | 单价（裸金额，暂无 Currency 实体）|
| quantity | Numeric(18,4), nullable=False, default 0, server_default "0" | 当前库存量 |
| min_quantity | Numeric(18,4), nullable=False, default 0, server_default "0" | 最小库存阈值 |
| unit | String(50), default "", server_default "" | 单位（pcs/L…）|
| barcode | String(120), nullable | 条码 |
| non_stock | Boolean, nullable=False, default False, server_default "0" | 不计库存的备件 |
| category_id | String(36) FK tb_part_category SET NULL, nullable, index | 分类 |

- `is_low_stock`：**非数据库列**，模型 `@property`：`return (not self.non_stock) and (self.quantity < self.min_quantity)`。schema Read 暴露；列表过滤 `?low_stock=true` 由 service 在查询层用 `non_stock == False AND quantity < min_quantity` 表达式实现。

### ② `tb_part_category` 备件分类（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| name | String(300), nullable=False | |
| description | Text, default "", server_default "" | |

镜像既有 AssetCategory 模式（每租户、软删、name/description）。

### ③ `tb_part_consumption` 消耗台账（仅 Timestamp + Tenant，**append-only 不软删**，审计性质）
| 字段 | 类型 | 说明 |
|---|---|---|
| part_id | String(36) FK tb_part RESTRICT, index | |
| work_order_id | String(36) FK tb_work_order CASCADE, index | 消耗所挂工单 |
| quantity | Numeric(18,4), nullable=False | 本次消耗量 |
| unit_cost | Numeric(18,4), nullable=False | 消耗时单价快照（取自 part.cost，定格）|
| consumed_by_user_id | String(36), nullable | 消耗人 |
| consumed_at | DATETIME6, nullable=False, default utcnow | 消耗时刻 |

### ④ `tb_multi_part` 套件（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| custom_id | String(20) | 每租户 Sequence，前缀 `KIT`（KIT000001）|
| name | String(300), nullable=False | |
| description | Text, default "", server_default "" | |

纯分组：无自身库存、无消耗行为（消耗仍是逐 part 进行）。

### ⑤ `tb_multi_part_item` 套件成员（+ Tenant，唯一约束 uq_multi_part_item）
multi_part_id (FK tb_multi_part CASCADE, index) + part_id (FK tb_part CASCADE, index)；`UniqueConstraint("multi_part_id", "part_id", name="uq_multi_part_item")`。

### ⑥ `tb_part_assignee` / ⑦ `tb_part_team` / ⑧ `tb_part_asset`（+ Tenant，各带唯一约束）
备件的 M:N 关联，同 2C meter_trigger_assignee/team 模式：
- `tb_part_assignee`：part_id (FK tb_part CASCADE) + user_id (FK tb_user CASCADE)，`uq_part_assignee`。
- `tb_part_team`：part_id (FK tb_part CASCADE) + team_id (FK tb_team CASCADE)，`uq_part_team`。
- `tb_part_asset`：part_id (FK tb_part CASCADE) + asset_id (FK tb_asset CASCADE)，`uq_part_asset`。

### 新增 Sequence
新增 Sequence kind `"part"`（Part 用 `PRT`）、`"multi_part"`（MultiParts 用 `KIT`）；consumption/category 无 custom_id。复用既有 kind 机制，无需改 sequence_service。

## 3. 消耗算法与事务

挂工单消耗（Atlas 行为的净室实现）。

### `consume_part(db, work_order, part, quantity, company_id, actor_user_id) -> PartConsumption`
（在 `app/services/part_consumption_service.py`）
```
1. 校验 quantity > 0，否则 bad_request("PART_BAD_QUANTITY")
2. 若 part.non_stock:               # 不计库存
       不校验库存、不扣减 quantity
   否则（计库存）:
       若 quantity > part.quantity → bad_request("PART_INSUFFICIENT_STOCK")
       part.quantity = part.quantity - quantity
3. 建 PartConsumption(
       part_id=part.id, work_order_id=work_order.id, quantity=quantity,
       unit_cost=part.cost,                      # 定格当时单价快照
       consumed_by_user_id=actor_user_id, company_id=company_id)
       （consumed_at 默认 utcnow）
4. db.commit(); db.refresh(consumption); return consumption
```

### 事务与语义
- 请求内单次 commit。中间件已置租户上下文，无需 bypass；不存在 2C Meter 那种 `create_work_order` 中途 commit 的 partial-commit 风险（本期 consume 不调用内部会 commit 的工单服务）。
- **append-only**：消耗台账不支持改/删（审计完整性，同 MeterReading）；冲销/更正属后期。
- `is_low_stock` 仅为计算属性，消耗除扣减库存外无其他副作用；低库存通知延后 Phase 5。
- 手动 PATCH 改 `quantity` 不写台账（设计如此，与"数量可直接编辑"一致）；台账只记录 WO 驱动的消耗。
- `non_stock` 备件：消耗永不报"库存不足"、不改 quantity，但仍写台账（记录用量与成本快照，供后期报表）。

## 4. Service 分层与 API

### Service 拆分
- `app/services/part_service.py`：Part CRUD（Sequence `PRT`、quantity 可经 update 直接改）、`list_parts(db, *, category_id?, asset_id?, low_stock?)`、get/delete（软删）；备件 M:N 关联读写（assignee/team/asset，全量替换 + dedup，同 2C）。
- `app/services/part_category_service.py`：PartCategory CRUD（软删）。
- `app/services/multi_part_service.py`：MultiParts CRUD（Sequence `KIT`、part_ids 全量替换）。
- `app/services/part_consumption_service.py`：`consume_part`（见 §3）、`list_consumptions(db, work_order_id)`。

### API（挂 `/api/v1`）
| 方法 路径 | 权限 |
|---|---|
| GET `/parts`（filter category_id / asset_id / low_stock）· GET `/parts/mini`（精简下拉，镜像既有 assets/locations 的 `/mini` 端点 + PartMini schema）| part.view |
| POST `/parts` | part.create |
| GET `/parts/{id}` | part.view |
| PATCH `/parts/{id}`（含改 quantity / min_quantity / cost 等）| part.edit |
| DELETE `/parts/{id}` | part.delete |
| GET `/part-categories` · POST `/part-categories` | part_category.view / manage |
| GET `/part-categories/{id}` · PATCH · DELETE | view / manage / manage |
| GET `/multi-parts` · POST `/multi-parts` | part.view / part.create |
| GET `/multi-parts/{id}` · PATCH（part_ids 全量替换）· DELETE | part.view / part.edit / part.delete |
| POST `/work-orders/{wo_id}/part-consumptions` `{part_id, quantity}` → 消耗 | part.consume |
| GET `/work-orders/{wo_id}/part-consumptions` | part.view |

- 消耗端点放**新 router `app/routers/part_consumptions.py`**（路径嵌在 work-orders 下），不改既有 `work_orders.py`，保持低耦合。校验 WO 与 part 均 `company_id == current_user.company_id` → 404（WO 经 `work_order_service.get_work_order` 或直接 `db.get` + 租户校验）。
- 所有端点强校验实体租户归属 → 404（part / category / multi_part / work_order）。
- 无独立"立即建单/手动扣库存以外"的端点（YAGNI）。

### Schemas `app/schemas/part.py`
- `PartCreate` / `PartUpdate`（全可选）/ `PartRead`（含计算 `is_low_stock`、assignee_ids/team_ids/asset_ids 由 router 在 model_validate 后填充，同 2C `_read_trigger`）/ `PartMini`（id/name/custom_id，下拉用）。
- `PartCategoryCreate` / `PartCategoryUpdate` / `PartCategoryRead`。
- `PartConsumptionCreate`（part_id 必填、quantity 必填）/ `PartConsumptionRead`（含 unit_cost + 计算 `total_cost = quantity * unit_cost`）。
- `MultiPartCreate` / `MultiPartUpdate`（part_ids 可选）/ `MultiPartRead`（含 part_ids）。

## 5. RBAC 权限

新增权限码，分组（同 2B/2C 模式）：
```python
PART_VIEW   = "part.view"
PART_CREATE = "part.create"
PART_EDIT   = "part.edit"
PART_DELETE = "part.delete"
PART_CONSUME = "part.consume"
PART_CATEGORY_VIEW   = "part_category.view"     # 镜像既有 asset_category.{view,manage}
PART_CATEGORY_MANAGE = "part_category.manage"

_PART = [PART_VIEW, PART_CREATE, PART_EDIT, PART_DELETE, PART_CONSUME]
_PART_CATEGORY = [PART_CATEGORY_VIEW, PART_CATEGORY_MANAGE]
ALL_PERMISSIONS = ... + _PART + _PART_CATEGORY
```

角色默认：
- super_admin / admin：自动含全部。
- **technician**：`part.view` + `part.consume` + `part_category.view`（看库存、按工单消耗；不能增删改备件/分类）。
- viewer：自动经 `.endswith(".view")` 含 `part.view` + `part_category.view`。
- requester：不变。

契约测试 `tests/test_permissions_phase3a.py`（照 2C 惯例）：断言 7 码注册、admin/super_admin 全含、technician 三码（part.view/part.consume/part_category.view，且无 part.create/edit/delete）、viewer 两个 .view、requester 不变。

## 6. 迁移 · 接线 · 测试策略

**迁移** `backend/alembic/versions/20260531_0007_phase3a_part.py`（`revision="phase3a_part"`, `down_revision="phase2c_meter"`）：手写 `_ts/_soft/_company_fk` helper（同 2A/2B/2C），建 8 表 + 索引 + 唯一约束；FK：`part.category_id`→SET NULL、`part_consumption.part_id`→RESTRICT、`part_consumption.work_order_id`→CASCADE、套件/关联表→CASCADE、关联 user/team/asset→CASCADE。MySQL/SQLite 双方言，无分支。迁移测试在 SQLite 建父表骨架（tb_company / tb_work_order / tb_asset / tb_user / tb_team）后 upgrade→downgrade 往返。

**接线**：8 个模型注册进 `app/models/__init__.py`（import + `__all__`）；4 个 router 文件（`parts.py`、`part_categories.py`、`multi_parts.py`、`part_consumptions.py`）挂 `main.py`；Sequence 新增 kind `"part"`/`"multi_part"`（无需改 sequence_service）。

**测试策略**
- **单元**：`consume_part`（计库存扣减、库存不足报错、non_stock 不扣减但入台账、单价快照定格、quantity>0 校验）；Part CRUD（含直接改 quantity）；`is_low_stock` 计算（含 non_stock 永不低库存、临界相等不算低）；`list_parts` 过滤（category_id / asset_id / low_stock）；MultiParts items 全量替换 + dedup；PartCategory CRUD；跨租户。
- **API**：Part CRUD；PartCategory CRUD；MultiParts CRUD；经 WO POST 消耗返回台账（含 total_cost）、库存扣减可见；technician 能消耗（201）但不能建备件（403）；跨租户 404；low_stock 过滤。
- **契约**：`test_permissions_phase3a.py`。
- **全量回归**：0 failed，alembic 单 head `phase3a_part`。

## 7. 风险缓解

| 风险 | 缓解 |
|---|---|
| 浮点漂移影响库存/成本 | quantity/cost/unit_cost 用 `Numeric(18,4)`；单测覆盖临界值 |
| 消耗与库存不一致 | `consume_part` 请求内单次 commit；不调用内部 commit 的工单服务，无 partial-commit 风险（区别于 2C Meter 的 generate_from_trigger 遗留风险） |
| non_stock 语义混淆 | 明确：non_stock 不扣库存、不报不足，但仍入台账 |
| 单价随时间变动 | PartConsumption 定格 `unit_cost` 快照，历史成本不受后续改价影响 |
| 多租户 | 读写在请求内（中间件已置租户上下文，无需 bypass）；router 强校验各实体 `company_id == current_user.company_id` → 404 |
| 与工单耦合 | 消耗端点独立 `part_consumptions.py`，不改 `work_orders.py`；仅依赖 WO 存在 + 租户校验 |
| GPL/Atlas | clean-room，输出无 "Atlas" 字样，不抄源码 |
| 库存仅减不增 | 本期 quantity 可经 PATCH 直接编辑（入库/校正）；采购自动入库属 3C |

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含 3A 单测 + API 测 + 契约/迁移测）。
- `tb_part` / `tb_part_category` / `tb_part_consumption` / `tb_multi_part` / `tb_multi_part_item` / `tb_part_assignee` / `tb_part_team` / `tb_part_asset` 八表经迁移可 upgrade/downgrade。
- `/parts`、`/part-categories`、`/multi-parts`、`/work-orders/{id}/part-consumptions` 全套端点工作；经工单消耗扣库存并写成本快照台账；技师能消耗、不能管理备件；跨租户隔离 404。
- non_stock 与库存不足语义正确；`is_low_stock` 计算正确（含临界与 non_stock）；单价快照定格。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净，alembic 单 head `phase3a_part`。
