# 库存采购补全 ④ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐库存/采购缺失的 6 张 M:N 关联（Part↔location/PM、Vendor↔asset/location、Customer↔asset/location）+ PurchaseOrderCategory + PurchaseOrder 扩展元数据字段。

**Architecture:** 全部复刻既有 M:N 模式（关联 id 列表内嵌实体 Create/Update/Read schema，service `delete`+re-add 全量同步，`xxx_ids` reader）。新关联在同步时**校验目标 id 归属当前租户**（改进点）。PurchaseOrderCategory 复刻 TimeCategory/WorkOrderCategory。统一迁移末位。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic + pytest（SQLite in-memory）。解释器 `backend/.venv/bin/python`；门禁 `ruff check app/` + `mypy app/`。

**全局约定（每任务适用）：**
- 工作目录 `backend/`；命令前缀 `.venv/bin/`。
- 每任务：写失败测试 → 跑红 → 最小实现 → 跑绿 → ruff + mypy 绿 → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 净室原创、仅中文。
- **并行协调**：本轮改 `permissions.py`/`models/__init__.py`/`main.py`（与 analytics/asset 轮相同的注册文件）。**建议在 analytics+asset 合入 main 后从更新后的 main 重新分叉执行**；否则合并按 backfill-merge-runbook 处理这三文件多方修改。
- 多租户：所有 join 表挂 TenantMixin；新关联写入校验同租户。

参考表名（已核实）：`tb_part` / `tb_location` / `tb_asset` / `tb_vendor` / `tb_customer` / `tb_preventive_maintenance` / `tb_purchase_order`。

测试 harness（复制到各新测试文件顶部，与现有库存测试一致）：
```python
def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}
```

---

## File Structure

| 文件 | 责任 | 任务 |
|---|---|---|
| `app/models/part.py` | + PartLocation / PartPM join 模型 | T1,T2 |
| `app/models/vendor.py` | + VendorAsset / VendorLocation | T3 |
| `app/models/customer.py` | + CustomerAsset / CustomerLocation | T4 |
| `app/models/purchase_order_category.py` | 新建分类模型 | T5 |
| `app/models/purchase_order.py` | + category_id + 4 元数据列 | T5,T6 |
| `app/schemas/part.py` | Part schema + location_ids/pm_ids | T1,T2 |
| `app/schemas/partner.py` | Vendor/Customer schema + asset_ids/location_ids | T3,T4 |
| `app/schemas/purchase_order.py` | PO schema + category_id + 4 字段 | T5,T6 |
| `app/schemas/purchase_order_category.py` | 新建分类 schema | T5 |
| `app/services/part_service.py` | location/pm 同步+校验 | T1,T2 |
| `app/services/vendor_service.py` | asset/location 同步+校验 | T3 |
| `app/services/customer_service.py` | asset/location 同步+校验 | T4 |
| `app/services/purchase_order_category_service.py` | 新建 CRUD service | T5 |
| `app/services/purchase_order_service.py` | category_id + 字段接线 | T5,T6 |
| `app/routers/purchase_order_categories.py` | 新建 CRUD router | T5 |
| `app/permissions.py` / `app/models/__init__.py` / `app/main.py` | 注册（T5 仅分类需要） | T5 |
| `alembic/versions/20260602_00XX_inventory_backfill.py` | 统一迁移 | T7 |

---

## Task 1: Part↔location（模板任务，完整展开）

**Files:**
- Modify: `app/models/part.py`、`app/schemas/part.py`、`app/services/part_service.py`、`app/routers/parts.py`
- Test: `tests/test_part_location_relation.py`

- [ ] **Step 1: 写失败测试**

