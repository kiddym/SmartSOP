# Phase 3B 供应商 · 客户 · 成本分类 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现库存域主数据：Vendor/Customer/CostCategory 三实体 CRUD + Vendor/Customer 与 Part 的 M:N 关联（自身 create/update 全量替换 + `?part_id=` 反查 + `/mini` 下拉），配套 RBAC。

**Architecture:** 与 3A 同构的分层（model/schema/service/router）。三个独立主数据实体，无编号、无库存/消耗行为；关联由 Vendor/Customer 侧拥有。Schema 单文件 `partner.py`。零侵入既有 3A parts 代码，只在共享文件（`__init__.py`/`main.py`/`permissions.py`）精确插入。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · SQLite(测试)/MySQL(生产) · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`__init__.py`/`main.py`/`permissions.py`）一律用 Edit 精确替换，禁 sed/re.sub
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`
- 新文件务必 `git add` 后再提交
- 复用既有签名：`bad_request(code,msg)`/`not_found(code,msg)`（均 raise HTTPException）；`app.models.base.utcnow`、`DATETIME6`；`app.deps.get_db`、`require_permission(code)`
- 基线：全量 pytest 857 passed，alembic 单 head `phase3a_part`。Vendor/Customer/CostCategory 均**无 custom_id**（不用 sequence_service）。

---

## Task 1: Vendor/Customer/CostCategory ORM 模型（5 张表）+ 注册

**Files:**
- Create: `backend/app/models/vendor.py`（Vendor + VendorPart）
- Create: `backend/app/models/customer.py`（Customer + CustomerPart）
- Create: `backend/app/models/cost_category.py`（CostCategory）
- Modify: `backend/app/models/__init__.py`（import 区 + `__all__`）
- Test: `backend/tests/unit/test_partner_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_partner_models.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.vendor import Vendor, VendorPart
from app.models.customer import Customer, CustomerPart
from app.models.cost_category import CostCategory


def test_vendor_row_and_parts(db: Session):
    v = Vendor(name="泉州轴承厂", vendor_type="轴承", rate=Decimal("8.5000"),
               email="a@b.com", company_id="co-1")
    db.add(v)
    db.commit()
    db.refresh(v)
    assert v.id and v.is_active is True
    assert v.vendor_type == "轴承" and v.description == "" and v.website == ""
    db.add(VendorPart(vendor_id=v.id, part_id="p-1", company_id="co-1"))
    db.commit()
    rel = db.query(VendorPart).filter_by(vendor_id=v.id).one()
    assert rel.part_id == "p-1"


def test_customer_row_and_parts(db: Session):
    c = Customer(name="某矿业", customer_type="大客户", rate=Decimal("0"),
                 billing_currency="CNY", company_id="co-1")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.id and c.is_active is True and c.billing_currency == "CNY"
    assert c.description == "" and c.phone == ""
    db.add(CustomerPart(customer_id=c.id, part_id="p-1", company_id="co-1"))
    db.commit()
    rel = db.query(CustomerPart).filter_by(customer_id=c.id).one()
    assert rel.part_id == "p-1"


def test_cost_category_row(db: Session):
    cc = CostCategory(name="耗材", company_id="co-1")
    db.add(cc)
    db.commit()
    db.refresh(cc)
    assert cc.id and cc.is_active is True and cc.description == ""


def test_partner_exports_registered():
    import app.models as mod
    for name in ("Vendor", "VendorPart", "Customer", "CustomerPart", "CostCategory"):
        assert name in mod.__all__ and hasattr(mod, name)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_models.py -q`
Expected: FAIL（ModuleNotFoundError: app.models.vendor）

- [ ] **Step 3: 写 Vendor 模型**

`backend/app/models/vendor.py`:
```python
"""供应商（Vendor，每租户）+ M:N 关联备件。纯主数据，无编号、无库存行为。"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Vendor(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_vendor"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), default="", server_default="")
    email: Mapped[str] = mapped_column(String(200), default="", server_default="")
    website: Mapped[str] = mapped_column(String(300), default="", server_default="")


class VendorPart(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_vendor_part"
    __table_args__ = (
        UniqueConstraint("vendor_id", "part_id", name="uq_vendor_part"),
    )

    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 4: 写 Customer 模型**

`backend/app/models/customer.py`:
```python
"""客户（Customer，每租户）+ M:N 关联备件。billing_currency 为裸货币码（Currency 实体延后）。"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Customer(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_customer"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    billing_currency: Mapped[str] = mapped_column(String(8), default="", server_default="")
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), default="", server_default="")
    email: Mapped[str] = mapped_column(String(200), default="", server_default="")
    website: Mapped[str] = mapped_column(String(300), default="", server_default="")


