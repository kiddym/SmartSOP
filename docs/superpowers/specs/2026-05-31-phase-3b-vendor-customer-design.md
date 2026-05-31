# Phase 3B 供应商 · 客户 · 成本分类 设计 spec

> Phase 3（库存与采购）拆为三个独立周期（3A 备件/库存/消耗/套件 · **3B 供应商/客户/成本分类** · 3C 采购单+审批→入库），各自走完整 spec→plan→implement。本文是 **3B**，承接 [3A 备件/库存](2026-05-31-phase-3a-parts-inventory-design.md)，依据 [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) 与 [功能对照矩阵](2026-05-30-feature-parity-matrix.md) IN3。

- **日期**: 2026-05-31
- **状态**: 已批准（brainstorming 协作产出）

## 1. 目标与范围

实现库存域的主数据：供应商 (Vendor)、客户 (Customer)、成本分类 (CostCategory) 的 CRUD，以及 Vendor/Customer 与 Part 的 M:N 关联。承接 3A 备件库存，是 3C（采购单：PO→Vendor、PO 行→Part）的供应商基础，以及 Phase 4（工单附加成本用 CostCategory 分类）的分类基础。本期是纯主数据 + 与既有 Part 的关联，不含任何触发/生成/扣减行为。

### 纳入范围
- `Vendor` 供应商：name + vendor_type + rate + 联系字段(address/phone/email/website) + description；M:N → Part。
- `Customer` 客户：上述联系字段 + customer_type + rate + `billing_currency`（货币码裸字符串）；M:N → Part。
- `CostCategory` 成本分类：查找型分类（name/description），镜像既有 PartCategory 模式（每租户、软删、name 唯一）。
- Vendor/Customer 的 part_ids 由自身 create/update 全量替换管理；反查"某备件的供应商/客户"用列表过滤 `?part_id=` 表达。
- `/mini` 下拉端点（Vendor/Customer）。
- RBAC：`vendor.{view,create,edit,delete}`、`customer.{view,create,edit,delete}`、`cost_category.{view,manage}`。

### 不纳入范围（明确延后）
- **Vendor/Customer ↔ Asset/Location 的 M:N**：Atlas 中两者亦关联资产/位置，但其消费端（资产/位置详情页展示、分析）在前端或 Phase 4，本期只建 Part 关联；Asset/Location 关联等真正需要时再加迁移。
- **采购单 PurchaseOrder + 审批 + 逐行入库** → 3C（PO 引用 Vendor + PartQuantity 行引用 Part，审批后入库回写 Part.quantity）。
- **CostCategory 的消费端**（工单 AdditionalCost / 工时成本汇总 / 工单总成本）→ Phase 4 分析期。本期 CostCategory 仅是可被引用的查找 CRUD，无消费端。
- **完整账单地址块**（billing_name/billing_address/billing_email…）与 **Currency 实体**（1:1 billingCurrency）→ Phase 6 商业化。本期 Customer 仅一个 `billing_currency` 裸货币码字符串。
- **Vendor 自定义字段** → Phase 6（复用 SmartSOP 既有 CustomFieldDef，强于 Atlas 仅 Vendor 的 CustomField）。
- **不在 PartRead 上反向暴露 vendor_ids/customer_ids**：保持 3A parts router/schema/service 零改动；反查走 `GET /vendors?part_id=` / `GET /customers?part_id=`。

### 沿用既有不变约束
clean-room、零 GPL 风险（输出不出现 "Atlas" 字样、不抄源码/DDL/文案）、多租户隔离（中间件 + ORM 事件，读写在请求内无需 bypass）、`tb_` 前缀、UUID 字符串主键、软删 `is_active`/`deleted_at`、money 用 `Numeric` 裸金额、货币用裸码字符串（Currency 实体属 Phase 6，尚未建）。

## 2. 数据模型

共 **5 张表**（均 `tb_` 前缀、UUID 主键、TenantMixin 盖租户章）。Vendor/Customer/CostCategory **均无 custom_id**（这三个实体在 Atlas 也不编号；不新增 Sequence scope，镜像既有 PartCategory/AssetCategory 的无编号惯例）。Vendor 与 Customer 的联系字段在各自模型内联声明（不引入新的共享 contact mixin，沿用本仓库各模型独立声明列的惯例）。

### ① `tb_vendor` 供应商（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| name | String(300), nullable=False | 供应商名 |
| vendor_type | String(120), default "", server_default "" | 类型（自由文本）|
| description | Text, default "", server_default "" | |
| rate | Numeric(18,4), nullable=False, default 0, server_default "0" | 费率（裸金额，本期无消费端，作 3C/Phase 4 预留）|
| address | String(500), default "", server_default "" | |
| phone | String(60), default "", server_default "" | |
| email | String(200), default "", server_default "" | |
| website | String(300), default "", server_default "" | |