`tests/test_part_location_relation.py`（含 harness）：
```python
"""Part↔location 关联：内嵌 location_ids + 同步 + 跨租户校验。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _loc(client, t, name="车间A"):
    return client.post("/api/v1/locations", headers=_h(t), json={"name": name}).json()["id"]


def _part(client, t, name="轴承", **extra):
    return client.post("/api/v1/parts", headers=_h(t), json={"name": name, **extra})


def test_create_with_locations(client):
    t = _admin(client)
    loc = _loc(client, t)
    r = _part(client, t, location_ids=[loc])
    assert r.status_code == 201, r.text
    assert r.json()["location_ids"] == [loc]


def test_update_replaces_locations(client):
    t = _admin(client)
    l1, l2 = _loc(client, t, "A"), _loc(client, t, "B")
    pid = _part(client, t, location_ids=[l1]).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"location_ids": [l2]})
    assert r.json()["location_ids"] == [l2]
    # 清空
    r2 = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"location_ids": []})
    assert r2.json()["location_ids"] == []


def test_cross_tenant_location_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    loc_a = _loc(client, ta, "A库")
    r = _part(client, tb, location_ids=[loc_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "LOCATION_NOT_FOUND"
```
> 核对建位置端点 `POST /api/v1/locations {name}` 与建零件端点返回结构（按现有 parts/locations 路由实际调整）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_part_location_relation.py -q`
Expected: FAIL（无 location_ids）。

- [ ] **Step 3: join 模型**

`app/models/part.py` 末尾追加（import 处确保有 `UniqueConstraint`）：
```python
class PartLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_location"
    __table_args__ = (UniqueConstraint("part_id", "location_id", name="uq_part_location"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
```
`app/models/__init__.py`：import `PartLocation`，加入 `__all__`。

- [ ] **Step 4: schema**

`app/schemas/part.py`：
- `PartCreate` 加 `location_ids: list[str] = []`
- `PartUpdate` 加 `location_ids: list[str] | None = None`
- `PartRead` 加 `location_ids: list[str] = []`

- [ ] **Step 5: service 同步 + 校验**

`app/services/part_service.py`：
- import 加 `from app.errors import not_found`、`from app.models.part import PartLocation`、`from app.models.location import Location`。
- 加校验助手：
```python
def _validate_location_ids(db: Session, ids: list[str], company_id: str) -> None:
    for lid in dict.fromkeys(ids):
        loc = db.get(Location, lid)
        if loc is None or not loc.is_active or loc.company_id != company_id:
            raise not_found("LOCATION_NOT_FOUND", "位置不存在")
```
- 加 reader：
```python
def location_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartLocation.location_id)
            .where(PartLocation.part_id == part_id)
            .order_by(PartLocation.location_id)
        )
        .scalars()
        .all()
    )
```
- `_set_relations`：扩展签名加 `location_id_list: list[str]`，函数体加：
```python
    for lid in dict.fromkeys(location_id_list):
        db.add(PartLocation(part_id=part_id, location_id=lid, company_id=company_id))
```
- `create_part`：在 `_set_relations(...)` 前 `_validate_location_ids(db, payload.location_ids, company_id)`；`_set_relations(...)` 调用补 `payload.location_ids`。
- `update_part`：`new_locations = data.pop("location_ids", None)`；末尾加：
```python
    if new_locations is not None:
        _validate_location_ids(db, new_locations, company_id)
        db.execute(delete(PartLocation).where(PartLocation.part_id == p.id))
        for lid in dict.fromkeys(new_locations):
            db.add(PartLocation(part_id=p.id, location_id=lid, company_id=company_id))
```
> 核对 `Location` 模型有 `is_active`/`company_id`（SoftDelete/Tenant Mixin）；如无 is_active，去掉该判断。

- [ ] **Step 6: 路由 read 回填**

`app/routers/parts.py` 的 `_read_part`：加 `data.location_ids = svc.location_ids(db, p.id)`。

- [ ] **Step 7: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_part_location_relation.py tests/test_parts_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS（不破坏既有零件测试）。

- [ ] **Step 8: commit**

```bash
git add -A && git commit -m "feat(inventory): Part<->location M:N relation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Part↔PM

**Files:** `app/models/part.py`、`app/schemas/part.py`、`app/services/part_service.py`、`app/routers/parts.py`；Test: `tests/test_part_pm_relation.py`

按 T1 同模式，delta：

