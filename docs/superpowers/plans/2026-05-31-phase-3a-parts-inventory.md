# Phase 3A 备件 · 库存 · 消耗 · 套件 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现备件库存核心闭环：Part/PartCategory/PartConsumption/MultiParts 实体 + 挂工单消耗（扣库存、不足报错、成本快照台账）+ 低库存标识 + 套件分组，配套 CRUD/消耗 API 与 RBAC。

**Architecture:** 与 2A/2B/2C 同构的分层（model/schema/service/router）。库存领域 CRUD + 与工单执行的消耗集成：消耗端点嵌在 work-orders 路径下但独立 router，请求内单次 commit（不调用内部 commit 的工单服务，无 2C partial-commit 风险）。Service 拆四文件（part / part_category / multi_part / part_consumption）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · SQLite(测试)/MySQL(生产) · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`__init__.py`/`main.py`/`permissions.py`）一律用 Edit 精确替换，禁 sed/re.sub
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`
- 新文件务必 `git add` 后再提交
- 复用既有签名：`sequence_service.next_value(db, scope, company_id)`、`sequence_service.format_custom_id(prefix, value, digits=6)`；`bad_request(code,msg)`/`not_found(code,msg)`（均 raise HTTPException）；`work_order_service.get_work_order(db, work_order_id)->WorkOrder|None`；`app.models.base.utcnow`、`DATETIME6`；`app.deps.get_db`、`require_permission(code)`
- 基线：全量 pytest 807 passed，alembic 单 head `phase2c_meter`。

---

## Task 1: Part/PartCategory/PartConsumption/MultiPart ORM 模型（8 张表）+ 注册

**Files:**
- Create: `backend/app/models/part_category.py`（PartCategory）
- Create: `backend/app/models/part.py`（Part + PartAssignee + PartTeam + PartAsset）
- Create: `backend/app/models/part_consumption.py`（PartConsumption）
- Create: `backend/app/models/multi_part.py`（MultiPart + MultiPartItem）
- Modify: `backend/app/models/__init__.py`（import 区 + `__all__`）
- Test: `backend/tests/unit/test_part_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_part_models.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.part import Part, PartAssignee, PartTeam, PartAsset
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.models.multi_part import MultiPart, MultiPartItem


def test_part_row_and_low_stock(db: Session):
    cat = PartCategory(name="轴承", company_id="co-1")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    p = Part(custom_id="PRT000001", name="6204 轴承", cost=Decimal("12.5000"),
             quantity=Decimal("3.0000"), min_quantity=Decimal("5.0000"),
             unit="pcs", category_id=cat.id, company_id="co-1")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.id and p.is_active is True and p.non_stock is False
    assert p.is_low_stock is True                         # 3 < 5 且计库存
    p.quantity = Decimal("10.0000")
    assert p.is_low_stock is False                        # 10 >= 5
    p.non_stock = True
    p.quantity = Decimal("0.0000")
    assert p.is_low_stock is False                        # non_stock 永不低库存
    db.add(PartAssignee(part_id=p.id, user_id="u-1", company_id="co-1"))
    db.add(PartTeam(part_id=p.id, team_id="t-1", company_id="co-1"))
    db.add(PartAsset(part_id=p.id, asset_id="as-1", company_id="co-1"))
    db.commit()


def test_consumption_and_multipart(db: Session):
    p = Part(custom_id="PRT000002", name="滤芯", company_id="co-1")
    db.add(p)
    db.commit()
    db.refresh(p)
    db.add(PartConsumption(part_id=p.id, work_order_id="wo-1",
                           quantity=Decimal("2.0000"), unit_cost=Decimal("9.9900"),
                           company_id="co-1"))
    mp = MultiPart(custom_id="KIT000001", name="保养套件", company_id="co-1")
    db.add(mp)
    db.commit()
    db.refresh(mp)
    db.add(MultiPartItem(multi_part_id=mp.id, part_id=p.id, company_id="co-1"))
    db.commit()
    c = db.query(PartConsumption).filter_by(part_id=p.id).one()
    assert c.consumed_at is not None                      # default utcnow


def test_part_exports_registered():
    import app.models as mod
    for name in ("Part", "PartAssignee", "PartTeam", "PartAsset",
                 "PartCategory", "PartConsumption", "MultiPart", "MultiPartItem"):
        assert name in mod.__all__ and hasattr(mod, name)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_models.py -q`
Expected: FAIL（ModuleNotFoundError: app.models.part_category）

- [ ] **Step 3: 写 PartCategory 模型**

`backend/app/models/part_category.py`:
```python
"""备件分类（每租户）。镜像 AssetCategory。"""
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


class PartCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_part_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_part_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 4: 写 Part + 关联表模型**