M:N part 关联经 `tb_vendor_part`。

### ② `tb_customer` 客户（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| name | String(300), nullable=False | 客户名 |
| customer_type | String(120), default "", server_default "" | |
| description | Text, default "", server_default "" | |
| rate | Numeric(18,4), nullable=False, default 0, server_default "0" | |
| billing_currency | String(8), default "", server_default "" | 货币码裸字符串（如 "CNY"；Currency 实体延后）|
| address | String(500), default "", server_default "" | |
| phone | String(60), default "", server_default "" | |
| email | String(200), default "", server_default "" | |
| website | String(300), default "", server_default "" | |

M:N part 关联经 `tb_customer_part`。

### ③ `tb_cost_category` 成本分类（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| name | String(300), nullable=False | |
| description | Text, default "", server_default "" | |

唯一约束 `uq_cost_category_company_name`(company_id, name)。与既有 PartCategory 逐行同构（每租户、软删、name/description）。

### ④ `tb_vendor_part` 供应商↔备件 M:N（仅 Timestamp + Tenant，append-only 关系行）
| 字段 | 类型 | 说明 |
|---|---|---|
| vendor_id | String(36) FK tb_vendor ondelete=CASCADE, index | |
| part_id | String(36) FK tb_part ondelete=CASCADE, index | |

唯一约束 `uq_vendor_part`(vendor_id, part_id)。

### ⑤ `tb_customer_part` 客户↔备件 M:N（仅 Timestamp + Tenant）
| 字段 | 类型 | 说明 |
|---|---|---|
| customer_id | String(36) FK tb_customer ondelete=CASCADE, index | |
| part_id | String(36) FK tb_part ondelete=CASCADE, index | |

唯一约束 `uq_customer_part`(customer_id, part_id)。

> 关联由 Vendor/Customer 侧拥有：part_ids 在各自 create/update 全量替换（先 `delete` 再 re-add，`dict.fromkeys` 去重，getter `order_by(part_id)` 确定序），与 3A `part_service` 的 assignee/team/asset 全量替换逐行同构。

## 3. Pydantic Schema（单文件 `app/schemas/partner.py`）

容纳三实体全部 schema（类比 3A 单文件 `schemas/part.py` 容纳 Part/Category/Consumption/MultiPart）：

- `VendorCreate`：name(min_length=1,max_length=300) + vendor_type/description/address/phone/email/website(带 max_length，default "") + rate(Decimal, default 0) + part_ids(list[str], default [])。
- `VendorUpdate`：全字段 Optional（含 part_ids: list[str] | None）。
- `VendorRead`（from_attributes）：id + 全列字段 + part_ids(list[str], 由 router 填充)。
- `VendorMini`（from_attributes）：id + name。
- `CustomerCreate/Update/Read/Mini`：同构，Read/Create/Update 多含 `billing_currency`。
- `CostCategoryCreate`：name(min_length=1) + description(default "")。
- `CostCategoryUpdate`：name/description Optional。
- `CostCategoryRead`（from_attributes）：id + name + description。

## 4. Service 层（3 文件，镜像 3A）

- `app/services/vendor_service.py`：
  - `create_vendor(db, payload, company_id, actor_user_id) -> Vendor`（flush 后 `_set_parts`，单 commit）。
  - `list_vendors(db, *, part_id=None) -> list[Vendor]`（`is_active` 真；part_id 经 `tb_vendor_part` 子查询过滤；`order_by(name, id)`）。
  - `get_vendor(db, vendor_id) -> Vendor | None`（软删不可见）。
  - `update_vendor(db, vendor, payload, company_id, actor_user_id)`（标量字段 setattr；part_ids 非 None 则全量替换）。
  - `delete_vendor(db, vendor)`（软删 is_active=False + deleted_at=utcnow）。
  - `part_ids(db, vendor_id) -> list[str]`（`order_by(part_id)`）。
- `app/services/customer_service.py`：同构（含 billing_currency 标量字段）。
- `app/services/cost_category_service.py`：与 `part_category_service` 逐行同构（CRUD 软删，无关联）。

## 5. API / 路由（3 router + main 挂载）

- `/api/v1/vendors`（tag vendors）：
  - `GET ""`（`?part_id=`，PART 不存在/跨租户时过滤结果为空，不报错）→ list[VendorRead]，需 `vendor.view`。
  - `POST ""` → 201 VendorRead，需 `vendor.create`。
  - `GET "/mini"`（**必须注册在 `/{vendor_id}` 之前**）→ list[VendorMini]，需 `vendor.view`。
  - `GET/PATCH/DELETE "/{vendor_id}"` → VendorRead / VendorRead / 204，需 view/edit/delete。
  - VendorRead 经 `_read(db, v)` 填充 `part_ids`。
