# Phase 3C 采购单（Purchase Order）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现采购单 PO（头引用 Vendor、行引用 Part）+ DRAFT→SUBMITTED→APPROVED|REJECTED|CANCELED 状态机 + 审批=整单入库回写 `Part.quantity`（non_stock 不增）+ 活动时间线 + RBAC。

**Architecture:** 与 3A/3B 同构分层（status 枚举 / model / schema / service / router）。状态机镜像 `request_status` + `request_service` 的 `can_transition`/`_resolve`/`_log` 模式；入库回写镜像 `part_consumption_service` 的 `non_stock` 语义。3 张新表（po 头 + line + activity），零侵入既有 3A/3B 代码，共享文件（`__init__.py`/`main.py`/`permissions.py`）精确插入。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · SQLite(测试)/MySQL(生产) · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`__init__.py`/`main.py`/`permissions.py`）一律用 Edit 精确替换，禁 sed/re.sub；插入前先 Read 定位真实锚点（3B 已在这些文件留下 vendor/customer/cost_category 锚点，3C 在其后追加）。
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`（注意是 "Claude Opus 4.5"，不是 4.8）
- 新文件务必 `git add` 后再提交
- 复用既有签名：`bad_request(code,msg)`（raise HTTPException）；`app.models.base.utcnow`、`DATETIME6`；`app.deps.get_db`、`require_permission(code)`；`app.errors.not_found(code,msg)`；`sequence_service.next_value(db, scope, company_id)` / `format_custom_id(prefix, value, digits=6)`
- 基线：全量 pytest 900 passed，alembic 单 head `phase3b_vendor`。

---

## Task 1: PurchaseOrderStatus 枚举 + can_transition

**Files:**
- Create: `backend/app/models/purchase_order_status.py`
- Test: `backend/tests/unit/test_purchase_order_status.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_status.py`:
```python
from app.models.purchase_order_status import PurchaseOrderStatus as S, can_transition