`backend/app/models/part.py`:
```python
"""备件（Part，每租户）+ M:N 关联（指派人/团队/资产）。

cost/quantity/min_quantity 用 Numeric(18,4) 避免浮点漂移。is_low_stock 为计算
属性（非列）：计库存且 quantity<min_quantity。non_stock 备件永不低库存。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Part(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_part"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    min_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    unit: Mapped[str] = mapped_column(String(50), default="", server_default="")
    barcode: Mapped[str | None] = mapped_column(String(120), default=None)
    non_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_part_category.id", ondelete="SET NULL"), index=True
    )

    @property
    def is_low_stock(self) -> bool:
        return (not self.non_stock) and (self.quantity < self.min_quantity)


class PartAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_assignee"
    __table_args__ = (
        UniqueConstraint("part_id", "user_id", name="uq_part_assignee"),
    )

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class PartTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_team"
    __table_args__ = (
        UniqueConstraint("part_id", "team_id", name="uq_part_team"),
    )

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )


class PartAsset(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_asset"
    __table_args__ = (
        UniqueConstraint("part_id", "asset_id", name="uq_part_asset"),
    )

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 5: 写 PartConsumption 模型**

`backend/app/models/part_consumption.py`:
```python
"""备件消耗台账（每租户，append-only 不软删，审计性质）。

挂工单消耗：扣库存（non_stock 除外）并定格 unit_cost 单价快照。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
    utcnow,
)


class PartConsumption(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_part_consumption"

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="RESTRICT"), index=True
    )
    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    consumed_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    consumed_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
```

- [ ] **Step 6: 写 MultiPart + 成员表模型**

`backend/app/models/multi_part.py`:
```python
"""多备件套件（MultiParts，每租户）。纯分组，无自身库存、无消耗行为。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class MultiPart(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_multi_part"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class MultiPartItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_multi_part_item"
    __table_args__ = (
        UniqueConstraint("multi_part_id", "part_id", name="uq_multi_part_item"),
    )

    multi_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_multi_part.id", ondelete="CASCADE"), index=True
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_part.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 7: 注册到 `app/models/__init__.py`**

先 Read 文件定位锚点。在 import 区 `from app.models.meter_trigger import MeterTrigger, MeterTriggerAssignee, MeterTriggerTeam` 行之后插入：
```python
from app.models.part_category import PartCategory
from app.models.part import Part, PartAssignee, PartTeam, PartAsset
from app.models.part_consumption import PartConsumption
from app.models.multi_part import MultiPart, MultiPartItem
```
在 `__all__` 列表中 `"MeterTriggerTeam",` 行之后插入：
```python
    "PartCategory",
    "Part",
    "PartAssignee",
    "PartTeam",
    "PartAsset",
    "PartConsumption",
    "MultiPart",
    "MultiPartItem",
```

- [ ] **Step 8: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_models.py -q && python -c "import app.models; import app.main"`
Expected: PASS（3 passed）+ 无导入错误

- [ ] **Step 9: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/part_category.py backend/app/models/part.py backend/app/models/part_consumption.py backend/app/models/multi_part.py backend/app/models/__init__.py backend/tests/unit/test_part_models.py
git commit -m "$(printf 'feat(phase-3a): add Part/PartCategory/PartConsumption/MultiPart ORM models\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/20260531_0007_phase3a_part.py`
- Test: `backend/tests/unit/test_part_migration.py`

- [ ] **Step 1: 写失败测试（upgrade/downgrade 在 SQLite 往返）**

`backend/tests/unit/test_part_migration.py`:
```python
import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0007_phase3a_part")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase3a_part"
    assert m.down_revision == "phase2c_meter"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_team (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_part", "tb_part_category", "tb_part_consumption",
                "tb_multi_part", "tb_multi_part_item",
                "tb_part_assignee", "tb_part_team", "tb_part_asset",
            } <= tables
            _mod().downgrade()
            assert "tb_part" not in inspect(conn).get_table_names()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_migration.py -q`
Expected: FAIL（ModuleNotFoundError: 迁移模块不存在）

- [ ] **Step 3: 写迁移**

`backend/alembic/versions/20260531_0007_phase3a_part.py`:
```python
"""phase3a part: part + part_category + part_consumption + multi_part(+item) + part assoc tables

Revision ID: phase3a_part
Revises: phase2c_meter
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3a_part"
down_revision: str | Sequence[str] | None = "phase2c_meter"
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
        "tb_part_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_part_category_company_name"),
    )
    op.create_index("ix_tb_part_category_company_id", "tb_part_category", ["company_id"])

    op.create_table(
        "tb_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("min_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(50), nullable=False, server_default=""),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("non_stock", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("category_id", sa.String(36),
                  sa.ForeignKey("tb_part_category.id", ondelete="SET NULL"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_part_company_id", "tb_part", ["company_id"])
    op.create_index("ix_tb_part_category_id", "tb_part", ["category_id"])

    op.create_table(
        "tb_part_consumption",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("consumed_by_user_id", sa.String(36), nullable=True),
        sa.Column("consumed_at", DATETIME6, nullable=False),
        *_ts(),
    )
    op.create_index("ix_tb_part_consumption_company_id", "tb_part_consumption", ["company_id"])
    op.create_index("ix_tb_part_consumption_part_id", "tb_part_consumption", ["part_id"])
    op.create_index("ix_tb_part_consumption_work_order_id", "tb_part_consumption", ["work_order_id"])

    op.create_table(
        "tb_multi_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_multi_part_company_id", "tb_multi_part", ["company_id"])

    op.create_table(
        "tb_multi_part_item",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("multi_part_id", sa.String(36),
                  sa.ForeignKey("tb_multi_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("multi_part_id", "part_id", name="uq_multi_part_item"),
    )
    op.create_index("ix_tb_multi_part_item_company_id", "tb_multi_part_item", ["company_id"])
    op.create_index("ix_tb_multi_part_item_multi_part_id", "tb_multi_part_item", ["multi_part_id"])
    op.create_index("ix_tb_multi_part_item_part_id", "tb_multi_part_item", ["part_id"])

    op.create_table(
        "tb_part_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "user_id", name="uq_part_assignee"),
    )
    op.create_index("ix_tb_part_assignee_company_id", "tb_part_assignee", ["company_id"])
    op.create_index("ix_tb_part_assignee_part_id", "tb_part_assignee", ["part_id"])
    op.create_index("ix_tb_part_assignee_user_id", "tb_part_assignee", ["user_id"])

    op.create_table(
        "tb_part_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "team_id", name="uq_part_team"),
    )
    op.create_index("ix_tb_part_team_company_id", "tb_part_team", ["company_id"])
    op.create_index("ix_tb_part_team_part_id", "tb_part_team", ["part_id"])
    op.create_index("ix_tb_part_team_team_id", "tb_part_team", ["team_id"])

    op.create_table(
        "tb_part_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "asset_id", name="uq_part_asset"),
    )
    op.create_index("ix_tb_part_asset_company_id", "tb_part_asset", ["company_id"])
    op.create_index("ix_tb_part_asset_part_id", "tb_part_asset", ["part_id"])
    op.create_index("ix_tb_part_asset_asset_id", "tb_part_asset", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_tb_part_asset_asset_id", table_name="tb_part_asset")
    op.drop_index("ix_tb_part_asset_part_id", table_name="tb_part_asset")
    op.drop_index("ix_tb_part_asset_company_id", table_name="tb_part_asset")
    op.drop_table("tb_part_asset")
    op.drop_index("ix_tb_part_team_team_id", table_name="tb_part_team")
    op.drop_index("ix_tb_part_team_part_id", table_name="tb_part_team")
    op.drop_index("ix_tb_part_team_company_id", table_name="tb_part_team")
    op.drop_table("tb_part_team")
    op.drop_index("ix_tb_part_assignee_user_id", table_name="tb_part_assignee")
    op.drop_index("ix_tb_part_assignee_part_id", table_name="tb_part_assignee")
    op.drop_index("ix_tb_part_assignee_company_id", table_name="tb_part_assignee")
    op.drop_table("tb_part_assignee")
    op.drop_index("ix_tb_multi_part_item_part_id", table_name="tb_multi_part_item")
    op.drop_index("ix_tb_multi_part_item_multi_part_id", table_name="tb_multi_part_item")
    op.drop_index("ix_tb_multi_part_item_company_id", table_name="tb_multi_part_item")
    op.drop_table("tb_multi_part_item")
    op.drop_index("ix_tb_multi_part_company_id", table_name="tb_multi_part")
    op.drop_table("tb_multi_part")
    op.drop_index("ix_tb_part_consumption_work_order_id", table_name="tb_part_consumption")
    op.drop_index("ix_tb_part_consumption_part_id", table_name="tb_part_consumption")
    op.drop_index("ix_tb_part_consumption_company_id", table_name="tb_part_consumption")
    op.drop_table("tb_part_consumption")
    op.drop_index("ix_tb_part_category_id", table_name="tb_part")
    op.drop_index("ix_tb_part_company_id", table_name="tb_part")
    op.drop_table("tb_part")
    op.drop_index("ix_tb_part_category_company_id", table_name="tb_part_category")
    op.drop_table("tb_part_category")
```

- [ ] **Step 4: 跑测试 + 确认 alembic head 唯一**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_migration.py -q && alembic heads`
Expected: PASS（2 passed）；`alembic heads` 输出仅 `phase3a_part (head)`

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/alembic/versions/20260531_0007_phase3a_part.py backend/tests/unit/test_part_migration.py
git commit -m "$(printf 'feat(phase-3a): add alembic migration for Part/inventory tables\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: RBAC 权限码 + 角色 + 契约测试

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase3a.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_phase3a.py`:
```python
from app import permissions as perms


def test_phase3a_codes_registered():
    for code in ["part.view", "part.create", "part.edit", "part.delete",
                 "part.consume", "part_category.view", "part_category.manage"]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_part():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_part():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["part.view", "part.create", "part.edit", "part.delete",
                 "part.consume", "part_category.view", "part_category.manage"]:
        assert code in admin["permissions"]


def test_technician_part_view_consume_category_view():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "part.view" in tech["permissions"]
    assert "part.consume" in tech["permissions"]
    assert "part_category.view" in tech["permissions"]
    assert "part.create" not in tech["permissions"]
    assert "part.edit" not in tech["permissions"]
    assert "part.delete" not in tech["permissions"]
    assert "part_category.manage" not in tech["permissions"]


def test_requester_unchanged_no_part():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_part_view_and_category_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "part.view" in viewer["permissions"]
    assert "part_category.view" in viewer["permissions"]
    assert "part.consume" not in viewer["permissions"]
    assert "part.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3a.py -q`
Expected: FAIL（part.* 未注册）

- [ ] **Step 3: 改 `app/permissions.py`**

先 Read 文件定位锚点。在 `READING_CREATE = "reading.create"` 行之后插入：
```python

# --- 库存（Phase 3A）---
PART_VIEW = "part.view"
PART_CREATE = "part.create"
PART_EDIT = "part.edit"
PART_DELETE = "part.delete"
PART_CONSUME = "part.consume"
PART_CATEGORY_VIEW = "part_category.view"
PART_CATEGORY_MANAGE = "part_category.manage"
```
在 `_READING = [READING_VIEW, READING_CREATE]` 行之后插入：
```python
_PART = [PART_VIEW, PART_CREATE, PART_EDIT, PART_DELETE, PART_CONSUME]
_PART_CATEGORY = [PART_CATEGORY_VIEW, PART_CATEGORY_MANAGE]
```
把 `ALL_PERMISSIONS` 定义改为（在末尾追加 `+ _PART + _PART_CATEGORY`）：
```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE
    + _METER + _READING + _PART + _PART_CATEGORY
)
```
在 technician 角色的 permissions 列表中，`METER_VIEW, READING_VIEW, READING_CREATE,` 行之后插入：
```python
        PART_VIEW, PART_CONSUME, PART_CATEGORY_VIEW,
```
（admin/super_admin 自动含全部；viewer 自动经 `.endswith(".view")` 含 part.view + part_category.view；requester 不变。）

- [ ] **Step 4: 跑测试确认通过 + 既有契约不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase3a.py tests/ -q -k "permission or auth_service or roles"`
Expected: PASS（含 phase3a 新测 + 既有契约测试仍绿）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/permissions.py backend/tests/test_permissions_phase3a.py
git commit -m "$(printf 'feat(phase-3a): add part.* and part_category.* permissions + role defaults\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/part.py`
- Test: `backend/tests/unit/test_part_schemas.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_part_schemas.py`:
```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.part import (
    PartCreate,
    PartUpdate,
    PartMini,
    PartCategoryCreate,
    PartConsumptionCreate,
    PartConsumptionRead,
    MultiPartCreate,
    MultiPartUpdate,
)


def test_part_mini_fields():
    m = PartMini(id="p-1", name="轴承", custom_id="PRT000001")
    assert m.id == "p-1" and m.name == "轴承" and m.custom_id == "PRT000001"


def test_part_create_defaults():
    p = PartCreate(name="轴承")
    assert p.cost == Decimal("0") and p.quantity == Decimal("0")
    assert p.min_quantity == Decimal("0") and p.non_stock is False
    assert p.unit == "" and p.category_id is None
    assert p.assignee_ids == [] and p.team_ids == [] and p.asset_ids == []


def test_part_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        PartCreate(name="")


def test_part_update_all_optional():
    assert PartUpdate().model_dump(exclude_unset=True) == {}


def test_category_create():
    c = PartCategoryCreate(name="轴承类")
    assert c.name == "轴承类" and c.description == ""


def test_consumption_create_requires_fields():
    c = PartConsumptionCreate(part_id="p-1", quantity=Decimal("2"))
    assert c.quantity == Decimal("2")
    with pytest.raises(ValidationError):
        PartConsumptionCreate(part_id="p-1")


def test_consumption_read_total_cost():
    r = PartConsumptionRead(id="c-1", part_id="p-1", work_order_id="wo-1",
                            quantity=Decimal("3"), unit_cost=Decimal("9.99"),
                            consumed_by_user_id=None, consumed_at="2026-06-01T00:00:00")
    assert r.total_cost == Decimal("29.97")


def test_multipart_create_and_update():
    m = MultiPartCreate(name="套件")
    assert m.part_ids == []
    assert MultiPartUpdate().model_dump(exclude_unset=True) == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_schemas.py -q`
Expected: FAIL（ModuleNotFoundError: app.schemas.part）

- [ ] **Step 3: 写实现**

`backend/app/schemas/part.py`:
```python
"""备件 schema（Phase 3A）。is_low_stock 计算字段只读；关联 ids 由 router 填充。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    cost: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    min_quantity: Decimal = Decimal("0")
    unit: str = Field(default="", max_length=50)
    barcode: str | None = Field(default=None, max_length=120)
    non_stock: bool = False
    category_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    asset_ids: list[str] = []


class PartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    cost: Decimal | None = None
    quantity: Decimal | None = None
    min_quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=50)
    barcode: str | None = Field(default=None, max_length=120)
    non_stock: bool | None = None
    category_id: str | None = None
    assignee_ids: list[str] | None = None
    team_ids: list[str] | None = None
    asset_ids: list[str] | None = None


class PartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    cost: Decimal
    quantity: Decimal
    min_quantity: Decimal
    unit: str
    barcode: str | None = None
    non_stock: bool
    is_low_stock: bool
    category_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    asset_ids: list[str] = []


class PartMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str


class PartCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class PartCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class PartCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str


class PartConsumptionCreate(BaseModel):
    part_id: str
    quantity: Decimal


class PartConsumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    part_id: str
    work_order_id: str
    quantity: Decimal
    unit_cost: Decimal
    consumed_by_user_id: str | None = None
    consumed_at: datetime

    @computed_field
    @property
    def total_cost(self) -> Decimal:
        return self.quantity * self.unit_cost


class MultiPartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    part_ids: list[str] = []


class MultiPartUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    part_ids: list[str] | None = None


class MultiPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    part_ids: list[str] = []
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_schemas.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/schemas/part.py backend/tests/unit/test_part_schemas.py
git commit -m "$(printf 'feat(phase-3a): add Part pydantic schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: part_category_service CRUD

**Files:**
- Create: `backend/app/services/part_category_service.py`
- Test: `backend/tests/unit/test_part_category_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_part_category_service.py`:
```python
from sqlalchemy.orm import Session

from app.schemas.part import PartCategoryCreate, PartCategoryUpdate
from app.services import part_category_service as svc

CO = "co-1"


def test_create_and_get_category(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="轴承类"), CO, actor_user_id="a")
    assert c.id and svc.get_category(db, c.id).name == "轴承类"