- [ ] **Step 1: 测试**（镜像 T1，端点建 PM：`POST /api/v1/preventive-maintenances`，核对实际路径与必填字段；关联字段名 `pm_ids`，错误码 `PREVENTIVE_MAINTENANCE_NOT_FOUND`）。
- [ ] **Step 2: 跑红**：`.venv/bin/python -m pytest tests/test_part_pm_relation.py -q` → FAIL。
- [ ] **Step 3: 模型**：
```python
class PartPM(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_pm"
    __table_args__ = (UniqueConstraint("part_id", "pm_id", name="uq_part_pm"),)

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    pm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"), index=True
    )
```
注册到 `__init__.py`。
- [ ] **Step 4: schema**：Part Create/Update/Read 加 `pm_ids`（同 T1 三处）。
- [ ] **Step 5: service**：
```python
from app.models.preventive_maintenance import PreventiveMaintenance

def _validate_pm_ids(db: Session, ids: list[str], company_id: str) -> None:
    for pid in dict.fromkeys(ids):
        pm = db.get(PreventiveMaintenance, pid)
        if pm is None or not pm.is_active or pm.company_id != company_id:
            raise not_found("PREVENTIVE_MAINTENANCE_NOT_FOUND", "预防性维护不存在")

def pm_ids(db: Session, part_id: str) -> list[str]:
    return list(
        db.execute(
            select(PartPM.pm_id).where(PartPM.part_id == part_id).order_by(PartPM.pm_id)
        ).scalars().all()
    )
```
`_set_relations` 加 `pm_id_list` 参数与 add 循环；create/update 接线（同 T1 location 的两处）。
- [ ] **Step 6: 路由**：`_read_part` 加 `data.pm_ids = svc.pm_ids(db, p.id)`。
- [ ] **Step 7: 跑绿+门禁**：同 T1 命令（替测试文件名）。
- [ ] **Step 8: commit**：`feat(inventory): Part<->PM M:N relation`。

---

## Task 3: Vendor↔asset + Vendor↔location

**Files:** `app/models/vendor.py`、`app/schemas/partner.py`、`app/services/vendor_service.py`、`app/routers/vendors.py`；Test: `tests/test_vendor_relations.py`

先读 `app/services/vendor_service.py` 与 `app/schemas/partner.py` 现有 `VendorPart` 同步模式（vendor 侧 `part_ids` 已有），按相同结构加 `asset_ids`/`location_ids`。

- [ ] **Step 1: 测试**：建 vendor（`POST /api/v1/vendors {name}`）带 `asset_ids`/`location_ids`，回显、update 替换、跨租户 404（`ASSET_NOT_FOUND`/`LOCATION_NOT_FOUND`）。
- [ ] **Step 2: 跑红**。
- [ ] **Step 3: 模型**（`app/models/vendor.py` 追加）：
```python
class VendorAsset(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_asset"
    __table_args__ = (UniqueConstraint("vendor_id", "asset_id", name="uq_vendor_asset"),)
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )


class VendorLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_location"
    __table_args__ = (UniqueConstraint("vendor_id", "location_id", name="uq_vendor_location"),)
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
```
注册 `__init__.py`。
- [ ] **Step 4: schema**（`partner.py`）：VendorCreate 加 `asset_ids: list[str]=[]`/`location_ids: list[str]=[]`；VendorUpdate 加可空版；VendorRead 加两字段。
- [ ] **Step 5: service**（`vendor_service.py`）：加 `_validate_asset_ids`/`_validate_location_ids`（同 T1 校验，针对 Asset/Location 模型）、`asset_ids`/`location_ids` reader，create/update 同步（仿现有 VendorPart 同步；create add、update delete+re-add，前置校验）。
- [ ] **Step 6: 路由**（`vendors.py` 的 `_read`）：加 `data.asset_ids=svc.asset_ids(...)`、`data.location_ids=svc.location_ids(...)`。
- [ ] **Step 7: 跑绿+门禁**：`tests/test_vendor_relations.py tests/test_vendors_api.py`。
- [ ] **Step 8: commit**：`feat(inventory): Vendor<->asset/location M:N relations`。

---

## Task 4: Customer↔asset + Customer↔location

**Files:** `app/models/customer.py`、`app/schemas/partner.py`、`app/services/customer_service.py`、`app/routers/customers.py`；Test: `tests/test_customer_relations.py`

与 T3 完全对称（把 Vendor 换成 Customer）：

- [ ] **Step 1: 测试**（建 customer `POST /api/v1/customers {name}` 带 asset_ids/location_ids；回显/替换/跨租户 404）。
- [ ] **Step 2: 跑红**。
- [ ] **Step 3: 模型**（`customer.py` 追加 `CustomerAsset`/`CustomerLocation`，表名 `tb_customer_asset`/`tb_customer_location`，约束 `uq_customer_asset`/`uq_customer_location`，结构同 T3 把 vendor_id→customer_id、FK→tb_customer）。注册 `__init__.py`。
- [ ] **Step 4: schema**（CustomerCreate/Update/Read 加 asset_ids/location_ids）。
- [ ] **Step 5: service**（`customer_service.py`：校验 + reader + create/update 同步，仿现有 CustomerPart）。
- [ ] **Step 6: 路由**（`customers.py` 的 `_read` 回填）。
- [ ] **Step 7: 跑绿+门禁**：`tests/test_customer_relations.py tests/test_customers_api.py`。
- [ ] **Step 8: commit**：`feat(inventory): Customer<->asset/location M:N relations`。