def test_enum_values():
    assert {s.value for s in S} == {
        "DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "CANCELED"}


def test_draft_transitions():
    assert can_transition(S.DRAFT, S.SUBMITTED) is True
    assert can_transition(S.DRAFT, S.CANCELED) is True
    assert can_transition(S.DRAFT, S.APPROVED) is False


def test_submitted_transitions():
    assert can_transition(S.SUBMITTED, S.APPROVED) is True
    assert can_transition(S.SUBMITTED, S.REJECTED) is True
    assert can_transition(S.SUBMITTED, S.CANCELED) is True
    assert can_transition(S.SUBMITTED, S.DRAFT) is False


def test_terminal_no_outgoing():
    for term in (S.APPROVED, S.REJECTED, S.CANCELED):
        for dst in S:
            assert can_transition(term, dst) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_status.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/models/purchase_order_status.py`:
```python
"""采购单状态机（DRAFT→SUBMITTED→APPROVED/REJECTED/CANCELED 终态）。"""
from __future__ import annotations

import enum


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


# 合法状态转移（DRAFT/SUBMITTED 为非终态；APPROVED/REJECTED/CANCELED 为终态，无出边）。
ALLOWED_TRANSITIONS: dict[PurchaseOrderStatus, frozenset[PurchaseOrderStatus]] = {
    PurchaseOrderStatus.DRAFT: frozenset(
        {PurchaseOrderStatus.SUBMITTED, PurchaseOrderStatus.CANCELED}
    ),
    PurchaseOrderStatus.SUBMITTED: frozenset(
        {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.REJECTED,
         PurchaseOrderStatus.CANCELED}
    ),
    PurchaseOrderStatus.APPROVED: frozenset(),
    PurchaseOrderStatus.REJECTED: frozenset(),
    PurchaseOrderStatus.CANCELED: frozenset(),
}


def can_transition(src: PurchaseOrderStatus, dst: PurchaseOrderStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_status.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/purchase_order_status.py backend/tests/unit/test_purchase_order_status.py
git commit -m "$(printf 'feat(phase-3c): add purchase order status state machine\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: ORM 模型（3 张表）+ 注册

**Files:**
- Create: `backend/app/models/purchase_order.py`（PurchaseOrder + PurchaseOrderLine + PurchaseOrderActivity）
- Modify: `backend/app/models/__init__.py`（import 区 + `__all__`）
- Test: `backend/tests/unit/test_purchase_order_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_models.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_status import PurchaseOrderStatus


def test_purchase_order_row_defaults(db: Session):
    po = PurchaseOrder(custom_id="PO000001", vendor_id="v-1", company_id="co-1")
    db.add(po)
    db.commit()
    db.refresh(po)
    assert po.id and po.is_active is True
    assert po.status == PurchaseOrderStatus.DRAFT
    assert po.notes == "" and po.resolution_note == ""
    assert po.resolved_by_user_id is None and po.resolved_at is None


def test_line_and_activity_rows(db: Session):
    po = PurchaseOrder(custom_id="PO000002", vendor_id="v-1", company_id="co-1")
    db.add(po)
    db.flush()
    db.add(PurchaseOrderLine(purchase_order_id=po.id, part_id="p-1",
                             quantity=Decimal("3"), unit_cost=Decimal("2.5"),
                             company_id="co-1"))
    db.add(PurchaseOrderActivity(purchase_order_id=po.id, activity_type="STATUS_CHANGE",
                                 from_status="DRAFT", to_status="SUBMITTED", company_id="co-1"))
    db.commit()
    ln = db.query(PurchaseOrderLine).filter_by(purchase_order_id=po.id).one()
    assert ln.part_id == "p-1" and ln.quantity == Decimal("3")
    act = db.query(PurchaseOrderActivity).filter_by(purchase_order_id=po.id).one()
    assert act.activity_type == "STATUS_CHANGE" and act.comment == ""


def test_purchase_order_exports_registered():
    import app.models as mod
    for name in ("PurchaseOrder", "PurchaseOrderLine", "PurchaseOrderActivity"):
        assert name in mod.__all__ and hasattr(mod, name)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_models.py -q`
Expected: FAIL（ModuleNotFoundError: app.models.purchase_order）

- [ ] **Step 3: 写模型**

`backend/app/models/purchase_order.py`:
```python
"""采购单（PO，每租户）：头 + 明细行 + 活动时间线。

头引用 Vendor（必填），行引用 Part（采购数量 + 单价快照）。
审批=整单入库回写 Part.quantity（见 purchase_order_service.approve）。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)
from app.models.purchase_order_status import PurchaseOrderStatus


class PurchaseOrder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_purchase_order"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_vendor.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SAEnum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.DRAFT
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolution_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)


class PurchaseOrderLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_line"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )


class PurchaseOrderActivity(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_purchase_order_activity"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    from_status: Mapped[str | None] = mapped_column(String(40), default=None)
    to_status: Mapped[str | None] = mapped_column(String(40), default=None)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 4: 注册到 `app/models/__init__.py`**

先 Read 文件。在 import 区 `from app.models.cost_category import CostCategory` 行之后插入：
```python
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
```
在 `__all__` 列表中 `"CostCategory",` 行之后插入：
```python
    "PurchaseOrder",
    "PurchaseOrderLine",
    "PurchaseOrderActivity",
```
（若锚点文本略有差异，Read 实际文件后在等价位置插入完全相同的新行。）

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_models.py -q && python -c "import app.models; import app.main"`
Expected: PASS（3 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/purchase_order.py backend/app/models/__init__.py backend/tests/unit/test_purchase_order_models.py
git commit -m "$(printf 'feat(phase-3c): add PurchaseOrder/Line/Activity ORM models\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/20260531_0009_phase3c_purchase_order.py`
- Test: `backend/tests/unit/test_purchase_order_migration.py`

- [ ] **Step 1: 写失败测试（upgrade/downgrade 在 SQLite 往返）**

`backend/tests/unit/test_purchase_order_migration.py`:
```python
import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module(
        "alembic.versions.20260531_0009_phase3c_purchase_order")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase3c_purchase_order"
    assert m.down_revision == "phase3b_vendor"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_vendor (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_part (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_purchase_order",
                "tb_purchase_order_line",
                "tb_purchase_order_activity",
            } <= tables
            _mod().downgrade()
            assert "tb_purchase_order" not in inspect(conn).get_table_names()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_migration.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写迁移**

`backend/alembic/versions/20260531_0009_phase3c_purchase_order.py`:
```python
"""phase3c purchase order: purchase_order + line + activity

Revision ID: phase3c_purchase_order
Revises: phase3b_vendor
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3c_purchase_order"
down_revision: str | Sequence[str] | None = "phase3b_vendor"
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
        "tb_purchase_order",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("vendor_id", sa.String(36),
                  sa.ForeignKey("tb_vendor.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Enum(
            "DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "CANCELED",
            name="purchaseorderstatus"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
        sa.Column("resolved_at", DATETIME6, nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_purchase_order_company_id", "tb_purchase_order", ["company_id"])
    op.create_index("ix_tb_purchase_order_vendor_id", "tb_purchase_order", ["vendor_id"])

    op.create_table(
        "tb_purchase_order_line",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("purchase_order_id", sa.String(36),
                  sa.ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_tb_purchase_order_line_company_id", "tb_purchase_order_line", ["company_id"])
    op.create_index("ix_tb_purchase_order_line_purchase_order_id", "tb_purchase_order_line", ["purchase_order_id"])
    op.create_index("ix_tb_purchase_order_line_part_id", "tb_purchase_order_line", ["part_id"])

    op.create_table(
        "tb_purchase_order_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("purchase_order_id", sa.String(36),
                  sa.ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("from_status", sa.String(40), nullable=True),
        sa.Column("to_status", sa.String(40), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        *_ts(),
    )
    op.create_index("ix_tb_purchase_order_activity_company_id", "tb_purchase_order_activity", ["company_id"])
    op.create_index("ix_tb_purchase_order_activity_purchase_order_id", "tb_purchase_order_activity", ["purchase_order_id"])


def downgrade() -> None:
    op.drop_index("ix_tb_purchase_order_activity_purchase_order_id", table_name="tb_purchase_order_activity")
    op.drop_index("ix_tb_purchase_order_activity_company_id", table_name="tb_purchase_order_activity")
    op.drop_table("tb_purchase_order_activity")
    op.drop_index("ix_tb_purchase_order_line_part_id", table_name="tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_line_purchase_order_id", table_name="tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_line_company_id", table_name="tb_purchase_order_line")
    op.drop_table("tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_vendor_id", table_name="tb_purchase_order")
    op.drop_index("ix_tb_purchase_order_company_id", table_name="tb_purchase_order")
    op.drop_table("tb_purchase_order")
```

- [ ] **Step 4: 跑测试 + 确认 alembic head 唯一**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_migration.py -q && alembic heads`
Expected: PASS（2 passed）；`alembic heads` 输出仅 `phase3c_purchase_order (head)`

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/alembic/versions/20260531_0009_phase3c_purchase_order.py backend/tests/unit/test_purchase_order_migration.py
git commit -m "$(printf 'feat(phase-3c): add alembic migration for purchase order tables\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: RBAC 权限码 + 角色 + 契约测试

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase3c.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_phase3c.py`:
```python
from app import permissions as perms


def test_phase3c_codes_registered():
    for code in ["purchase_order.view", "purchase_order.create",
                 "purchase_order.edit", "purchase_order.delete",
                 "purchase_order.approve"]:
        assert code in perms.ALL_PERMISSIONS


def test_no_duplicate_codes():
    assert len(perms.ALL_PERMISSIONS) == len(set(perms.ALL_PERMISSIONS))


def test_super_admin_wildcard_includes_po():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_po():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["purchase_order.view", "purchase_order.create",
                 "purchase_order.edit", "purchase_order.delete",
                 "purchase_order.approve"]:
        assert code in admin["permissions"]


def test_technician_po_view_only():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "purchase_order.view" in tech["permissions"]
    for denied in ("purchase_order.create", "purchase_order.edit",
                   "purchase_order.delete", "purchase_order.approve"):
        assert denied not in tech["permissions"]


def test_requester_unchanged():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_po_view_only():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "purchase_order.view" in viewer["permissions"]
    assert "purchase_order.approve" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3c.py -q`
Expected: FAIL（purchase_order.* 未注册）

- [ ] **Step 3: 改 `app/permissions.py`**

先 Read 文件定位锚点（3B 已加入 VENDOR/CUSTOMER/COST_CATEGORY）。在 `COST_CATEGORY_MANAGE = "cost_category.manage"` 行之后插入：
```python

# --- 采购单（Phase 3C）---
PURCHASE_ORDER_VIEW = "purchase_order.view"
PURCHASE_ORDER_CREATE = "purchase_order.create"
PURCHASE_ORDER_EDIT = "purchase_order.edit"
PURCHASE_ORDER_DELETE = "purchase_order.delete"
PURCHASE_ORDER_APPROVE = "purchase_order.approve"
```
在 `_COST_CATEGORY = [COST_CATEGORY_VIEW, COST_CATEGORY_MANAGE]` 行之后插入：
```python
_PURCHASE_ORDER = [
    PURCHASE_ORDER_VIEW, PURCHASE_ORDER_CREATE, PURCHASE_ORDER_EDIT,
    PURCHASE_ORDER_DELETE, PURCHASE_ORDER_APPROVE,
]
```
把 `ALL_PERMISSIONS` 聚合表达式末尾追加 `+ _PURCHASE_ORDER`（先 Read 实际表达式，仅在 `+ _VENDOR + _CUSTOMER + _COST_CATEGORY` 之后追加，不丢任何既有组）：
```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE
    + _METER + _READING + _PART + _PART_CATEGORY
    + _VENDOR + _CUSTOMER + _COST_CATEGORY
    + _PURCHASE_ORDER
)
```
在 technician 角色 permissions 列表中，`VENDOR_VIEW, CUSTOMER_VIEW, COST_CATEGORY_VIEW,` 行之后插入：
```python
        PURCHASE_ORDER_VIEW,
```
（admin/super_admin 自动含全部；viewer 自动经 `.endswith(".view")` 含 purchase_order.view；requester 不变；approve 仅 admin/super_admin。）

- [ ] **Step 4: 跑测试确认通过 + 既有契约不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3c.py tests/test_permissions_phase3b.py -q && PYTHONDONTWRITEBYTECODE=1 pytest tests/ -q -k "permission or auth_service or roles"`
Expected: PASS（含 phase3c 新测 + 既有契约测试仍绿）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/permissions.py backend/tests/test_permissions_phase3c.py
git commit -m "$(printf 'feat(phase-3c): add purchase_order permissions + role defaults\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: Pydantic schemas（单文件 purchase_order.py）

**Files:**
- Create: `backend/app/schemas/purchase_order.py`
- Test: `backend/tests/unit/test_purchase_order_schemas.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_schemas.py`:
```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.purchase_order import (
    POLineCreate,
    POLineRead,
    POResolve,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)


def test_create_defaults():
    po = PurchaseOrderCreate(vendor_id="v-1")
    assert po.notes == "" and po.lines == []


def test_create_rejects_blank_vendor():
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(vendor_id="")


def test_line_create_and_default_cost():
    ln = POLineCreate(part_id="p-1", quantity=Decimal("3"))
    assert ln.unit_cost == Decimal("0")


def test_line_read_line_total_computed():
    lr = POLineRead(id="l-1", part_id="p-1", quantity=Decimal("3"),
                    unit_cost=Decimal("2.5"))
    assert lr.line_total == Decimal("7.5")
    assert lr.model_dump()["line_total"] == Decimal("7.5")


def test_update_all_optional():
    assert PurchaseOrderUpdate().model_dump(exclude_unset=True) == {}


def test_resolve_default_note():
    assert POResolve().note == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_schemas.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/schemas/purchase_order.py`:
```python
"""采购单 schema（Phase 3C）。lines/total_cost 由 router 填充。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.purchase_order_status import PurchaseOrderStatus


class POLineCreate(BaseModel):
    part_id: str = Field(min_length=1)
    quantity: Decimal
    unit_cost: Decimal = Decimal("0")


class POLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    part_id: str
    quantity: Decimal
    unit_cost: Decimal

    @computed_field
    @property
    def line_total(self) -> Decimal:
        # 量化到 4 位（与 Numeric(18,4) 一致；避免 scale-8 乘积噪声）
        return (self.quantity * self.unit_cost).quantize(Decimal("0.0001"))


class PurchaseOrderCreate(BaseModel):
    vendor_id: str = Field(min_length=1)
    notes: str = ""
    lines: list[POLineCreate] = []


class PurchaseOrderUpdate(BaseModel):
    vendor_id: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    lines: list[POLineCreate] | None = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    vendor_id: str
    status: PurchaseOrderStatus
    notes: str
    resolution_note: str
    resolved_by_user_id: str | None
    resolved_at: datetime | None
    lines: list[POLineRead] = []
    total_cost: Decimal = Decimal("0")


class PurchaseOrderMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    vendor_id: str
    status: PurchaseOrderStatus


class POActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None
    from_status: str | None
    to_status: str | None
    comment: str
    created_at: datetime


class POResolve(BaseModel):
    note: str = ""
```

> 注：`status` 用 `PurchaseOrderStatus` 枚举类型（镜像既有 `RequestRead.status` 的做法）——`from_attributes` 读出 ORM 枚举值，Pydantic v2 序列化为其 `.value` 字符串（如 `"DRAFT"`），与既有 Request API（`status=="PENDING"`）一致。list 过滤参数 `status="DRAFT"` 为裸字符串，SAEnum 列与之比较成立。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_schemas.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/schemas/purchase_order.py backend/tests/unit/test_purchase_order_schemas.py
git commit -m "$(printf 'feat(phase-3c): add purchase order pydantic schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: purchase_order_service — CRUD + 行全量替换（draft-only）

**Files:**
- Create: `backend/app/services/purchase_order_service.py`
- Test: `backend/tests/unit/test_purchase_order_service_crud.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_service_crud.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import (
    POLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services import purchase_order_service as svc

CO = "co-1"


def _payload(**kw):
    kw.setdefault("vendor_id", "v-1")
    return PurchaseOrderCreate(**kw)


def test_create_assigns_custom_id_and_lines(db: Session):
    po = svc.create_purchase_order(db, _payload(lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("3"), unit_cost=Decimal("2")),
        POLineCreate(part_id="p-2", quantity=Decimal("1")),
    ]), CO, actor_user_id="a")
    assert po.custom_id.startswith("PO") and po.status == PurchaseOrderStatus.DRAFT
    assert [ln.part_id for ln in svc.lines(db, po.id)] == ["p-1", "p-2"]


def test_list_and_filters(db: Session):
    svc.create_purchase_order(db, _payload(vendor_id="v-1"), CO, actor_user_id="a")
    svc.create_purchase_order(db, _payload(vendor_id="v-2"), CO, actor_user_id="a")
    assert len(svc.list_purchase_orders(db)) == 2
    got = svc.list_purchase_orders(db, vendor_id="v-2")
    assert len(got) == 1 and got[0].vendor_id == "v-2"
    drafts = svc.list_purchase_orders(db, status="DRAFT")
    assert len(drafts) == 2


def test_get_soft_deleted_hidden(db: Session):
    po = svc.create_purchase_order(db, _payload(), CO, actor_user_id="a")
    svc.delete_purchase_order(db, po)
    assert svc.get_purchase_order(db, po.id) is None


def test_update_draft_replaces_lines_and_scalars(db: Session):
    po = svc.create_purchase_order(db, _payload(notes="old", lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("1"))]), CO, actor_user_id="a")
    svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="new", lines=[
        POLineCreate(part_id="p-9", quantity=Decimal("2"), unit_cost=Decimal("4"))]),
        CO, actor_user_id="a")
    assert po.notes == "new"
    lines = svc.lines(db, po.id)
    assert len(lines) == 1 and lines[0].part_id == "p-9"