def test_list_categories(db: Session):
    svc.create_category(db, PartCategoryCreate(name="A"), CO, actor_user_id="a")
    svc.create_category(db, PartCategoryCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_categories(db)) == 2


def test_update_category(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="旧"), CO, actor_user_id="a")
    svc.update_category(db, c, PartCategoryUpdate(name="新", description="d"),
                        CO, actor_user_id="a")
    assert c.name == "新" and c.description == "d"


def test_delete_category_soft(db: Session):
    c = svc.create_category(db, PartCategoryCreate(name="X"), CO, actor_user_id="a")
    svc.delete_category(db, c)
    assert svc.get_category(db, c.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_category_service.py -q`
Expected: FAIL（ModuleNotFoundError: app.services.part_category_service）

- [ ] **Step 3: 写实现**

`backend/app/services/part_category_service.py`:
```python
"""备件分类服务：CRUD（软删）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.part_category import PartCategory
from app.schemas.part import PartCategoryCreate, PartCategoryUpdate


def create_category(db: Session, payload: PartCategoryCreate, company_id: str,
                    actor_user_id: str | None) -> PartCategory:
    cat = PartCategory(name=payload.name, description=payload.description,
                       company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[PartCategory]:
    return list(db.execute(
        select(PartCategory).where(PartCategory.is_active.is_(True))
        .order_by(PartCategory.name, PartCategory.id)).scalars().all())


def get_category(db: Session, category_id: str) -> PartCategory | None:
    c = db.get(PartCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_category(db: Session, cat: PartCategory, payload: PartCategoryUpdate,
                    company_id: str, actor_user_id: str | None) -> PartCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: PartCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_category_service.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/part_category_service.py backend/tests/unit/test_part_category_service.py
git commit -m "$(printf 'feat(phase-3a): add part category service CRUD\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: part_service — Part CRUD + 关联 + 过滤

**Files:**
- Create: `backend/app/services/part_service.py`
- Test: `backend/tests/unit/test_part_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_part_service.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.schemas.part import PartCreate, PartUpdate
from app.services import part_service as svc

CO = "co-1"


def test_create_part_assigns_custom_id_and_relations(db: Session):
    p = svc.create_part(db, PartCreate(
        name="轴承", cost=Decimal("12.5"), quantity=Decimal("10"),
        min_quantity=Decimal("3"), unit="pcs",
        assignee_ids=["u-1", "u-2"], team_ids=["t-1"], asset_ids=["as-1"]),
        CO, actor_user_id="a")
    assert p.custom_id == "PRT000001"
    assert set(svc.assignee_ids(db, p.id)) == {"u-1", "u-2"}
    assert svc.team_ids(db, p.id) == ["t-1"]
    assert svc.asset_ids(db, p.id) == ["as-1"]


def test_list_and_filter_parts(db: Session):
    svc.create_part(db, PartCreate(name="A", asset_ids=["as-1"],
                    quantity=Decimal("1"), min_quantity=Decimal("5")), CO, actor_user_id="a")
    svc.create_part(db, PartCreate(name="B", quantity=Decimal("9"),
                    min_quantity=Decimal("5")), CO, actor_user_id="a")
    assert len(svc.list_parts(db)) == 2
    assert len(svc.list_parts(db, asset_id="as-1")) == 1
    low = svc.list_parts(db, low_stock=True)
    assert len(low) == 1 and low[0].name == "A"          # 1 < 5


def test_filter_by_category(db: Session):
    from app.services import part_category_service as cs
    from app.schemas.part import PartCategoryCreate
    cat = cs.create_category(db, PartCategoryCreate(name="轴承类"), CO, actor_user_id="a")
    svc.create_part(db, PartCreate(name="A", category_id=cat.id), CO, actor_user_id="a")
    svc.create_part(db, PartCreate(name="B"), CO, actor_user_id="a")
    got = svc.list_parts(db, category_id=cat.id)
    assert len(got) == 1 and got[0].name == "A"


def test_update_part_quantity_and_relations(db: Session):
    p = svc.create_part(db, PartCreate(name="轴承", assignee_ids=["u-1"]),
                        CO, actor_user_id="a")
    svc.update_part(db, p, PartUpdate(quantity=Decimal("99"), assignee_ids=["u-9"]),
                    CO, actor_user_id="a")
    assert p.quantity == Decimal("99")
    assert svc.assignee_ids(db, p.id) == ["u-9"]          # 全量替换


def test_delete_part_soft(db: Session):
    p = svc.create_part(db, PartCreate(name="轴承"), CO, actor_user_id="a")
    svc.delete_part(db, p)
    assert svc.get_part(db, p.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_service.py -q`
Expected: FAIL（ModuleNotFoundError: app.services.part_service）

- [ ] **Step 3: 写实现**

`backend/app/services/part_service.py`:
```python
"""备件服务：Part CRUD（customId PRT）、M:N 关联（指派/团队/资产，全量替换）、列表过滤。

quantity 可经 update 直接改（入库/校正）；WO 消耗走 part_consumption_service。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.part import Part, PartAssignee, PartTeam, PartAsset
from app.schemas.part import PartCreate, PartUpdate
from app.services import sequence_service


def assignee_ids(db: Session, part_id: str) -> list[str]:
    return list(db.execute(
        select(PartAssignee.user_id).where(PartAssignee.part_id == part_id)
        .order_by(PartAssignee.user_id)).scalars().all())


def team_ids(db: Session, part_id: str) -> list[str]:
    return list(db.execute(
        select(PartTeam.team_id).where(PartTeam.part_id == part_id)
        .order_by(PartTeam.team_id)).scalars().all())


def asset_ids(db: Session, part_id: str) -> list[str]:
    return list(db.execute(
        select(PartAsset.asset_id).where(PartAsset.part_id == part_id)
        .order_by(PartAsset.asset_id)).scalars().all())


def _set_relations(db: Session, part_id: str, company_id: str,
                   user_ids: list[str], team_id_list: list[str],
                   asset_id_list: list[str]) -> None:
    for uid in dict.fromkeys(user_ids):
        db.add(PartAssignee(part_id=part_id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(team_id_list):
        db.add(PartTeam(part_id=part_id, team_id=tid, company_id=company_id))
    for aid in dict.fromkeys(asset_id_list):
        db.add(PartAsset(part_id=part_id, asset_id=aid, company_id=company_id))


def create_part(db: Session, payload: PartCreate, company_id: str,
                actor_user_id: str | None) -> Part:
    seq = sequence_service.next_value(db, "part", company_id)
    p = Part(
        custom_id=sequence_service.format_custom_id("PRT", seq),
        name=payload.name, description=payload.description, cost=payload.cost,
        quantity=payload.quantity, min_quantity=payload.min_quantity,
        unit=payload.unit, barcode=payload.barcode, non_stock=payload.non_stock,
        category_id=payload.category_id, company_id=company_id,
    )
    db.add(p)
    db.flush()
    _set_relations(db, p.id, company_id, payload.assignee_ids, payload.team_ids,
                   payload.asset_ids)
    db.commit()
    db.refresh(p)
    return p


def list_parts(db: Session, *, category_id: str | None = None,
               asset_id: str | None = None, low_stock: bool | None = None) -> list[Part]:
    stmt = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(Part.category_id == category_id)
    if asset_id is not None:
        stmt = stmt.where(Part.id.in_(
            select(PartAsset.part_id).where(PartAsset.asset_id == asset_id)))
    if low_stock is True:
        stmt = stmt.where(Part.non_stock.is_(False), Part.quantity < Part.min_quantity)
    return list(db.execute(stmt.order_by(Part.custom_id)).scalars().all())


def get_part(db: Session, part_id: str) -> Part | None:
    p = db.get(Part, part_id)
    if p is None or not p.is_active:
        return None
    return p


def update_part(db: Session, p: Part, payload: PartUpdate, company_id: str,
                actor_user_id: str | None) -> Part:
    data = payload.model_dump(exclude_unset=True)
    new_assignees = data.pop("assignee_ids", None)
    new_teams = data.pop("team_ids", None)
    new_assets = data.pop("asset_ids", None)
    for k, v in data.items():
        setattr(p, k, v)
    if new_assignees is not None:
        db.execute(PartAssignee.__table__.delete().where(PartAssignee.part_id == p.id))
        for uid in dict.fromkeys(new_assignees):
            db.add(PartAssignee(part_id=p.id, user_id=uid, company_id=company_id))
    if new_teams is not None:
        db.execute(PartTeam.__table__.delete().where(PartTeam.part_id == p.id))
        for tid in dict.fromkeys(new_teams):
            db.add(PartTeam(part_id=p.id, team_id=tid, company_id=company_id))
    if new_assets is not None:
        db.execute(PartAsset.__table__.delete().where(PartAsset.part_id == p.id))
        for aid in dict.fromkeys(new_assets):
            db.add(PartAsset(part_id=p.id, asset_id=aid, company_id=company_id))
    db.commit()
    db.refresh(p)
    return p


def delete_part(db: Session, p: Part) -> None:
    p.is_active = False
    p.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_service.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/part_service.py backend/tests/unit/test_part_service.py
git commit -m "$(printf 'feat(phase-3a): add part service CRUD + relations + filters\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: multi_part_service CRUD + 成员

**Files:**
- Create: `backend/app/services/multi_part_service.py`
- Test: `backend/tests/unit/test_multi_part_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_multi_part_service.py`:
```python
from sqlalchemy.orm import Session

from app.schemas.part import MultiPartCreate, MultiPartUpdate
from app.services import multi_part_service as svc

CO = "co-1"


def test_create_multipart_assigns_custom_id_and_items(db: Session):
    m = svc.create_multi_part(db, MultiPartCreate(name="保养套件", part_ids=["p-1", "p-2"]),
                              CO, actor_user_id="a")
    assert m.custom_id == "KIT000001"
    assert svc.part_ids(db, m.id) == ["p-1", "p-2"]


def test_list_multiparts(db: Session):
    svc.create_multi_part(db, MultiPartCreate(name="A"), CO, actor_user_id="a")
    svc.create_multi_part(db, MultiPartCreate(name="B"), CO, actor_user_id="a")
    assert len(svc.list_multi_parts(db)) == 2


def test_update_replaces_items(db: Session):
    m = svc.create_multi_part(db, MultiPartCreate(name="套件", part_ids=["p-1"]),
                              CO, actor_user_id="a")
    svc.update_multi_part(db, m, MultiPartUpdate(name="改名", part_ids=["p-9", "p-8"]),
                          CO, actor_user_id="a")
    assert m.name == "改名"
    assert svc.part_ids(db, m.id) == ["p-8", "p-9"]       # 全量替换（按 part_id 序）


def test_delete_multipart_soft(db: Session):
    m = svc.create_multi_part(db, MultiPartCreate(name="X"), CO, actor_user_id="a")
    svc.delete_multi_part(db, m)
    assert svc.get_multi_part(db, m.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_multi_part_service.py -q`
Expected: FAIL（ModuleNotFoundError: app.services.multi_part_service）

- [ ] **Step 3: 写实现**

`backend/app/services/multi_part_service.py`:
```python
"""多备件套件服务：CRUD（customId KIT）、成员（part_ids 全量替换）。纯分组。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.multi_part import MultiPart, MultiPartItem
from app.schemas.part import MultiPartCreate, MultiPartUpdate
from app.services import sequence_service


def part_ids(db: Session, multi_part_id: str) -> list[str]:
    return list(db.execute(
        select(MultiPartItem.part_id).where(MultiPartItem.multi_part_id == multi_part_id)
        .order_by(MultiPartItem.part_id)).scalars().all())


def _set_items(db: Session, multi_part_id: str, company_id: str,
               part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(MultiPartItem(multi_part_id=multi_part_id, part_id=pid, company_id=company_id))


def create_multi_part(db: Session, payload: MultiPartCreate, company_id: str,
                      actor_user_id: str | None) -> MultiPart:
    seq = sequence_service.next_value(db, "multi_part", company_id)
    mp = MultiPart(
        custom_id=sequence_service.format_custom_id("KIT", seq),
        name=payload.name, description=payload.description, company_id=company_id,
    )
    db.add(mp)
    db.flush()
    _set_items(db, mp.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(mp)
    return mp


def list_multi_parts(db: Session) -> list[MultiPart]:
    return list(db.execute(
        select(MultiPart).where(MultiPart.is_active.is_(True))
        .order_by(MultiPart.custom_id)).scalars().all())


def get_multi_part(db: Session, multi_part_id: str) -> MultiPart | None:
    mp = db.get(MultiPart, multi_part_id)
    if mp is None or not mp.is_active:
        return None
    return mp


def update_multi_part(db: Session, mp: MultiPart, payload: MultiPartUpdate,
                      company_id: str, actor_user_id: str | None) -> MultiPart:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, v in data.items():
        setattr(mp, k, v)
    if new_parts is not None:
        db.execute(MultiPartItem.__table__.delete()
                   .where(MultiPartItem.multi_part_id == mp.id))
        _set_items(db, mp.id, company_id, new_parts)
    db.commit()
    db.refresh(mp)
    return mp


def delete_multi_part(db: Session, mp: MultiPart) -> None:
    mp.is_active = False
    mp.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_multi_part_service.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/multi_part_service.py backend/tests/unit/test_multi_part_service.py
git commit -m "$(printf 'feat(phase-3a): add multi-part (kit) service CRUD + items\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: part_consumption_service.consume_part（挂工单消耗）

**Files:**
- Create: `backend/app/services/part_consumption_service.py`
- Test: `backend/tests/unit/test_part_consumption_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_part_consumption_service.py`:
```python
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.schemas.part import PartCreate
from app.services import part_service as ps
from app.services import part_consumption_service as cs

CO = "co-1"


def _wo(db):
    wo = WorkOrder(custom_id="WO000001", title="检修", company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_consume_decrements_stock_and_snapshots_cost(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", cost=Decimal("12.5"),
                       quantity=Decimal("10")), CO, actor_user_id="a")
    c = cs.consume_part(db, wo, p, Decimal("3"), CO, actor_user_id="u-1")
    assert isinstance(c, PartConsumption)
    assert c.unit_cost == Decimal("12.5") and c.quantity == Decimal("3")
    assert c.work_order_id == wo.id and c.consumed_by_user_id == "u-1"
    db.refresh(p)
    assert p.quantity == Decimal("7")                     # 10 - 3


def test_consume_insufficient_raises(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("2")),
                       CO, actor_user_id="a")
    with pytest.raises(HTTPException) as ei:
        cs.consume_part(db, wo, p, Decimal("5"), CO, actor_user_id="u-1")
    assert ei.value.status_code == 400
    db.refresh(p)
    assert p.quantity == Decimal("2")                     # 未扣减


def test_consume_bad_quantity_raises(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("10")),
                       CO, actor_user_id="a")
    with pytest.raises(HTTPException) as ei:
        cs.consume_part(db, wo, p, Decimal("0"), CO, actor_user_id="u-1")
    assert ei.value.status_code == 400


def test_consume_non_stock_records_but_no_decrement(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="耗材", cost=Decimal("1.0"),
                       quantity=Decimal("0"), non_stock=True), CO, actor_user_id="a")
    c = cs.consume_part(db, wo, p, Decimal("100"), CO, actor_user_id="u-1")
    assert c.quantity == Decimal("100")                   # 入台账
    db.refresh(p)
    assert p.quantity == Decimal("0")                     # non_stock 不扣减、不报错