class CustomerPart(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_customer_part"
    __table_args__ = (
        UniqueConstraint("customer_id", "part_id", name="uq_customer_part"),
    )

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_customer.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 5: 写 CostCategory 模型**

`backend/app/models/cost_category.py`:
```python
"""成本分类（每租户）。镜像 PartCategory。"""
from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class CostCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_cost_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_cost_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 6: 注册到 `app/models/__init__.py`**

先 Read 文件定位锚点。在 import 区 `from app.models.multi_part import MultiPart, MultiPartItem` 行之后插入：
```python
from app.models.vendor import Vendor, VendorPart
from app.models.customer import Customer, CustomerPart
from app.models.cost_category import CostCategory
```
在 `__all__` 列表中 `"MultiPartItem",` 行之后插入：
```python
    "Vendor",
    "VendorPart",
    "Customer",
    "CustomerPart",
    "CostCategory",
```
（若锚点文本略有差异，Read 实际文件后在等价位置插入完全相同的新行。）

- [ ] **Step 7: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_models.py -q && python -c "import app.models; import app.main"`
Expected: PASS（4 passed）+ 无导入错误

- [ ] **Step 8: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/vendor.py backend/app/models/customer.py backend/app/models/cost_category.py backend/app/models/__init__.py backend/tests/unit/test_partner_models.py
git commit -m "$(printf 'feat(phase-3b): add Vendor/Customer/CostCategory ORM models\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/20260531_0008_phase3b_vendor.py`
- Test: `backend/tests/unit/test_partner_migration.py`

- [ ] **Step 1: 写失败测试（upgrade/downgrade 在 SQLite 往返）**

`backend/tests/unit/test_partner_migration.py`:
```python
import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0008_phase3b_vendor")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase3b_vendor"
    assert m.down_revision == "phase3a_part"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_part (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_vendor", "tb_customer", "tb_cost_category",
                "tb_vendor_part", "tb_customer_part",
            } <= tables
            _mod().downgrade()
            assert "tb_vendor" not in inspect(conn).get_table_names()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_migration.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写迁移**

`backend/alembic/versions/20260531_0008_phase3b_vendor.py`:
```python
"""phase3b vendor: vendor + customer + cost_category + vendor_part + customer_part

Revision ID: phase3b_vendor
Revises: phase3a_part
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3b_vendor"
down_revision: str | Sequence[str] | None = "phase3a_part"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_vendor",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("vendor_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("website", sa.String(300), nullable=False, server_default=""),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_vendor_company_id", "tb_vendor", ["company_id"])

    op.create_table(
        "tb_customer",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("customer_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("billing_currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("website", sa.String(300), nullable=False, server_default=""),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_customer_company_id", "tb_customer", ["company_id"])

    op.create_table(
        "tb_cost_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_cost_category_company_name"),
    )
    op.create_index("ix_tb_cost_category_company_id", "tb_cost_category", ["company_id"])

    op.create_table(
        "tb_vendor_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("vendor_id", sa.String(36),
                  sa.ForeignKey("tb_vendor.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("vendor_id", "part_id", name="uq_vendor_part"),
    )
    op.create_index("ix_tb_vendor_part_company_id", "tb_vendor_part", ["company_id"])
    op.create_index("ix_tb_vendor_part_vendor_id", "tb_vendor_part", ["vendor_id"])
    op.create_index("ix_tb_vendor_part_part_id", "tb_vendor_part", ["part_id"])

    op.create_table(
        "tb_customer_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("customer_id", sa.String(36),
                  sa.ForeignKey("tb_customer.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("customer_id", "part_id", name="uq_customer_part"),
    )
    op.create_index("ix_tb_customer_part_company_id", "tb_customer_part", ["company_id"])
    op.create_index("ix_tb_customer_part_customer_id", "tb_customer_part", ["customer_id"])
    op.create_index("ix_tb_customer_part_part_id", "tb_customer_part", ["part_id"])


def downgrade() -> None:
    op.drop_index("ix_tb_customer_part_part_id", table_name="tb_customer_part")
    op.drop_index("ix_tb_customer_part_customer_id", table_name="tb_customer_part")
    op.drop_index("ix_tb_customer_part_company_id", table_name="tb_customer_part")
    op.drop_table("tb_customer_part")
    op.drop_index("ix_tb_vendor_part_part_id", table_name="tb_vendor_part")
    op.drop_index("ix_tb_vendor_part_vendor_id", table_name="tb_vendor_part")
    op.drop_index("ix_tb_vendor_part_company_id", table_name="tb_vendor_part")
    op.drop_table("tb_vendor_part")
    op.drop_index("ix_tb_cost_category_company_id", table_name="tb_cost_category")
    op.drop_table("tb_cost_category")
    op.drop_index("ix_tb_customer_company_id", table_name="tb_customer")
    op.drop_table("tb_customer")
    op.drop_index("ix_tb_vendor_company_id", table_name="tb_vendor")
    op.drop_table("tb_vendor")
```

- [ ] **Step 4: 跑测试 + 确认 alembic head 唯一**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_migration.py -q && alembic heads`
Expected: PASS（2 passed）；`alembic heads` 输出仅 `phase3b_vendor (head)`

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/alembic/versions/20260531_0008_phase3b_vendor.py backend/tests/unit/test_partner_migration.py
git commit -m "$(printf 'feat(phase-3b): add alembic migration for vendor/customer/cost-category tables\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: RBAC 权限码 + 角色 + 契约测试

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase3b.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_phase3b.py`:
```python
from app import permissions as perms


def test_phase3b_codes_registered():
    for code in ["vendor.view", "vendor.create", "vendor.edit", "vendor.delete",
                 "customer.view", "customer.create", "customer.edit", "customer.delete",
                 "cost_category.view", "cost_category.manage"]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_partner():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_partner():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["vendor.view", "vendor.create", "vendor.edit", "vendor.delete",
                 "customer.view", "customer.create", "customer.edit", "customer.delete",
                 "cost_category.view", "cost_category.manage"]:
        assert code in admin["permissions"]


def test_technician_partner_view_only():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "vendor.view" in tech["permissions"]
    assert "customer.view" in tech["permissions"]
    assert "cost_category.view" in tech["permissions"]
    for denied in ("vendor.create", "vendor.edit", "vendor.delete",
                   "customer.create", "customer.edit", "customer.delete",
                   "cost_category.manage"):
        assert denied not in tech["permissions"]


def test_requester_unchanged_no_partner():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_partner_views():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "vendor.view" in viewer["permissions"]
    assert "customer.view" in viewer["permissions"]
    assert "cost_category.view" in viewer["permissions"]
    assert "vendor.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3b.py -q`
Expected: FAIL（vendor.* 等未注册）

- [ ] **Step 3: 改 `app/permissions.py`**

先 Read 文件定位锚点（3A 已加入 PART_* 与 _PART/_PART_CATEGORY）。在 `PART_CATEGORY_MANAGE = "part_category.manage"` 行之后插入：
```python

# --- 供应商 / 客户 / 成本分类（Phase 3B）---
VENDOR_VIEW = "vendor.view"
VENDOR_CREATE = "vendor.create"
VENDOR_EDIT = "vendor.edit"
VENDOR_DELETE = "vendor.delete"
CUSTOMER_VIEW = "customer.view"
CUSTOMER_CREATE = "customer.create"
CUSTOMER_EDIT = "customer.edit"
CUSTOMER_DELETE = "customer.delete"
COST_CATEGORY_VIEW = "cost_category.view"
COST_CATEGORY_MANAGE = "cost_category.manage"
```
在 `_PART_CATEGORY = [PART_CATEGORY_VIEW, PART_CATEGORY_MANAGE]` 行之后插入：
```python
_VENDOR = [VENDOR_VIEW, VENDOR_CREATE, VENDOR_EDIT, VENDOR_DELETE]
_CUSTOMER = [CUSTOMER_VIEW, CUSTOMER_CREATE, CUSTOMER_EDIT, CUSTOMER_DELETE]
_COST_CATEGORY = [COST_CATEGORY_VIEW, COST_CATEGORY_MANAGE]
```
把 `ALL_PERMISSIONS` 定义改为（在末尾追加 `+ _VENDOR + _CUSTOMER + _COST_CATEGORY`）；先 Read 实际聚合表达式，仅在其尾部追加，不丢任何既有组：
```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE
    + _METER + _READING + _PART + _PART_CATEGORY
    + _VENDOR + _CUSTOMER + _COST_CATEGORY
)
```
在 technician 角色的 permissions 列表中，`PART_VIEW, PART_CONSUME, PART_CATEGORY_VIEW,` 行之后插入：
```python
        VENDOR_VIEW, CUSTOMER_VIEW, COST_CATEGORY_VIEW,
```
（admin/super_admin 自动含全部；viewer 自动经 `.endswith(".view")` 含三个 view；requester 不变。）

- [ ] **Step 4: 跑测试确认通过 + 既有契约不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3b.py tests/ -q -k "permission or auth_service or roles"`
Expected: PASS（含 phase3b 新测 + 既有契约测试仍绿）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/permissions.py backend/tests/test_permissions_phase3b.py
git commit -m "$(printf 'feat(phase-3b): add vendor/customer/cost_category permissions + role defaults\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: Pydantic schemas（单文件 partner.py）

**Files:**
- Create: `backend/app/schemas/partner.py`
- Test: `backend/tests/unit/test_partner_schemas.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_partner_schemas.py`:
```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.partner import (
    VendorCreate,
    VendorUpdate,
    VendorMini,
    CustomerCreate,
    CustomerUpdate,
    CostCategoryCreate,
)


def test_vendor_create_defaults():
    v = VendorCreate(name="供应商A")
    assert v.vendor_type == "" and v.description == "" and v.rate == Decimal("0")
    assert v.address == "" and v.phone == "" and v.email == "" and v.website == ""
    assert v.part_ids == []


def test_vendor_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        VendorCreate(name="")


def test_vendor_update_all_optional():
    assert VendorUpdate().model_dump(exclude_unset=True) == {}


def test_vendor_mini_fields():
    m = VendorMini(id="v-1", name="供应商A")
    assert m.id == "v-1" and m.name == "供应商A"


def test_customer_create_defaults_and_currency():
    c = CustomerCreate(name="客户A", billing_currency="CNY")
    assert c.billing_currency == "CNY" and c.customer_type == ""
    assert c.rate == Decimal("0") and c.part_ids == []


def test_customer_update_all_optional():
    assert CustomerUpdate().model_dump(exclude_unset=True) == {}


def test_cost_category_create():
    cc = CostCategoryCreate(name="耗材")
    assert cc.name == "耗材" and cc.description == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_schemas.py -q`
Expected: FAIL（ModuleNotFoundError: app.schemas.partner）

- [ ] **Step 3: 写实现**

`backend/app/schemas/partner.py`:
```python
"""供应商/客户/成本分类 schema（Phase 3B）。关联 part_ids 由 router 填充。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    vendor_type: str = Field(default="", max_length=120)
    description: str = ""
    rate: Decimal = Decimal("0")
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    part_ids: list[str] = []


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    vendor_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    rate: Decimal | None = None
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    part_ids: list[str] | None = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    vendor_type: str
    description: str
    rate: Decimal
    address: str
    phone: str
    email: str
    website: str
    part_ids: list[str] = []


class VendorMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    customer_type: str = Field(default="", max_length=120)
    description: str = ""
    rate: Decimal = Decimal("0")
    billing_currency: str = Field(default="", max_length=8)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    part_ids: list[str] = []


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    customer_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    rate: Decimal | None = None
    billing_currency: str | None = Field(default=None, max_length=8)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    part_ids: list[str] | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    customer_type: str
    description: str
    rate: Decimal
    billing_currency: str
    address: str
    phone: str
    email: str
    website: str
    part_ids: list[str] = []


class CustomerMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class CostCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class CostCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class CostCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_partner_schemas.py -q`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/schemas/partner.py backend/tests/unit/test_partner_schemas.py
git commit -m "$(printf 'feat(phase-3b): add vendor/customer/cost-category pydantic schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: cost_category_service CRUD

**Files:**
- Create: `backend/app/services/cost_category_service.py`
- Test: `backend/tests/unit/test_cost_category_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_cost_category_service.py`:
```python
from sqlalchemy.orm import Session

from app.schemas.partner import CostCategoryCreate, CostCategoryUpdate
from app.services import cost_category_service as svc

CO = "co-1"


def test_create_and_get(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="耗材"), CO, actor_user_id="a")
    assert c.id and svc.get_cost_category(db, c.id).name == "耗材"