def test_update_keeps_lines_when_omitted(db: Session):
    po = svc.create_purchase_order(db, _payload(lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("1"))]), CO, actor_user_id="a")
    svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="x"), CO, actor_user_id="a")
    assert len(svc.lines(db, po.id)) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_crud.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/purchase_order_service.py`:
```python
"""采购单服务：CRUD（软删）、行全量替换（draft-only）、状态机、审批入库。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.part import Part
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_status import PurchaseOrderStatus, can_transition
from app.schemas.purchase_order import (
    POLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services import sequence_service


def _log(db: Session, purchase_order_id: str, company_id: str, activity_type: str,
         actor_user_id: str | None = None, from_status: str | None = None,
         to_status: str | None = None, comment: str = "") -> None:
    db.add(PurchaseOrderActivity(
        purchase_order_id=purchase_order_id, company_id=company_id,
        activity_type=activity_type, actor_user_id=actor_user_id,
        from_status=from_status, to_status=to_status, comment=comment,
    ))


def lines(db: Session, purchase_order_id: str) -> list[PurchaseOrderLine]:
    return list(db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
        .order_by(PurchaseOrderLine.id)).scalars().all())


def _set_lines(db: Session, purchase_order_id: str, company_id: str,
               line_list: list[POLineCreate]) -> None:
    for ln in line_list:
        db.add(PurchaseOrderLine(
            purchase_order_id=purchase_order_id, part_id=ln.part_id,
            quantity=ln.quantity, unit_cost=ln.unit_cost, company_id=company_id,
        ))


def create_purchase_order(db: Session, payload: PurchaseOrderCreate, company_id: str,
                          actor_user_id: str | None) -> PurchaseOrder:
    seq = sequence_service.next_value(db, "purchase_order", company_id)
    po = PurchaseOrder(
        custom_id=sequence_service.format_custom_id("PO", seq),
        vendor_id=payload.vendor_id, notes=payload.notes, company_id=company_id,
    )
    db.add(po)
    db.flush()
    _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def list_purchase_orders(db: Session, *, status: str | None = None,
                         vendor_id: str | None = None) -> list[PurchaseOrder]:
    stmt = select(PurchaseOrder).where(PurchaseOrder.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(PurchaseOrder.status == status)
    if vendor_id is not None:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    return list(db.execute(stmt.order_by(PurchaseOrder.custom_id)).scalars().all())


def get_purchase_order(db: Session, purchase_order_id: str) -> PurchaseOrder | None:
    po = db.get(PurchaseOrder, purchase_order_id)
    if po is None or not po.is_active:
        return None
    return po


def _assert_draft(po: PurchaseOrder) -> None:
    if po.status != PurchaseOrderStatus.DRAFT:
        raise bad_request("PURCHASE_ORDER_NOT_DRAFT", "采购单非草稿，不可编辑")


def update_purchase_order(db: Session, po: PurchaseOrder, payload: PurchaseOrderUpdate,
                          company_id: str, actor_user_id: str | None) -> PurchaseOrder:
    _assert_draft(po)
    data = payload.model_dump(exclude_unset=True)
    data.pop("lines", None)
    for k, v in data.items():
        setattr(po, k, v)
    if payload.lines is not None:
        db.execute(PurchaseOrderLine.__table__.delete().where(
            PurchaseOrderLine.purchase_order_id == po.id))
        _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def delete_purchase_order(db: Session, po: PurchaseOrder) -> None:
    po.is_active = False
    po.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_crud.py -q`
Expected: PASS（5 passed）

> 注：`test_update_only_in_draft`（非草稿编辑报错）的覆盖在 Task 7 提交后补全；本 task 仅覆盖 CRUD 与行替换。`_assert_draft` 已实现，Task 7 的 submit 会产生非 DRAFT 态供其断言。

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/purchase_order_service.py backend/tests/unit/test_purchase_order_service_crud.py
git commit -m "$(printf 'feat(phase-3c): add purchase order service CRUD + line replacement\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: service 状态转移 — submit / reject / cancel + 活动时间线

**Files:**
- Modify: `backend/app/services/purchase_order_service.py`（追加函数）
- Test: `backend/tests/unit/test_purchase_order_service_transitions.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_service_transitions.py`:
```python
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import POLineCreate, PurchaseOrderCreate, PurchaseOrderUpdate
from app.services import purchase_order_service as svc

CO = "co-1"


def _po_with_line(db):
    return svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1", lines=[
        POLineCreate(part_id="p-1", quantity=Decimal("1"))]), CO, actor_user_id="a")


def test_submit_requires_lines(db: Session):
    empty = svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1"),
                                      CO, actor_user_id="a")
    with pytest.raises(HTTPException):
        svc.submit_purchase_order(db, empty, CO, actor_user_id="a")


def test_submit_moves_to_submitted_and_logs(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.SUBMITTED
    acts = svc.list_activities(db, po.id)
    assert acts[-1].activity_type == "STATUS_CHANGE"
    assert acts[-1].to_status == "SUBMITTED"


def test_update_blocked_after_submit(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    with pytest.raises(HTTPException):
        svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="x"),
                                  CO, actor_user_id="a")


def test_reject_from_submitted(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    svc.reject_purchase_order(db, po, "no budget", CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.REJECTED
    assert po.resolution_note == "no budget" and po.resolved_by_user_id == "a"


def test_cancel_from_draft(db: Session):
    po = _po_with_line(db)
    svc.cancel_purchase_order(db, po, "mistake", CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.CANCELED


def test_illegal_transition_rejected(db: Session):
    po = _po_with_line(db)  # DRAFT
    with pytest.raises(HTTPException):
        svc.reject_purchase_order(db, po, "", CO, actor_user_id="a")  # DRAFT->REJECTED illegal
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_transitions.py -q`
Expected: FAIL（submit_purchase_order 等未定义）

- [ ] **Step 3: 追加实现到 `app/services/purchase_order_service.py`**

在文件末尾（`delete_purchase_order` 之后）追加：
```python
def list_activities(db: Session, purchase_order_id: str) -> list[PurchaseOrderActivity]:
    return list(db.execute(
        select(PurchaseOrderActivity)
        .where(PurchaseOrderActivity.purchase_order_id == purchase_order_id)
        .order_by(PurchaseOrderActivity.created_at, PurchaseOrderActivity.id)
    ).scalars().all())


def submit_purchase_order(db: Session, po: PurchaseOrder, company_id: str,
                          actor_user_id: str | None) -> PurchaseOrder:
    if not can_transition(po.status, PurchaseOrderStatus.SUBMITTED):
        raise bad_request("PURCHASE_ORDER_BAD_TRANSITION",
                          f"非法状态转移 {po.status.value}->SUBMITTED")
    if not lines(db, po.id):
        raise bad_request("PURCHASE_ORDER_EMPTY", "采购单无明细行，不可提交")
    from_status = po.status.value
    po.status = PurchaseOrderStatus.SUBMITTED
    _log(db, po.id, company_id, "STATUS_CHANGE", actor_user_id=actor_user_id,
         from_status=from_status, to_status=PurchaseOrderStatus.SUBMITTED.value)
    db.commit()
    db.refresh(po)
    return po


def _resolve(db: Session, po: PurchaseOrder, dst: PurchaseOrderStatus, note: str,
             company_id: str, actor_user_id: str | None) -> PurchaseOrder:
    if not can_transition(po.status, dst):
        raise bad_request("PURCHASE_ORDER_BAD_TRANSITION",
                          f"非法状态转移 {po.status.value}->{dst.value}")
    from_status = po.status.value
    po.status = dst
    po.resolution_note = note
    po.resolved_by_user_id = actor_user_id
    po.resolved_at = utcnow()
    _log(db, po.id, company_id, "STATUS_CHANGE", actor_user_id=actor_user_id,
         from_status=from_status, to_status=dst.value, comment=note)
    db.commit()
    db.refresh(po)
    return po


def reject_purchase_order(db: Session, po: PurchaseOrder, note: str, company_id: str,
                          actor_user_id: str | None) -> PurchaseOrder:
    return _resolve(db, po, PurchaseOrderStatus.REJECTED, note, company_id, actor_user_id)


def cancel_purchase_order(db: Session, po: PurchaseOrder, note: str, company_id: str,
                          actor_user_id: str | None) -> PurchaseOrder:
    return _resolve(db, po, PurchaseOrderStatus.CANCELED, note, company_id, actor_user_id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_transitions.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/purchase_order_service.py backend/tests/unit/test_purchase_order_service_transitions.py
git commit -m "$(printf 'feat(phase-3c): add purchase order submit/reject/cancel transitions + activity log\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: service approve — 整单入库回写 Part.quantity

**Files:**
- Modify: `backend/app/services/purchase_order_service.py`（追加 approve）
- Test: `backend/tests/unit/test_purchase_order_service_approve.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_purchase_order_service_approve.py`:
```python
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import POLineCreate, PurchaseOrderCreate
from app.services import purchase_order_service as svc

CO = "co-1"


def _part(db, *, qty="0", non_stock=False, cost="0"):
    p = Part(custom_id="PRT000001", name="x", quantity=Decimal(qty),
             non_stock=non_stock, cost=Decimal(cost), company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _submit(db, lines):
    po = svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1", lines=lines),
                                   CO, actor_user_id="a")
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    return po


def test_approve_writes_back_stock(db: Session):
    p1 = _part(db, qty="10")
    p2 = _part(db, qty="5", non_stock=True)
    po = _submit(db, [
        POLineCreate(part_id=p1.id, quantity=Decimal("3"), unit_cost=Decimal("2")),
        POLineCreate(part_id=p2.id, quantity=Decimal("4")),
    ])
    svc.approve_purchase_order(db, po, "ok", CO, actor_user_id="a")
    db.refresh(p1)
    db.refresh(p2)
    assert po.status == PurchaseOrderStatus.APPROVED
    assert p1.quantity == Decimal("13")   # 10 + 3
    assert p2.quantity == Decimal("5")    # non_stock 不增
    acts = [a.activity_type for a in svc.list_activities(db, po.id)]
    assert "RECEIVED" in acts


def test_double_approve_blocked_writes_once(db: Session):
    p1 = _part(db, qty="10")
    po = _submit(db, [POLineCreate(part_id=p1.id, quantity=Decimal("3"))])
    svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    with pytest.raises(HTTPException):
        svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    db.refresh(p1)
    assert p1.quantity == Decimal("13")   # 仅回写一次


def test_approve_requires_submitted(db: Session):
    p1 = _part(db, qty="10")
    po = svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1", lines=[
        POLineCreate(part_id=p1.id, quantity=Decimal("3"))]), CO, actor_user_id="a")
    with pytest.raises(HTTPException):   # DRAFT->APPROVED 非法
        svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    db.refresh(p1)
    assert p1.quantity == Decimal("10")  # 未变
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_approve.py -q`
Expected: FAIL（approve_purchase_order 未定义）

- [ ] **Step 3: 追加 approve 到 `app/services/purchase_order_service.py`**

在文件末尾追加：
```python
def approve_purchase_order(db: Session, po: PurchaseOrder, note: str, company_id: str,
                           actor_user_id: str | None) -> PurchaseOrder:
    """审批通过=整单入库：逐行把数量加回 Part.quantity（non_stock 跳过、不报错）。

    终态守卫（can_transition）保证库存恰好回写一次；单次 commit。
    """
    if not can_transition(po.status, PurchaseOrderStatus.APPROVED):
        raise bad_request("PURCHASE_ORDER_BAD_TRANSITION",
                          f"非法状态转移 {po.status.value}->APPROVED")
    for ln in lines(db, po.id):
        part = db.get(Part, ln.part_id)
        if part is not None and part.is_active and not part.non_stock:
            part.quantity = part.quantity + ln.quantity
    from_status = po.status.value
    po.status = PurchaseOrderStatus.APPROVED
    po.resolution_note = note
    po.resolved_by_user_id = actor_user_id
    po.resolved_at = utcnow()
    _log(db, po.id, company_id, "STATUS_CHANGE", actor_user_id=actor_user_id,
         from_status=from_status, to_status=PurchaseOrderStatus.APPROVED.value, comment=note)
    _log(db, po.id, company_id, "RECEIVED", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(po)
    return po
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_purchase_order_service_approve.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/purchase_order_service.py backend/tests/unit/test_purchase_order_service_approve.py
git commit -m "$(printf 'feat(phase-3c): add purchase order approve with stock write-back\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: purchase_orders router — CRUD + mini + main 挂载

**Files:**
- Create: `backend/app/routers/purchase_orders.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_purchase_order_api_crud.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_purchase_order_api_crud.py`:
```python
"""采购单 API CRUD（Phase 3C）。"""
from __future__ import annotations

from decimal import Decimal


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _vendor_id(client, t, name="供应商A"):
    return client.post("/api/v1/vendors", json={"name": name}, headers=_h(t)).json()["id"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"},
                       headers=_h(t)).json()["id"]


def test_po_crud_and_lines(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    p = _part_id(client, t)
    r = client.post("/api/v1/purchase-orders", json={
        "vendor_id": v, "notes": "n",
        "lines": [{"part_id": p, "quantity": "3", "unit_cost": "2"}]}, headers=_h(t))
    assert r.status_code == 201, r.text
    body = r.json()
    pid = body["id"]
    assert body["custom_id"].startswith("PO") and body["status"] == "DRAFT"
    # Decimal 序列化格式（字符串/数字）无关紧要：按值比较
    assert Decimal(str(body["lines"][0]["line_total"])) == Decimal("6")
    assert Decimal(str(body["total_cost"])) == Decimal("6")
    got = client.get(f"/api/v1/purchase-orders/{pid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["vendor_id"] == v
    upd = client.patch(f"/api/v1/purchase-orders/{pid}", json={"notes": "n2", "lines": []},
                       headers=_h(t))
    assert upd.json()["notes"] == "n2" and upd.json()["lines"] == []
    assert client.delete(f"/api/v1/purchase-orders/{pid}", headers=_h(t)).status_code == 204


def test_po_list_filter_by_vendor(client):
    t = _admin(client)
    v1, v2 = _vendor_id(client, t, "V1"), _vendor_id(client, t, "V2")
    client.post("/api/v1/purchase-orders", json={"vendor_id": v1}, headers=_h(t))
    client.post("/api/v1/purchase-orders", json={"vendor_id": v2}, headers=_h(t))
    got = client.get(f"/api/v1/purchase-orders?vendor_id={v1}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["vendor_id"] == v1


def test_po_mini(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(t))
    mini = client.get("/api/v1/purchase-orders/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "custom_id", "vendor_id", "status"}


def test_po_tenant_isolation(client):
    a = _admin(client)
    v = _vendor_id(client, a)
    pid = client.post("/api/v1/purchase-orders", json={"vendor_id": v},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/purchase-orders/{pid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_purchase_order_api_crud.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/purchase_orders.py`:
```python
"""采购单 API（/api/v1/purchase-orders）。"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.purchase_order import (
    POLineRead,
    PurchaseOrderCreate,
    PurchaseOrderMini,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from app.services import purchase_order_service as svc