def test_list_consumptions_by_wo(db: Session):
    wo = _wo(db)
    p = ps.create_part(db, PartCreate(name="轴承", quantity=Decimal("10")),
                       CO, actor_user_id="a")
    cs.consume_part(db, wo, p, Decimal("1"), CO, actor_user_id="u-1")
    cs.consume_part(db, wo, p, Decimal("2"), CO, actor_user_id="u-1")
    assert len(cs.list_consumptions(db, wo.id)) == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_consumption_service.py -q`
Expected: FAIL（ModuleNotFoundError: app.services.part_consumption_service）

- [ ] **Step 3: 写实现**

`backend/app/services/part_consumption_service.py`:
```python
"""备件消耗服务：挂工单消耗（扣库存、不足报错、单价快照台账）+ 台账查询。

请求内单次 commit；不调用内部 commit 的工单服务，无 partial-commit 风险。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder


def consume_part(db: Session, work_order: WorkOrder, part: Part, quantity: Decimal,
                 company_id: str, actor_user_id: str | None) -> PartConsumption:
    """在工单上消耗备件：non_stock 不扣库存不报错；计库存则不足报错并扣减。"""
    if quantity <= 0:
        raise bad_request("PART_BAD_QUANTITY", "消耗数量必须大于 0")
    if not part.non_stock:
        if quantity > part.quantity:
            raise bad_request("PART_INSUFFICIENT_STOCK", "备件库存不足")
        part.quantity = part.quantity - quantity
    consumption = PartConsumption(
        part_id=part.id, work_order_id=work_order.id, quantity=quantity,
        unit_cost=part.cost, consumed_by_user_id=actor_user_id, company_id=company_id,
    )
    db.add(consumption)
    db.commit()
    db.refresh(consumption)
    return consumption


def list_consumptions(db: Session, work_order_id: str) -> list[PartConsumption]:
    return list(db.execute(
        select(PartConsumption).where(PartConsumption.work_order_id == work_order_id)
        .order_by(PartConsumption.consumed_at, PartConsumption.id)).scalars().all())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_part_consumption_service.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/part_consumption_service.py backend/tests/unit/test_part_consumption_service.py
git commit -m "$(printf 'feat(phase-3a): add part consumption service (consume on work order)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: part_categories router + main 挂载

**Files:**
- Create: `backend/app/routers/part_categories.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_part_category_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_part_category_api.py`:
```python
"""备件分类 API（Phase 3A）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_part_category_crud(client):
    t = _admin(client)
    r = client.post("/api/v1/part-categories", json={"name": "轴承类"}, headers=_h(t))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.get("/api/v1/part-categories", headers=_h(t)).status_code == 200
    upd = client.patch(f"/api/v1/part-categories/{cid}", json={"name": "改名"}, headers=_h(t))
    assert upd.json()["name"] == "改名"
    assert client.delete(f"/api/v1/part-categories/{cid}", headers=_h(t)).status_code == 204