def test_list(db: Session):
    svc.create_cost_category(db, CostCategoryCreate(name="A"), CO, actor_user_id="a")
    svc.create_cost_category(db, CostCategoryCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_cost_categories(db)) == 2


def test_update(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="旧"), CO, actor_user_id="a")
    svc.update_cost_category(db, c, CostCategoryUpdate(name="新", description="d"),
                             CO, actor_user_id="a")
    assert c.name == "新" and c.description == "d"


def test_delete_soft(db: Session):
    c = svc.create_cost_category(db, CostCategoryCreate(name="X"), CO, actor_user_id="a")
    svc.delete_cost_category(db, c)
    assert svc.get_cost_category(db, c.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_cost_category_service.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/cost_category_service.py`:
```python
"""成本分类服务：CRUD（软删）。镜像 part_category_service。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.cost_category import CostCategory
from app.schemas.partner import CostCategoryCreate, CostCategoryUpdate


def create_cost_category(db: Session, payload: CostCategoryCreate, company_id: str,
                         actor_user_id: str | None) -> CostCategory:
    cat = CostCategory(name=payload.name, description=payload.description,
                       company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_cost_categories(db: Session) -> list[CostCategory]:
    return list(db.execute(
        select(CostCategory).where(CostCategory.is_active.is_(True))
        .order_by(CostCategory.name, CostCategory.id)).scalars().all())


def get_cost_category(db: Session, category_id: str) -> CostCategory | None:
    c = db.get(CostCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_cost_category(db: Session, cat: CostCategory, payload: CostCategoryUpdate,
                         company_id: str, actor_user_id: str | None) -> CostCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_cost_category(db: Session, cat: CostCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_cost_category_service.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/cost_category_service.py backend/tests/unit/test_cost_category_service.py
git commit -m "$(printf 'feat(phase-3b): add cost category service CRUD\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: vendor_service — CRUD + part 关联 + 过滤

**Files:**
- Create: `backend/app/services/vendor_service.py`
- Test: `backend/tests/unit/test_vendor_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_vendor_service.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.partner import VendorCreate, VendorUpdate
from app.services import vendor_service as svc

CO = "co-1"


def test_create_vendor_with_parts(db: Session):
    v = svc.create_vendor(db, VendorCreate(
        name="供应商A", vendor_type="轴承", rate=Decimal("8.5"),
        part_ids=["p-1", "p-2", "p-1"]), CO, actor_user_id="a")
    assert v.id and v.vendor_type == "轴承"
    assert svc.part_ids(db, v.id) == ["p-1", "p-2"]          # 去重 + 按 part_id 序


def test_list_and_filter_by_part(db: Session):
    svc.create_vendor(db, VendorCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.create_vendor(db, VendorCreate(name="B", part_ids=["p-2"]), CO, actor_user_id="a")
    assert len(svc.list_vendors(db)) == 2
    got = svc.list_vendors(db, part_id="p-1")
    assert len(got) == 1 and got[0].name == "A"


def test_update_replaces_parts_and_scalars(db: Session):
    v = svc.create_vendor(db, VendorCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.update_vendor(db, v, VendorUpdate(name="改名", part_ids=["p-9", "p-8"]),
                      CO, actor_user_id="a")
    assert v.name == "改名"
    assert svc.part_ids(db, v.id) == ["p-8", "p-9"]          # 全量替换


def test_delete_vendor_soft(db: Session):
    v = svc.create_vendor(db, VendorCreate(name="A"), CO, actor_user_id="a")
    svc.delete_vendor(db, v)
    assert svc.get_vendor(db, v.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_vendor_service.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/vendor_service.py`:
```python
"""供应商服务：CRUD（软删）、M:N 备件（全量替换）、列表过滤（part_id 反查）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.vendor import Vendor, VendorPart
from app.schemas.partner import VendorCreate, VendorUpdate


def part_ids(db: Session, vendor_id: str) -> list[str]:
    return list(db.execute(
        select(VendorPart.part_id).where(VendorPart.vendor_id == vendor_id)
        .order_by(VendorPart.part_id)).scalars().all())


def _set_parts(db: Session, vendor_id: str, company_id: str,
               part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(VendorPart(vendor_id=vendor_id, part_id=pid, company_id=company_id))


def create_vendor(db: Session, payload: VendorCreate, company_id: str,
                  actor_user_id: str | None) -> Vendor:
    v = Vendor(
        name=payload.name, vendor_type=payload.vendor_type,
        description=payload.description, rate=payload.rate, address=payload.address,
        phone=payload.phone, email=payload.email, website=payload.website,
        company_id=company_id,
    )
    db.add(v)
    db.flush()
    _set_parts(db, v.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(v)
    return v


def list_vendors(db: Session, *, part_id: str | None = None) -> list[Vendor]:
    stmt = select(Vendor).where(Vendor.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(Vendor.id.in_(
            select(VendorPart.vendor_id).where(VendorPart.part_id == part_id)))
    return list(db.execute(stmt.order_by(Vendor.name, Vendor.id)).scalars().all())


def get_vendor(db: Session, vendor_id: str) -> Vendor | None:
    v = db.get(Vendor, vendor_id)
    if v is None or not v.is_active:
        return None
    return v


def update_vendor(db: Session, v: Vendor, payload: VendorUpdate, company_id: str,
                  actor_user_id: str | None) -> Vendor:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, val in data.items():
        setattr(v, k, val)
    if new_parts is not None:
        db.execute(VendorPart.__table__.delete().where(VendorPart.vendor_id == v.id))
        _set_parts(db, v.id, company_id, new_parts)
    db.commit()
    db.refresh(v)
    return v


def delete_vendor(db: Session, v: Vendor) -> None:
    v.is_active = False
    v.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_vendor_service.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/vendor_service.py backend/tests/unit/test_vendor_service.py
git commit -m "$(printf 'feat(phase-3b): add vendor service CRUD + part relations + filter\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: customer_service — CRUD + part 关联 + 过滤

**Files:**
- Create: `backend/app/services/customer_service.py`
- Test: `backend/tests/unit/test_customer_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_customer_service.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.partner import CustomerCreate, CustomerUpdate
from app.services import customer_service as svc

CO = "co-1"


def test_create_customer_with_parts_and_currency(db: Session):
    c = svc.create_customer(db, CustomerCreate(
        name="客户A", customer_type="大客户", billing_currency="CNY",
        rate=Decimal("0"), part_ids=["p-2", "p-1"]), CO, actor_user_id="a")
    assert c.id and c.billing_currency == "CNY"
    assert svc.part_ids(db, c.id) == ["p-1", "p-2"]          # 按 part_id 序


def test_list_and_filter_by_part(db: Session):
    svc.create_customer(db, CustomerCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.create_customer(db, CustomerCreate(name="B", part_ids=["p-2"]), CO, actor_user_id="a")
    assert len(svc.list_customers(db)) == 2
    got = svc.list_customers(db, part_id="p-2")
    assert len(got) == 1 and got[0].name == "B"


def test_update_replaces_parts(db: Session):
    c = svc.create_customer(db, CustomerCreate(name="A", part_ids=["p-1"]), CO, actor_user_id="a")
    svc.update_customer(db, c, CustomerUpdate(billing_currency="USD", part_ids=["p-9"]),
                        CO, actor_user_id="a")
    assert c.billing_currency == "USD"
    assert svc.part_ids(db, c.id) == ["p-9"]


def test_delete_customer_soft(db: Session):
    c = svc.create_customer(db, CustomerCreate(name="A"), CO, actor_user_id="a")
    svc.delete_customer(db, c)
    assert svc.get_customer(db, c.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_customer_service.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/customer_service.py`:
```python
"""客户服务：CRUD（软删）、M:N 备件（全量替换）、列表过滤（part_id 反查）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.customer import Customer, CustomerPart
from app.schemas.partner import CustomerCreate, CustomerUpdate


def part_ids(db: Session, customer_id: str) -> list[str]:
    return list(db.execute(
        select(CustomerPart.part_id).where(CustomerPart.customer_id == customer_id)
        .order_by(CustomerPart.part_id)).scalars().all())


def _set_parts(db: Session, customer_id: str, company_id: str,
               part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(CustomerPart(customer_id=customer_id, part_id=pid, company_id=company_id))


def create_customer(db: Session, payload: CustomerCreate, company_id: str,
                    actor_user_id: str | None) -> Customer:
    c = Customer(
        name=payload.name, customer_type=payload.customer_type,
        description=payload.description, rate=payload.rate,
        billing_currency=payload.billing_currency, address=payload.address,
        phone=payload.phone, email=payload.email, website=payload.website,
        company_id=company_id,
    )
    db.add(c)
    db.flush()
    _set_parts(db, c.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(c)
    return c


def list_customers(db: Session, *, part_id: str | None = None) -> list[Customer]:
    stmt = select(Customer).where(Customer.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(Customer.id.in_(
            select(CustomerPart.customer_id).where(CustomerPart.part_id == part_id)))
    return list(db.execute(stmt.order_by(Customer.name, Customer.id)).scalars().all())


def get_customer(db: Session, customer_id: str) -> Customer | None:
    c = db.get(Customer, customer_id)
    if c is None or not c.is_active:
        return None
    return c


def update_customer(db: Session, c: Customer, payload: CustomerUpdate, company_id: str,
                    actor_user_id: str | None) -> Customer:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, val in data.items():
        setattr(c, k, val)
    if new_parts is not None:
        db.execute(CustomerPart.__table__.delete().where(CustomerPart.customer_id == c.id))
        _set_parts(db, c.id, company_id, new_parts)
    db.commit()
    db.refresh(c)
    return c


def delete_customer(db: Session, c: Customer) -> None:
    c.is_active = False
    c.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_customer_service.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/customer_service.py backend/tests/unit/test_customer_service.py
git commit -m "$(printf 'feat(phase-3b): add customer service CRUD + part relations + filter\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: cost_categories router + main 挂载

**Files:**
- Create: `backend/app/routers/cost_categories.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_cost_category_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_cost_category_api.py`:
```python
"""成本分类 API（Phase 3B）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_cost_category_crud(client):
    t = _admin(client)
    r = client.post("/api/v1/cost-categories", json={"name": "耗材"}, headers=_h(t))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.get("/api/v1/cost-categories", headers=_h(t)).status_code == 200
    upd = client.patch(f"/api/v1/cost-categories/{cid}", json={"name": "改名"}, headers=_h(t))
    assert upd.json()["name"] == "改名"
    assert client.delete(f"/api/v1/cost-categories/{cid}", headers=_h(t)).status_code == 204


def test_cost_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post("/api/v1/cost-categories", json={"name": "X"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/cost-categories/{cid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cost_category_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/cost_categories.py`:
```python
"""成本分类 API（/api/v1/cost-categories）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.cost_category import CostCategory
from app.models.user import User
from app.schemas.partner import (
    CostCategoryCreate,
    CostCategoryRead,
    CostCategoryUpdate,
)
from app.services import cost_category_service as svc

router = APIRouter(prefix="/api/v1/cost-categories", tags=["cost-categories"])


def _ensure(c: CostCategory | None, company_id: str) -> CostCategory:
    if c is None or c.company_id != company_id:
        raise not_found("COST_CATEGORY_NOT_FOUND", "成本分类不存在")
    return c


@router.get("", response_model=list[CostCategoryRead])
def list_cost_categories(db: Session = Depends(get_db),
                         current_user: User = Depends(require_permission(permissions.COST_CATEGORY_VIEW))):
    return svc.list_cost_categories(db)


@router.post("", response_model=CostCategoryRead, status_code=status.HTTP_201_CREATED)
def create_cost_category(payload: CostCategoryCreate, db: Session = Depends(get_db),
                         current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE))):
    return svc.create_cost_category(db, payload, current_user.company_id, actor_user_id=current_user.id)


@router.get("/{category_id}", response_model=CostCategoryRead)
def get_cost_category(category_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.COST_CATEGORY_VIEW))):
    return _ensure(svc.get_cost_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=CostCategoryRead)