router = APIRouter(prefix="/api/v1/purchase-orders", tags=["purchase-orders"])


def _ensure(po: PurchaseOrder | None, company_id: str) -> PurchaseOrder:
    if po is None or po.company_id != company_id:
        raise not_found("PURCHASE_ORDER_NOT_FOUND", "采购单不存在")
    return po


def _read(db: Session, po: PurchaseOrder) -> PurchaseOrderRead:
    data = PurchaseOrderRead.model_validate(po)
    line_reads = [POLineRead.model_validate(ln) for ln in svc.lines(db, po.id)]
    data.lines = line_reads
    data.total_cost = sum((lr.line_total for lr in line_reads), Decimal("0"))
    return data


@router.get("", response_model=list[PurchaseOrderRead])
def list_purchase_orders(status: str | None = None, vendor_id: str | None = None,
                         db: Session = Depends(get_db),
                         current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW))):
    return [_read(db, po) for po in svc.list_purchase_orders(db, status=status, vendor_id=vendor_id)]


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_CREATE))):
    po = svc.create_purchase_order(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


# 注：/mini 必须注册在 /{po_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[PurchaseOrderMini])
def list_purchase_orders_mini(db: Session = Depends(get_db),
                              current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW))):
    return svc.list_purchase_orders(db)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(po_id: str, db: Session = Depends(get_db),
                       current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    return _read(db, po)


@router.patch("/{po_id}", response_model=PurchaseOrderRead)
def update_purchase_order(po_id: str, payload: PurchaseOrderUpdate, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.update_purchase_order(db, po, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_order(po_id: str, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_DELETE))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.delete_purchase_order(db, po)
```

> 注：状态动作端点（submit/approve/reject/cancel/activities）在 Task 10 追加；本 task 仅 CRUD + mini。

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `customers,` 行之后插入一行：
```python
    purchase_orders,
```
在 `app.include_router(customers.router)` 行之后插入：
```python
app.include_router(purchase_orders.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_purchase_order_api_crud.py -q && python -c "import app.main"`
Expected: PASS（4 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/purchase_orders.py backend/app/main.py backend/tests/test_purchase_order_api_crud.py
git commit -m "$(printf 'feat(phase-3c): add purchase-orders router (CRUD + mini) + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: router 状态动作端点 — submit/approve/reject/cancel/activities + RBAC

**Files:**
- Modify: `backend/app/routers/purchase_orders.py`（追加 5 个动作端点 + 扩充 schema import）
- Test: `backend/tests/test_purchase_order_api_actions.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_purchase_order_api_actions.py`:
```python
"""采购单 API 状态动作 + RBAC（Phase 3C）。"""
from __future__ import annotations

from decimal import Decimal


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


def _vendor_id(client, t):
    return client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(t)).json()["id"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "10"},
                       headers=_h(t)).json()["id"]


def _draft_with_line(client, t):
    v, p = _vendor_id(client, t), _part_id(client, t)
    return client.post("/api/v1/purchase-orders", json={
        "vendor_id": v, "lines": [{"part_id": p, "quantity": "3", "unit_cost": "2"}]},
        headers=_h(t)).json(), p


def test_submit_then_approve_writes_back_stock(client):
    t = _admin(client)
    po, p = _draft_with_line(client, t)
    pid = po["id"]
    assert client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t)).json()["status"] == "SUBMITTED"
    appr = client.post(f"/api/v1/purchase-orders/{pid}/approve", json={"note": "ok"}, headers=_h(t))
    assert appr.status_code == 200 and appr.json()["status"] == "APPROVED"
    # 库存 10 + 3 = 13（Decimal 按值比较，序列化格式无关）
    assert Decimal(str(client.get(f"/api/v1/parts/{p}", headers=_h(t)).json()["quantity"])) == Decimal("13")
    acts = client.get(f"/api/v1/purchase-orders/{pid}/activities", headers=_h(t)).json()
    assert any(a["activity_type"] == "RECEIVED" for a in acts)