def test_part_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post("/api/v1/part-categories", json={"name": "X"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/part-categories/{cid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_category_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/part_categories.py`:
```python
"""备件分类 API（/api/v1/part-categories）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.part_category import PartCategory
from app.models.user import User
from app.schemas.part import (
    PartCategoryCreate,
    PartCategoryRead,
    PartCategoryUpdate,
)
from app.services import part_category_service as svc

router = APIRouter(prefix="/api/v1/part-categories", tags=["part-categories"])


def _ensure(c: PartCategory | None, company_id: str) -> PartCategory:
    if c is None or c.company_id != company_id:
        raise not_found("PART_CATEGORY_NOT_FOUND", "备件分类不存在")
    return c


@router.get("", response_model=list[PartCategoryRead])
def list_categories(db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_VIEW))):
    return svc.list_categories(db)


@router.post("", response_model=PartCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: PartCategoryCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE))):
    return svc.create_category(db, payload, current_user.company_id, actor_user_id=current_user.id)


@router.get("/{category_id}", response_model=PartCategoryRead)
def get_category(category_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.PART_CATEGORY_VIEW))):
    return _ensure(svc.get_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=PartCategoryRead)
def update_category(category_id: str, payload: PartCategoryUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE))):
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    return svc.update_category(db, c, payload, current_user.company_id, actor_user_id=current_user.id)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE))):
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    svc.delete_category(db, c)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `meters,` 行之后插入一行：
```python
    part_categories,
```
在 `app.include_router(meters.router)` 行之后插入：
```python
app.include_router(part_categories.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_category_api.py -q && python -c "import app.main"`
Expected: PASS（2 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/part_categories.py backend/app/main.py backend/tests/test_part_category_api.py
git commit -m "$(printf 'feat(phase-3a): add part-categories router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: parts router + main 挂载

**Files:**
- Create: `backend/app/routers/parts.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_part_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_part_api.py`:
```python
"""备件 API（Phase 3A）。"""
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


def _part(client, token, **kw):
    body = {"name": "轴承", "quantity": "10", "min_quantity": "3"}
    body.update(kw)
    return client.post("/api/v1/parts", json=body, headers=_h(token))


def test_part_crud(client):
    t = _admin(client)
    r = _part(client, t)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["custom_id"] == "PRT000001"
    assert r.json()["is_low_stock"] is False              # 10 >= 3
    got = client.get(f"/api/v1/parts/{pid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["name"] == "轴承"
    upd = client.patch(f"/api/v1/parts/{pid}", json={"quantity": "1"}, headers=_h(t))
    assert upd.json()["is_low_stock"] is True             # 1 < 3
    assert client.delete(f"/api/v1/parts/{pid}", headers=_h(t)).status_code == 204


def test_part_low_stock_filter(client):
    t = _admin(client)
    _part(client, t, name="低", quantity="1", min_quantity="5")
    _part(client, t, name="足", quantity="9", min_quantity="5")
    low = client.get("/api/v1/parts?low_stock=true", headers=_h(t)).json()
    assert len(low) == 1 and low[0]["name"] == "低"


def test_part_mini(client):
    t = _admin(client)
    _part(client, t, name="轴承")
    mini = client.get("/api/v1/parts/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert mini.json()[0]["custom_id"] == "PRT000001"
    assert set(mini.json()[0].keys()) == {"id", "name", "custom_id"}


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    _part(client, admin)
    assert client.get("/api/v1/parts", headers=_h(tech)).status_code == 200
    assert _part(client, tech, name="x").status_code == 403


def test_part_tenant_isolation(client):
    a = _admin(client)
    pid = _part(client, a).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/parts/{pid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/parts.py`:
```python
"""备件 API（/api/v1/parts）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.part import Part
from app.models.user import User
from app.schemas.part import PartCreate, PartMini, PartRead, PartUpdate
from app.services import part_service as svc

router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


def _ensure_part(p: Part | None, company_id: str) -> Part:
    if p is None or p.company_id != company_id:
        raise not_found("PART_NOT_FOUND", "备件不存在")
    return p


def _read_part(db: Session, p: Part) -> PartRead:
    data = PartRead.model_validate(p)
    data.assignee_ids = svc.assignee_ids(db, p.id)
    data.team_ids = svc.team_ids(db, p.id)
    data.asset_ids = svc.asset_ids(db, p.id)
    return data


@router.get("", response_model=list[PartRead])
def list_parts(category_id: str | None = None, asset_id: str | None = None,
               low_stock: bool | None = None, db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    return [_read_part(db, p) for p in svc.list_parts(
        db, category_id=category_id, asset_id=asset_id, low_stock=low_stock)]


@router.post("", response_model=PartRead, status_code=status.HTTP_201_CREATED)
def create_part(payload: PartCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.PART_CREATE))):
    p = svc.create_part(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_part(db, p)


# 注：/mini 必须注册在 /{part_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[PartMini])
def list_parts_mini(db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    return svc.list_parts(db)


@router.get("/{part_id}", response_model=PartRead)
def get_part(part_id: str, db: Session = Depends(get_db),
             current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    return _read_part(db, p)


@router.patch("/{part_id}", response_model=PartRead)
def update_part(part_id: str, payload: PartUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.PART_EDIT))):
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    svc.update_part(db, p, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_part(db, p)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part(part_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.PART_DELETE))):
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    svc.delete_part(db, p)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `part_categories,` 行之后插入一行：
```python
    parts,
```
在 `app.include_router(part_categories.router)` 行之后插入：
```python
app.include_router(parts.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_api.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/parts.py backend/app/main.py backend/tests/test_part_api.py
git commit -m "$(printf 'feat(phase-3a): add parts router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: multi_parts router + main 挂载

**Files:**
- Create: `backend/app/routers/multi_parts.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_multi_part_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_multi_part_api.py`:
```python
"""多备件套件 API（Phase 3A）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"},
                       headers=_h(t)).json()["id"]


def test_multipart_crud(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    r = client.post("/api/v1/multi-parts",
                    json={"name": "套件", "part_ids": [p1, p2]}, headers=_h(t))
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["custom_id"] == "KIT000001"
    assert set(r.json()["part_ids"]) == {p1, p2}
    upd = client.patch(f"/api/v1/multi-parts/{mid}",
                       json={"part_ids": [p1]}, headers=_h(t))
    assert upd.json()["part_ids"] == [p1]
    assert len(client.get("/api/v1/multi-parts", headers=_h(t)).json()) == 1
    assert client.delete(f"/api/v1/multi-parts/{mid}", headers=_h(t)).status_code == 204


def test_multipart_tenant_isolation(client):
    a = _admin(client)
    mid = client.post("/api/v1/multi-parts", json={"name": "X"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/multi-parts/{mid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_multi_part_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/multi_parts.py`:
```python
"""多备件套件 API（/api/v1/multi-parts）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.multi_part import MultiPart
from app.models.user import User
from app.schemas.part import MultiPartCreate, MultiPartRead, MultiPartUpdate
from app.services import multi_part_service as svc

router = APIRouter(prefix="/api/v1/multi-parts", tags=["multi-parts"])


def _ensure(mp: MultiPart | None, company_id: str) -> MultiPart:
    if mp is None or mp.company_id != company_id:
        raise not_found("MULTI_PART_NOT_FOUND", "套件不存在")
    return mp


def _read(db: Session, mp: MultiPart) -> MultiPartRead:
    data = MultiPartRead.model_validate(mp)
    data.part_ids = svc.part_ids(db, mp.id)
    return data


@router.get("", response_model=list[MultiPartRead])
def list_multi_parts(db: Session = Depends(get_db),
                     current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    return [_read(db, mp) for mp in svc.list_multi_parts(db)]


@router.post("", response_model=MultiPartRead, status_code=status.HTTP_201_CREATED)
def create_multi_part(payload: MultiPartCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.PART_CREATE))):
    mp = svc.create_multi_part(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, mp)


@router.get("/{multi_part_id}", response_model=MultiPartRead)
def get_multi_part(multi_part_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    return _read(db, mp)


@router.patch("/{multi_part_id}", response_model=MultiPartRead)
def update_multi_part(multi_part_id: str, payload: MultiPartUpdate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.PART_EDIT))):
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    svc.update_multi_part(db, mp, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, mp)