def update_cost_category(category_id: str, payload: CostCategoryUpdate, db: Session = Depends(get_db),
                         current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE))):
    c = _ensure(svc.get_cost_category(db, category_id), current_user.company_id)
    return svc.update_cost_category(db, c, payload, current_user.company_id, actor_user_id=current_user.id)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cost_category(category_id: str, db: Session = Depends(get_db),
                         current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE))):
    c = _ensure(svc.get_cost_category(db, category_id), current_user.company_id)
    svc.delete_cost_category(db, c)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `part_consumptions,` 行之后插入一行：
```python
    cost_categories,
```
在 `app.include_router(part_consumptions.router)` 行之后插入：
```python
app.include_router(cost_categories.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cost_category_api.py -q && python -c "import app.main"`
Expected: PASS（2 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/cost_categories.py backend/app/main.py backend/tests/test_cost_category_api.py
git commit -m "$(printf 'feat(phase-3b): add cost-categories router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: vendors router + main 挂载

**Files:**
- Create: `backend/app/routers/vendors.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_vendor_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_vendor_api.py`:
```python
"""供应商 API（Phase 3B）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post("/api/v1/users", headers=_h(admin_token), json={
        "email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid})
    return client.post("/api/v1/auth/login", json={
        "company_slug": "acme", "email": "tech@acme.com",
        "password": "secret123"}).json()["access_token"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"},
                       headers=_h(t)).json()["id"]


def test_vendor_crud_and_parts(client):
    t = _admin(client)
    p1 = _part_id(client, t, "A")
    r = client.post("/api/v1/vendors",
                    json={"name": "供应商A", "vendor_type": "轴承", "part_ids": [p1]},
                    headers=_h(t))
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert r.json()["vendor_type"] == "轴承" and r.json()["part_ids"] == [p1]
    got = client.get(f"/api/v1/vendors/{vid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["name"] == "供应商A"
    upd = client.patch(f"/api/v1/vendors/{vid}", json={"name": "改名", "part_ids": []},
                       headers=_h(t))
    assert upd.json()["name"] == "改名" and upd.json()["part_ids"] == []
    assert client.delete(f"/api/v1/vendors/{vid}", headers=_h(t)).status_code == 204


def test_vendor_filter_by_part(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    client.post("/api/v1/vendors", json={"name": "V1", "part_ids": [p1]}, headers=_h(t))
    client.post("/api/v1/vendors", json={"name": "V2", "part_ids": [p2]}, headers=_h(t))
    got = client.get(f"/api/v1/vendors?part_id={p1}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["name"] == "V1"


def test_vendor_mini(client):
    t = _admin(client)
    client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(t))
    mini = client.get("/api/v1/vendors/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "name"}
    assert mini.json()[0]["name"] == "供应商A"


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(admin))
    assert client.get("/api/v1/vendors", headers=_h(tech)).status_code == 200
    assert client.post("/api/v1/vendors", json={"name": "x"},
                       headers=_h(tech)).status_code == 403


def test_vendor_tenant_isolation(client):
    a = _admin(client)
    vid = client.post("/api/v1/vendors", json={"name": "供应商A"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/vendors/{vid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vendor_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/vendors.py`:
```python
"""供应商 API（/api/v1/vendors）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.partner import VendorCreate, VendorMini, VendorRead, VendorUpdate
from app.services import vendor_service as svc

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])


def _ensure(v: Vendor | None, company_id: str) -> Vendor:
    if v is None or v.company_id != company_id:
        raise not_found("VENDOR_NOT_FOUND", "供应商不存在")
    return v


def _read(db: Session, v: Vendor) -> VendorRead:
    data = VendorRead.model_validate(v)
    data.part_ids = svc.part_ids(db, v.id)
    return data


@router.get("", response_model=list[VendorRead])
def list_vendors(part_id: str | None = None, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.VENDOR_VIEW))):
    return [_read(db, v) for v in svc.list_vendors(db, part_id=part_id)]


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.VENDOR_CREATE))):
    v = svc.create_vendor(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, v)


# 注：/mini 必须注册在 /{vendor_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[VendorMini])
def list_vendors_mini(db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.VENDOR_VIEW))):
    return svc.list_vendors(db)


@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(vendor_id: str, db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.VENDOR_VIEW))):
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    return _read(db, v)


@router.patch("/{vendor_id}", response_model=VendorRead)
def update_vendor(vendor_id: str, payload: VendorUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.VENDOR_EDIT))):
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    svc.update_vendor(db, v, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, v)


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(vendor_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.VENDOR_DELETE))):
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    svc.delete_vendor(db, v)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `cost_categories,` 行之后插入一行：
```python
    vendors,