def test_submit_empty_400(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    pid = client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(t)).json()["id"]
    assert client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t)).status_code == 400


def test_reject_and_cancel(client):
    t = _admin(client)
    po, _ = _draft_with_line(client, t)
    pid = po["id"]
    client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t))
    assert client.post(f"/api/v1/purchase-orders/{pid}/reject", json={"note": "x"},
                       headers=_h(t)).json()["status"] == "REJECTED"
    po2, _ = _draft_with_line(client, t)
    assert client.post(f"/api/v1/purchase-orders/{po2['id']}/cancel", json={"note": "x"},
                       headers=_h(t)).json()["status"] == "CANCELED"


def test_technician_view_only(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    v = _vendor_id(client, admin)
    pid = client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(admin)).json()["id"]
    assert client.get("/api/v1/purchase-orders", headers=_h(tech)).status_code == 200
    assert client.post("/api/v1/purchase-orders", json={"vendor_id": v},
                       headers=_h(tech)).status_code == 403


def test_technician_cannot_approve(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    v = _vendor_id(client, admin)
    p = _part_id(client, admin)
    pid = client.post("/api/v1/purchase-orders", json={
        "vendor_id": v, "lines": [{"part_id": p, "quantity": "1"}]}, headers=_h(admin)).json()["id"]
    client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(admin))
    assert client.post(f"/api/v1/purchase-orders/{pid}/approve", json={"note": ""},
                       headers=_h(tech)).status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_purchase_order_api_actions.py -q`
Expected: FAIL（动作端点尚未挂载 → 404/405）

- [ ] **Step 3: 追加动作端点到 `app/routers/purchase_orders.py`**

先扩充 schema import（在现有 `from app.schemas.purchase_order import (...)` 块内加入 `POActivityRead,` 与 `POResolve,`）：
```python
from app.schemas.purchase_order import (
    POActivityRead,
    POLineRead,
    POResolve,
    PurchaseOrderCreate,
    PurchaseOrderMini,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
```
在文件末尾（`delete_purchase_order` 之后）追加 5 个端点：
```python
@router.post("/{po_id}/submit", response_model=PurchaseOrderRead)
def submit_purchase_order(po_id: str, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.submit_purchase_order(db, po, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
def approve_purchase_order(po_id: str, payload: POResolve, db: Session = Depends(get_db),
                           current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_APPROVE))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.approve_purchase_order(db, po, payload.note, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.post("/{po_id}/reject", response_model=PurchaseOrderRead)
def reject_purchase_order(po_id: str, payload: POResolve, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_APPROVE))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.reject_purchase_order(db, po, payload.note, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
def cancel_purchase_order(po_id: str, payload: POResolve, db: Session = Depends(get_db),
                          current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.cancel_purchase_order(db, po, payload.note, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.get("/{po_id}/activities", response_model=list[POActivityRead])
def list_purchase_order_activities(po_id: str, db: Session = Depends(get_db),
                                   current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW))):
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    return svc.list_activities(db, po.id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_purchase_order_api_actions.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/purchase_orders.py backend/tests/test_purchase_order_api_actions.py
git commit -m "$(printf 'feat(phase-3c): add purchase order action endpoints (submit/approve/reject/cancel/activities)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: 全量回归 + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/po_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 900 + 新增；0 failed）。Read tee 文件确认真实摘要行（防陈旧回放）。

- [ ] **Step 2: 确认工作树与提交链干净**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git status --porcelain && git log --oneline -11
```
Expected: porcelain 为空；最近提交含 Task 1–10 各一次。

- [ ] **Step 3: alembic 单 head 校验 + Atlas 扫描**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && grep -ric atlas backend/app/models/purchase_order.py backend/app/models/purchase_order_status.py backend/app/schemas/purchase_order.py backend/app/services/purchase_order_service.py backend/app/routers/purchase_orders.py backend/alembic/versions/20260531_0009_phase3c_purchase_order.py
```
Expected: `alembic heads` 仅 `phase3c_purchase_order (head)`；Atlas 计数全 0。

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含新增 PO 单测 + API 测 + 契约/迁移测）。
- `tb_purchase_order` / `tb_purchase_order_line` / `tb_purchase_order_activity` 三表经迁移可 upgrade/downgrade。
- `/purchase-orders` 全套端点工作；状态机 DRAFT→SUBMITTED→APPROVED|REJECTED|CANCELED 守卫正确；approve 整单入库回写 `Part.quantity`（普通增、non_stock 不增、恰回写一次、Part.cost 不变）；submit 空单 400；非 DRAFT 编辑 400；`/mini`；technician 只读、非 admin 不能 approve；跨租户隔离 404。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净，alembic 单 head `phase3c_purchase_order`。