@router.delete("/{multi_part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_multi_part(multi_part_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.PART_DELETE))):
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    svc.delete_multi_part(db, mp)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `parts,` 行之后插入一行：
```python
    multi_parts,
```
在 `app.include_router(parts.router)` 行之后插入：
```python
app.include_router(multi_parts.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_multi_part_api.py -q && python -c "import app.main"`
Expected: PASS（2 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/multi_parts.py backend/app/main.py backend/tests/test_multi_part_api.py
git commit -m "$(printf 'feat(phase-3a): add multi-parts router + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 12: part_consumptions router（挂工单）+ main 挂载

**Files:**
- Create: `backend/app/routers/part_consumptions.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_part_consumption_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_part_consumption_api.py`:
```python
"""备件消耗 API（Phase 3A，挂工单）。"""
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


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def _part_id(client, t, **kw):
    body = {"name": "轴承", "cost": "12.5", "quantity": "10"}
    body.update(kw)
    return client.post("/api/v1/parts", json=body, headers=_h(t)).json()["id"]


def test_consume_decrements_and_returns_ledger(client):
    t = _admin(client)
    wo, pid = _wo_id(client, t), _part_id(client, t)
    r = client.post(f"/api/v1/work-orders/{wo}/part-consumptions",
                    json={"part_id": pid, "quantity": "3"}, headers=_h(t))
    assert r.status_code == 201, r.text
    assert r.json()["unit_cost"] == "12.5000" or float(r.json()["unit_cost"]) == 12.5
    assert float(r.json()["total_cost"]) == 37.5         # 3 * 12.5
    # 库存扣减
    assert float(client.get(f"/api/v1/parts/{pid}", headers=_h(t)).json()["quantity"]) == 7.0
    lst = client.get(f"/api/v1/work-orders/{wo}/part-consumptions", headers=_h(t))
    assert len(lst.json()) == 1


def test_consume_insufficient_400(client):
    t = _admin(client)
    wo, pid = _wo_id(client, t), _part_id(client, t, quantity="2")
    r = client.post(f"/api/v1/work-orders/{wo}/part-consumptions",
                    json={"part_id": pid, "quantity": "5"}, headers=_h(t))
    assert r.status_code == 400


def test_technician_can_consume(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    wo, pid = _wo_id(client, admin), _part_id(client, admin)
    r = client.post(f"/api/v1/work-orders/{wo}/part-consumptions",
                    json={"part_id": pid, "quantity": "1"}, headers=_h(tech))
    assert r.status_code == 201, r.text


def test_consume_cross_tenant_404(client):
    a = _admin(client)
    wo, pid = _wo_id(client, a), _part_id(client, a)
    b = _admin(client, company="Beta", email="admin@beta.com")
    # 他租户工单不可见
    r = client.post(f"/api/v1/work-orders/{wo}/part-consumptions",
                    json={"part_id": pid, "quantity": "1"}, headers=_h(b))
    assert r.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_consumption_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/part_consumptions.py`:
```python
"""备件消耗 API（/api/v1/work-orders/{wo_id}/part-consumptions）。独立 router，不改 work_orders.py。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.part import PartConsumptionCreate, PartConsumptionRead
from app.services import part_consumption_service as svc
from app.services import part_service as ps
from app.services import work_order_service as wos

router = APIRouter(prefix="/api/v1/work-orders/{work_order_id}/part-consumptions",
                   tags=["part-consumptions"])


def _ensure_wo(db: Session, work_order_id: str, company_id: str) -> WorkOrder:
    wo = wos.get_work_order(db, work_order_id)
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


@router.get("", response_model=list[PartConsumptionRead])
def list_consumptions(work_order_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.PART_VIEW))):
    _ensure_wo(db, work_order_id, current_user.company_id)
    return svc.list_consumptions(db, work_order_id)


@router.post("", response_model=PartConsumptionRead, status_code=status.HTTP_201_CREATED)
def consume(work_order_id: str, payload: PartConsumptionCreate, db: Session = Depends(get_db),
            current_user: User = Depends(require_permission(permissions.PART_CONSUME))):
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    part = ps.get_part(db, payload.part_id)
    if part is None or part.company_id != current_user.company_id:
        raise not_found("PART_NOT_FOUND", "备件不存在")
    return svc.consume_part(db, wo, part, payload.quantity, current_user.company_id,
                            actor_user_id=current_user.id)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `multi_parts,` 行之后插入一行：
```python
    part_consumptions,
```
在 `app.include_router(multi_parts.router)` 行之后插入：
```python
app.include_router(part_consumptions.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_part_consumption_api.py -q && python -c "import app.main"`
Expected: PASS（4 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/part_consumptions.py backend/app/main.py backend/tests/test_part_consumption_api.py
git commit -m "$(printf 'feat(phase-3a): add part-consumptions router (consume on work order) + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 13: 全量回归 + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/part_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 807 + 新增；0 failed）。Read tee 文件确认真实摘要行（防陈旧回放）。

- [ ] **Step 2: 确认工作树与提交链干净**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git status --porcelain && git log --oneline -13
```
Expected: porcelain 为空；最近提交含 Task 1–12 各一次。

- [ ] **Step 3: alembic 单 head 校验**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads`
Expected: 仅 `phase3a_part (head)`

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含新增 Part 单测 + API 测 + 契约/迁移测）。
- `tb_part` / `tb_part_category` / `tb_part_consumption` / `tb_multi_part` / `tb_multi_part_item` / `tb_part_assignee` / `tb_part_team` / `tb_part_asset` 八表经迁移可 upgrade/downgrade。
- `/parts`、`/part-categories`、`/multi-parts`、`/work-orders/{id}/part-consumptions` 全套端点工作；经工单消耗扣库存并写成本快照台账；技师能消耗、不能管理备件；跨租户隔离 404。
- non_stock 与库存不足语义正确；`is_low_stock` 计算正确；单价快照定格。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净，alembic 单 head `phase3a_part`。