```
在 `app.include_router(cost_categories.router)` 行之后插入：
```python
app.include_router(vendors.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_vendor_api.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/vendors.py backend/app/main.py backend/tests/test_vendor_api.py
git commit -m "$(printf 'feat(phase-3b): add vendors router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: customers router + main 挂载

**Files:**
- Create: `backend/app/routers/customers.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_customer_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_customer_api.py`:
```python
"""客户 API（Phase 3B）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post("/api/v1/users", headers=_h(admin_token), json={
        "email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid})
    return client.post("/api/v1/auth/login", json={
        "company_slug": "acme", "email": "tech@acme.com",
        "password": "secret123"}).json()["access_token"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"},
                       headers=_h(t)).json()["id"]


def test_customer_crud_and_currency(client):
    t = _admin(client)
    p1 = _part_id(client, t, "A")
    r = client.post("/api/v1/customers",
                    json={"name": "客户A", "billing_currency": "CNY", "part_ids": [p1]},
                    headers=_h(t))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["billing_currency"] == "CNY" and r.json()["part_ids"] == [p1]
    upd = client.patch(f"/api/v1/customers/{cid}", json={"billing_currency": "USD"},
                       headers=_h(t))
    assert upd.json()["billing_currency"] == "USD"
    assert client.delete(f"/api/v1/customers/{cid}", headers=_h(t)).status_code == 204


def test_customer_filter_by_part(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    client.post("/api/v1/customers", json={"name": "C1", "part_ids": [p1]}, headers=_h(t))
    client.post("/api/v1/customers", json={"name": "C2", "part_ids": [p2]}, headers=_h(t))
    got = client.get(f"/api/v1/customers?part_id={p2}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["name"] == "C2"


def test_customer_mini(client):
    t = _admin(client)
    client.post("/api/v1/customers", json={"name": "客户A"}, headers=_h(t))
    mini = client.get("/api/v1/customers/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "name"}
    assert mini.json()[0]["name"] == "客户A"


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    client.post("/api/v1/customers", json={"name": "客户A"}, headers=_h(admin))
    assert client.get("/api/v1/customers", headers=_h(tech)).status_code == 200
    assert client.post("/api/v1/customers", json={"name": "x"},
                       headers=_h(tech)).status_code == 403


def test_customer_tenant_isolation(client):
    a = _admin(client)
    cid = client.post("/api/v1/customers", json={"name": "客户A"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/customers/{cid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_customer_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/customers.py`:
```python
"""客户 API（/api/v1/customers）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.customer import Customer
from app.models.user import User
from app.schemas.partner import CustomerCreate, CustomerMini, CustomerRead, CustomerUpdate
from app.services import customer_service as svc

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _ensure(c: Customer | None, company_id: str) -> Customer:
    if c is None or c.company_id != company_id:
        raise not_found("CUSTOMER_NOT_FOUND", "客户不存在")
    return c


def _read(db: Session, c: Customer) -> CustomerRead:
    data = CustomerRead.model_validate(c)
    data.part_ids = svc.part_ids(db, c.id)
    return data


@router.get("", response_model=list[CustomerRead])
def list_customers(part_id: str | None = None, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW))):
    return [_read(db, c) for c in svc.list_customers(db, part_id=part_id)]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.CUSTOMER_CREATE))):
    c = svc.create_customer(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, c)


# 注：/mini 必须注册在 /{customer_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[CustomerMini])
def list_customers_mini(db: Session = Depends(get_db),
                        current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW))):
    return svc.list_customers(db)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.CUSTOMER_VIEW))):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    return _read(db, c)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.CUSTOMER_EDIT))):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    svc.update_customer(db, c, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, c)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.CUSTOMER_DELETE))):
    c = _ensure(svc.get_customer(db, customer_id), current_user.company_id)
    svc.delete_customer(db, c)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `vendors,` 行之后插入一行：
```python
    customers,
```
在 `app.include_router(vendors.router)` 行之后插入：
```python
app.include_router(customers.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_customer_api.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/customers.py backend/app/main.py backend/tests/test_customer_api.py
git commit -m "$(printf 'feat(phase-3b): add customers router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: 全量回归 + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/partner_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 857 + 新增；0 failed）。Read tee 文件确认真实摘要行（防陈旧回放）。

- [ ] **Step 2: 确认工作树与提交链干净**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git status --porcelain && git log --oneline -11
```
Expected: porcelain 为空；最近提交含 Task 1–10 各一次。

- [ ] **Step 3: alembic 单 head 校验**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads`
Expected: 仅 `phase3b_vendor (head)`

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含新增 partner 单测 + API 测 + 契约/迁移测）。
- `tb_vendor` / `tb_customer` / `tb_cost_category` / `tb_vendor_part` / `tb_customer_part` 五表经迁移可 upgrade/downgrade。
- `/vendors`、`/customers`、`/cost-categories` 全套端点工作；Vendor/Customer 含 part_ids 全量替换 + `?part_id=` 反查 + `/mini`；技师只读、不能管理；跨租户隔离 404。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净，alembic 单 head `phase3b_vendor`。