---

## Task 5: PurchaseOrderCategory + PO.category_id

**Files:** 新建 `app/models/purchase_order_category.py`、`app/schemas/purchase_order_category.py`、`app/services/purchase_order_category_service.py`、`app/routers/purchase_order_categories.py`；改 `app/permissions.py`、`app/models/__init__.py`、`app/main.py`、`app/models/purchase_order.py`、`app/schemas/purchase_order.py`、`app/services/purchase_order_service.py`；Test: `tests/test_purchase_order_category_api.py`

复刻 WorkOrderCategory（见 analytics 轮）。delta 仅命名：

- [ ] **Step 1: 测试**：CRUD + 软删 + 重名 409（`PURCHASE_ORDER_CATEGORY_DUPLICATE`）+ 跨租户 + PO create 带 category_id 回显 + 跨租户 category→404（`PURCHASE_ORDER_CATEGORY_NOT_FOUND`）。
- [ ] **Step 2: 跑红**。
- [ ] **Step 3: 模型** `purchase_order_category.py`：
```python
class PurchaseOrderCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_purchase_order_category_company_name"),
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
```
- [ ] **Step 4: schema** `purchase_order_category.py`：Create(name/description)/Update(可空)/Read(id/name/description, from_attributes)。
- [ ] **Step 5: service** `purchase_order_category_service.py`：create（重名 409）/list（is_active）/get（软删→None）/update/delete（软删）。镜像 work_order_category_service。
- [ ] **Step 6: router** `purchase_order_categories.py`：`/api/v1/purchase-order-categories` CRUD，view/manage 权限，`_ensure` 抛 `PURCHASE_ORDER_CATEGORY_NOT_FOUND`。
- [ ] **Step 7: 权限/注册/挂载**：`permissions.py` 加 `PURCHASE_ORDER_CATEGORY_VIEW/MANAGE` + `_PURCHASE_ORDER_CATEGORY` 分组入 `ALL_PERMISSIONS`，technician 加 view；`__init__.py` 注册模型；`main.py` 挂 router。
- [ ] **Step 8: PO.category_id 接线**：`purchase_order.py` 加 `category_id` FK→tb_purchase_order_category SET NULL nullable index；`purchase_order.py` schema Create/Update 加 `category_id`、Read 暴露；`purchase_order_service.py` create/update 校验 category_id 同租户（404）并落值。
- [ ] **Step 9: 跑绿+门禁**：`tests/test_purchase_order_category_api.py tests/test_purchase_orders_api.py`。
- [ ] **Step 10: commit**：`feat(inventory): PurchaseOrderCategory + PO.category_id`。

---

## Task 6: PO 扩展元数据字段

**Files:** `app/models/purchase_order.py`、`app/schemas/purchase_order.py`、`app/services/purchase_order_service.py`；Test: `tests/test_purchase_order_fields.py`

- [ ] **Step 1: 测试**：PO create 带 `shipping_address`/`shipping_method`/`terms_of_payment`/`expected_delivery_date` → 回显；update 改值回显。
- [ ] **Step 2: 跑红**。
- [ ] **Step 3: 模型**（`purchase_order.py` 的 `PurchaseOrder` 加，import 处确保 `Date`）：
```python
    shipping_address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    shipping_method: Mapped[str] = mapped_column(String(120), default="", server_default="")
    terms_of_payment: Mapped[str] = mapped_column(String(200), default="", server_default="")
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, default=None)
```
（顶部 `from datetime import date` 若无则加。）
- [ ] **Step 4: schema**（`purchase_order.py`）：Create/Update 加四字段（Update 全可空）、Read 暴露。
- [ ] **Step 5: service**：create 构造补四字段；update 走 `model_dump(exclude_unset=True)` setattr（若已是该模式则自动覆盖，确认无遗漏白名单）。
- [ ] **Step 6: 跑绿+门禁**：`tests/test_purchase_order_fields.py tests/test_purchase_orders_api.py`。
- [ ] **Step 7: commit**：`feat(inventory): PO shipping/terms/expected-delivery fields`。

---

## Task 7: 统一迁移 + 单测 + 零漂移