- `/api/v1/customers`（tag customers）：同构，CustomerRead 含 part_ids + billing_currency。
- `/api/v1/cost-categories`（tag cost-categories）：镜像 part-categories，`GET ""` / `POST ""`(cost_category.manage) / `GET/PATCH/DELETE "/{id}"`，**无 mini**（查找列表本身即足够小）。
- **跨租户**：每个 `_ensure_*` 校验 `entity.company_id == current_user.company_id`，否则 404（`VENDOR_NOT_FOUND` / `CUSTOMER_NOT_FOUND` / `COST_CATEGORY_NOT_FOUND`）。
- create/update 的 part_ids **不强校验跨租户归属**：沿用 3A `category_id` 的既有模式（跨租户 part_id 因 ORM 租户作用域在读取时自然不解析，无害）；不夹带跨模块加固决策。

## 6. RBAC（`app/permissions.py` 精确 Edit 插入）

- 新权限码常量：`VENDOR_VIEW/CREATE/EDIT/DELETE`、`CUSTOMER_VIEW/CREATE/EDIT/DELETE`、`COST_CATEGORY_VIEW`、`COST_CATEGORY_MANAGE`。
- 分组列表：`_VENDOR`、`_CUSTOMER`、`_COST_CATEGORY`。
- `ALL_PERMISSIONS` 末尾追加 `+ _VENDOR + _CUSTOMER + _COST_CATEGORY`（不丢任何既有组）。
- 角色默认：
  - admin / super_admin：自动全含。
  - **technician**：追加 `VENDOR_VIEW, CUSTOMER_VIEW, COST_CATEGORY_VIEW`（可引用、不可管理，呼应 3A technician 的只读授予）。
  - viewer：自动经 `.endswith(".view")` 含 vendor.view + customer.view + cost_category.view。
  - requester：不变（仅 request.view/create）。

## 7. 迁移

单文件 `backend/alembic/versions/20260531_0008_phase3b_vendor.py`，`revision = "phase3b_vendor"`，`down_revision = "phase3a_part"`。hand-authored 双方言（MySQL prod + SQLite test），新表 `create_table`。建 5 表（tb_vendor、tb_customer、tb_cost_category、tb_vendor_part、tb_customer_part）含全部索引（company_id + 各 FK 列）与唯一约束。`upgrade` ↔ `downgrade` 对称（downgrade 先 drop 子关联表再 drop 父表，索引先于表 drop）。迁移后 `alembic heads` 仅 `phase3b_vendor (head)`。

## 8. 测试策略（TDD，逐 task 红→绿→提交）

- 模型：行写入 + 关联 + 唯一约束 + `__all__` 导出注册。
- 迁移：revision 链 + SQLite upgrade/downgrade 往返（断言 5 表建/删）。
- RBAC 契约：新码注册 + admin/super_admin 全含 + technician 三个 view（无 create/edit/delete/manage）+ viewer 含三 view + requester 不变 + 既有契约不破。
- schema：必填/默认/Optional + part_ids 默认空。
- service：3 实体 CRUD + part_ids 全量替换 + `list_vendors/customers(part_id=)` 过滤 + 软删不可见。
- router API：CRUD + `/mini` 路由顺序 + 跨租户 404 + technician 只读 403。

预计 ~11–12 个 TDD task。

## 9. 文件清单

**新增：** `app/models/vendor.py`(Vendor + VendorPart)、`app/models/customer.py`(Customer + CustomerPart)、`app/models/cost_category.py`(CostCategory)；`app/schemas/partner.py`（三实体 schema 合一）；`app/services/vendor_service.py`、`customer_service.py`、`cost_category_service.py`；`app/routers/vendors.py`、`customers.py`、`cost_categories.py`；迁移 `alembic/versions/20260531_0008_phase3b_vendor.py`。

**修改（共享文件，精确 Edit）：** `app/permissions.py`、`app/models/__init__.py`、`app/main.py`。

## 10. 完成标准（Definition of Done）

- 全量 pytest 0 failed（基线 857 + 本期新增）。
- 5 张表经迁移可 upgrade/downgrade；`alembic heads` 单 head `phase3b_vendor`。
- `/vendors`、`/customers`、`/cost-categories` 全套端点工作；Vendor/Customer 含 part_ids 全量替换 + `?part_id=` 反查 + `/mini`；technician 只读、不能管理；跨租户隔离 404。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净。