**Files:** `alembic/versions/20260602_00XX_inventory_backfill.py`（XX 取当前 versions 目录下一个可用序号）；Test: `tests/unit/test_migration_inventory_backfill.py`

- [ ] **Step 1: 写失败测试** `tests/unit/test_migration_inventory_backfill.py`：
```python
"""迁移 inventory_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_00XX_inventory_backfill")


def test_revision_chain():
    m = _mod()
    assert m.revision == "inventory_backfill"
    assert m.down_revision == "workorder_labor_cost"  # 合并时按 runbook rebase


def test_upgrade_downgrade_sqlite():
    eng = create_engine("sqlite://")
    parents = (
        "tb_company", "tb_part", "tb_location", "tb_asset", "tb_vendor", "tb_customer",
        "tb_preventive_maintenance", "tb_purchase_order",
    )
    with eng.begin() as conn:
        for tbl in parents:
            conn.exec_driver_sql(f"CREATE TABLE {tbl} (id VARCHAR(36) PRIMARY KEY)")
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_part_location", "tb_part_pm", "tb_vendor_asset", "tb_vendor_location",
                "tb_customer_asset", "tb_customer_location", "tb_purchase_order_category",
            } <= tables
            po_cols = {c["name"] for c in inspect(conn).get_columns("tb_purchase_order")}
            assert {"category_id", "shipping_address", "shipping_method",
                    "terms_of_payment", "expected_delivery_date"} <= po_cols
            _mod().downgrade()
            tables2 = set(inspect(conn).get_table_names())
            assert "tb_part_location" not in tables2
```
（把文件名 `00XX` 与 `_mod()` 路径替换为实际序号。）

- [ ] **Step 2: 跑红**：`.venv/bin/python -m pytest tests/unit/test_migration_inventory_backfill.py -q` → FAIL。

- [ ] **Step 3: 迁移**：手写迁移，`revision="inventory_backfill"`、`down_revision="workorder_labor_cost"`。
  - `op.create_table` 6 张 join 表（每张：两 FK 列 CASCADE + id/created_at/updated_at/company_id + company FK CASCADE + PK + UniqueConstraint + company_id/两 FK 列各 index，与模型 mixin 完全一致）。
  - `op.create_table` `tb_purchase_order_category`（同 WorkOrderCategory 迁移结构：name/description/id/created_at/updated_at/is_active/deleted_at/company_id + company FK + PK + uq + company_id/created_at/is_active 索引）。
  - 对 `tb_purchase_order` 用 `op.batch_alter_table` 加 5 列（category_id + FK SET NULL + index；shipping_address/shipping_method/terms_of_payment server_default=""；expected_delivery_date nullable）。
  - downgrade 逆序 drop（先 PO 列与 batch FK、再 7 张表）。
  - docstring 注明：MySQL 全链受既有 initial_schema 阻塞（无关），DDL 以单测验证；合并按 backfill-merge-runbook rebase down_revision。
  > 逐表列对账模型 mixin（参照 analytics 轮的 0004 与 asset 轮的 0005 迁移写法）。batch 模式保证 SQLite ALTER 安全。

- [ ] **Step 4: 跑绿**：`.venv/bin/python -m pytest tests/unit/test_migration_inventory_backfill.py -q` → PASS。

- [ ] **Step 5: 零漂移**：`.venv/bin/alembic heads`（确认新迁移为 head）；逐表/列对账模型。全链 `alembic upgrade head` 若受既有 initial_schema 阻塞，以单测 DDL 为准（docstring 已声明）。

- [ ] **Step 6: 全量回归 + 门禁**：`.venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/` → 全 PASS。

- [ ] **Step 7: commit**：`feat(inventory): unified migration for relations + PO category/fields`。

---

## 收尾

完成 T1–T7 后派发最终 code review，再用 `superpowers:finishing-a-development-branch`。

**自查清单：**
- 6 张关联均：内嵌 `*_ids`、create/update 全量同步、Read 回显、**跨租户校验 404**、唯一约束防重复。
- PurchaseOrderCategory CRUD + PO.category_id 跨租户校验。
- PO 四元数据字段 create/update/read 通。
- **未加 PO 级货币字段**（不扰动分析 po_spend 口径）。
- 注册三文件（permissions/__init__/main）改动已知与他轮共享 → 合并按 runbook。
- 迁移 down_revision 合并 rebase 点已在 docstring 标注。
- 无 assert 控制生产流程。
