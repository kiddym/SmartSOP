# Phase 2C 计量（Meter）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现「读数越过阈值 → 自动生成工单」：Meter/Reading/Trigger 三实体 + 提交读数同步评估触发器（边沿触发 + 重新武装）生单，配套 CRUD/读数/触发器 API 与 RBAC。

**Architecture:** 与 2A Request / 2B PM 同构的「触发源→生成工单」分层（model/schema/service/router）。区别于 PM 的调度器，本模块由 POST reading 事件**同步**驱动：读数提交在同一请求内评估该 meter 全部启用 trigger，边沿命中复用 `work_order_service.create_work_order` + `work_order_execution_service.attach_procedure` 生单。Service 拆 `meter_trigger_service`（触发器+评估引擎）与 `meter_service`（仪表+读数+编排）两文件。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · SQLite(测试)/MySQL(生产) · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`__init__.py`/`main.py`/`permissions.py`）一律用 Edit 精确替换，禁 sed/re.sub
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`
- 新文件务必 `git add` 后再提交
- 复用既有签名：`sequence_service.next_value(db, scope, company_id)`、`format_custom_id(prefix, value, digits=6)`；`bad_request(code,msg)`/`not_found(code,msg)`（均 raise HTTPException）；`work_order_service.create_work_order(db, payload, company_id, actor_user_id)`（内部 commit）、`work_order_service.to_read(db, wo)->dict`；`work_order_execution_service.attach_procedure(db, wo, procedure_id, company_id, actor_user_id)`；`app.models.base.utcnow`、`DATETIME6`

---

## Task 1: MeterComparator 枚举

**Files:**
- Create: `backend/app/models/meter_comparator.py`
- Test: `backend/tests/unit/test_meter_comparator.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_comparator.py`:
```python
from app.models.meter_comparator import MeterComparator


def test_comparator_values():
    assert MeterComparator.LESS_THAN.value == "LESS_THAN"
    assert MeterComparator.MORE_THAN.value == "MORE_THAN"
    assert {c.value for c in MeterComparator} == {"LESS_THAN", "MORE_THAN"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_comparator.py -q`
Expected: FAIL（ModuleNotFoundError: app.models.meter_comparator）

- [ ] **Step 3: 写实现**

`backend/app/models/meter_comparator.py`:
```python
"""仪表触发比较符（Phase 2C）。"""
from __future__ import annotations

from enum import Enum


class MeterComparator(str, Enum):
    LESS_THAN = "LESS_THAN"
    MORE_THAN = "MORE_THAN"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_comparator.py -q`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/meter_comparator.py backend/tests/unit/test_meter_comparator.py
git commit -m "$(printf 'feat(phase-2c): add MeterComparator enum\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: Meter ORM 模型（5 张表）+ 注册

**Files:**
- Create: `backend/app/models/meter.py`（Meter）
- Create: `backend/app/models/meter_reading.py`（MeterReading）
- Create: `backend/app/models/meter_trigger.py`（MeterTrigger + MeterTriggerAssignee + MeterTriggerTeam）
- Modify: `backend/app/models/__init__.py`（import 区 + `__all__`）
- Test: `backend/tests/unit/test_meter_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_models.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.models.meter_comparator import MeterComparator
from app.models.meter_trigger import (
    MeterTrigger,
    MeterTriggerAssignee,
    MeterTriggerTeam,
)
from app.models.work_order_status import WorkOrderPriority


def test_meter_row_roundtrip(db: Session):
    m = Meter(custom_id="MTR000001", name="主轴温度", unit="℃",
              update_frequency_days=7, company_id="co-1")
    db.add(m)
    db.commit()
    db.refresh(m)
    assert m.id and m.is_active is True
    db.add(MeterReading(meter_id=m.id, value=Decimal("123.4500"), company_id="co-1"))
    trig = MeterTrigger(
        meter_id=m.id, name="高温", comparator=MeterComparator.MORE_THAN,
        threshold=Decimal("100.0000"), priority=WorkOrderPriority.HIGH,
        title="高温处理", company_id="co-1",
    )
    db.add(trig)
    db.commit()
    db.refresh(trig)
    assert trig.is_armed is True and trig.is_enabled is True
    assert trig.last_triggered_at is None and trig.last_work_order_id is None
    db.add(MeterTriggerAssignee(trigger_id=trig.id, user_id="u-1", company_id="co-1"))
    db.add(MeterTriggerTeam(trigger_id=trig.id, team_id="t-1", company_id="co-1"))
    db.commit()
    reading = db.query(MeterReading).filter_by(meter_id=m.id).one()
    assert reading.reading_at is not None  # default utcnow


def test_meter_exports_registered():
    import app.models as mod
    for name in ("Meter", "MeterReading", "MeterTrigger",
                 "MeterTriggerAssignee", "MeterTriggerTeam"):
        assert name in mod.__all__ and hasattr(mod, name)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_models.py -q`
Expected: FAIL（ModuleNotFoundError: app.models.meter）

- [ ] **Step 3: 写 Meter 模型**

`backend/app/models/meter.py`:
```python
"""仪表（Meter，每租户）。挂资产；unit/update_frequency_days 为元数据。

读数命中触发器阈值→自动生成工单（见 meter_trigger）。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Meter(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_meter"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="", server_default="")
    update_frequency_days: Mapped[int | None] = mapped_column(Integer, default=None)
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
```

- [ ] **Step 4: 写 MeterReading 模型**

`backend/app/models/meter_reading.py`:
```python
"""仪表读数（每租户，append-only 不软删，审计性质）。

value 用 Numeric(18,4) 避免浮点漂移影响阈值比较。reading_at 默认当前时刻。
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


class MeterReading(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_reading"

    meter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reading_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
    recorded_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
```

- [ ] **Step 5: 写 MeterTrigger + 关联表**

`backend/app/models/meter_trigger.py`:
```python
"""仪表工单触发器（WorkOrderMeterTrigger，每租户）。

comparator+threshold 定义阈值；is_armed 为边沿去重武装态；其余字段为生单预设
（复用 WorkOrderPriority）。priority/primary_user 弱关联，procedure_id 无 FK 弱引用。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)
from app.models.meter_comparator import MeterComparator
from app.models.work_order_status import WorkOrderPriority


class MeterTrigger(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger"

    meter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    comparator: Mapped[MeterComparator] = mapped_column(
        SAEnum(MeterComparator), nullable=False
    )
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_armed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.NONE
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )
    procedure_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    last_work_order_id: Mapped[str | None] = mapped_column(String(36), default=None)


class MeterTriggerAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger_assignee"
    __table_args__ = (
        UniqueConstraint("trigger_id", "user_id", name="uq_meter_trigger_assignee"),
    )

    trigger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class MeterTriggerTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_meter_trigger_team"
    __table_args__ = (
        UniqueConstraint("trigger_id", "team_id", name="uq_meter_trigger_team"),
    )

    trigger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 6: 注册到 `app/models/__init__.py`**

先 Read 文件定位锚点。在 import 区 `from app.models.pm_activity import PMActivity` 行之后插入：
```python
from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import MeterTrigger, MeterTriggerAssignee, MeterTriggerTeam
```
在 `__all__` 列表中 `"PreventiveMaintenance",` 行之后插入：
```python
    "Meter",
    "MeterReading",
    "MeterTrigger",
    "MeterTriggerAssignee",
    "MeterTriggerTeam",
```

- [ ] **Step 7: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_models.py -q && python -c "import app.models; import app.main"`
Expected: PASS（2 passed）+ 无导入错误

- [ ] **Step 8: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/meter.py backend/app/models/meter_reading.py backend/app/models/meter_trigger.py backend/app/models/__init__.py backend/tests/unit/test_meter_models.py
git commit -m "$(printf 'feat(phase-2c): add Meter ORM models (meter + reading + trigger/assignee/team)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/20260531_0006_phase2c_meter.py`
- Test: `backend/tests/unit/test_meter_migration.py`

- [ ] **Step 1: 写失败测试（upgrade/downgrade 在 SQLite 往返）**

`backend/tests/unit/test_meter_migration.py`:
```python
import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260531_0006_phase2c_meter")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "phase2c_meter"
    assert m.down_revision == "phase2b_pm"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_asset (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_location (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_team (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        # alembic 1.18: Operations.context() 接收 MigrationContext 本身。
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_meter", "tb_meter_reading", "tb_meter_trigger",
                "tb_meter_trigger_assignee", "tb_meter_trigger_team",
            } <= tables
            _mod().downgrade()
            assert "tb_meter" not in inspect(conn).get_table_names()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_migration.py -q`
Expected: FAIL（ModuleNotFoundError: 迁移模块不存在）

- [ ] **Step 3: 写迁移**

`backend/alembic/versions/20260531_0006_phase2c_meter.py`:
```python
"""phase2c meter: meter + meter_reading + meter_trigger/assignee/team tables

Revision ID: phase2c_meter
Revises: phase2b_pm
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase2c_meter"
down_revision: str | Sequence[str] | None = "phase2b_pm"
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
        "tb_meter",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default=""),
        sa.Column("update_frequency_days", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_meter_company_id", "tb_meter", ["company_id"])
    op.create_index("ix_tb_meter_asset_id", "tb_meter", ["asset_id"])
    op.create_index("ix_tb_meter_location_id", "tb_meter", ["location_id"])

    op.create_table(
        "tb_meter_reading",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("meter_id", sa.String(36),
                  sa.ForeignKey("tb_meter.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("reading_at", DATETIME6, nullable=False),
        sa.Column("recorded_by_user_id", sa.String(36), nullable=True),
        *_ts(),
    )
    op.create_index("ix_tb_meter_reading_company_id", "tb_meter_reading", ["company_id"])
    op.create_index("ix_tb_meter_reading_meter_id", "tb_meter_reading", ["meter_id"])

    op.create_table(
        "tb_meter_trigger",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("meter_id", sa.String(36),
                  sa.ForeignKey("tb_meter.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("comparator",
                  sa.Enum("LESS_THAN", "MORE_THAN", name="metercomparator"),
                  nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("is_armed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("procedure_id", sa.String(36), nullable=True),
        sa.Column("last_triggered_at", DATETIME6, nullable=True),
        sa.Column("last_work_order_id", sa.String(36), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_meter_trigger_company_id", "tb_meter_trigger", ["company_id"])
    op.create_index("ix_tb_meter_trigger_meter_id", "tb_meter_trigger", ["meter_id"])
    op.create_index("ix_tb_meter_trigger_primary_user_id", "tb_meter_trigger", ["primary_user_id"])
    op.create_index("ix_tb_meter_trigger_procedure_id", "tb_meter_trigger", ["procedure_id"])

    op.create_table(
        "tb_meter_trigger_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("trigger_id", sa.String(36),
                  sa.ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("trigger_id", "user_id", name="uq_meter_trigger_assignee"),
    )
    op.create_index("ix_tb_meter_trigger_assignee_company_id", "tb_meter_trigger_assignee", ["company_id"])
    op.create_index("ix_tb_meter_trigger_assignee_trigger_id", "tb_meter_trigger_assignee", ["trigger_id"])
    op.create_index("ix_tb_meter_trigger_assignee_user_id", "tb_meter_trigger_assignee", ["user_id"])

    op.create_table(
        "tb_meter_trigger_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("trigger_id", sa.String(36),
                  sa.ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("trigger_id", "team_id", name="uq_meter_trigger_team"),
    )
    op.create_index("ix_tb_meter_trigger_team_company_id", "tb_meter_trigger_team", ["company_id"])
    op.create_index("ix_tb_meter_trigger_team_trigger_id", "tb_meter_trigger_team", ["trigger_id"])
    op.create_index("ix_tb_meter_trigger_team_team_id", "tb_meter_trigger_team", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_tb_meter_trigger_team_team_id", table_name="tb_meter_trigger_team")
    op.drop_index("ix_tb_meter_trigger_team_trigger_id", table_name="tb_meter_trigger_team")
    op.drop_index("ix_tb_meter_trigger_team_company_id", table_name="tb_meter_trigger_team")
    op.drop_table("tb_meter_trigger_team")
    op.drop_index("ix_tb_meter_trigger_assignee_user_id", table_name="tb_meter_trigger_assignee")
    op.drop_index("ix_tb_meter_trigger_assignee_trigger_id", table_name="tb_meter_trigger_assignee")
    op.drop_index("ix_tb_meter_trigger_assignee_company_id", table_name="tb_meter_trigger_assignee")
    op.drop_table("tb_meter_trigger_assignee")
    op.drop_index("ix_tb_meter_trigger_procedure_id", table_name="tb_meter_trigger")
    op.drop_index("ix_tb_meter_trigger_primary_user_id", table_name="tb_meter_trigger")
    op.drop_index("ix_tb_meter_trigger_meter_id", table_name="tb_meter_trigger")
    op.drop_index("ix_tb_meter_trigger_company_id", table_name="tb_meter_trigger")
    op.drop_table("tb_meter_trigger")
    op.drop_index("ix_tb_meter_reading_meter_id", table_name="tb_meter_reading")
    op.drop_index("ix_tb_meter_reading_company_id", table_name="tb_meter_reading")
    op.drop_table("tb_meter_reading")
    op.drop_index("ix_tb_meter_location_id", table_name="tb_meter")
    op.drop_index("ix_tb_meter_asset_id", table_name="tb_meter")
    op.drop_index("ix_tb_meter_company_id", table_name="tb_meter")
    op.drop_table("tb_meter")
```

- [ ] **Step 4: 跑测试 + 确认 alembic head 唯一**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_migration.py -q && alembic heads`
Expected: PASS（2 passed）；`alembic heads` 输出仅 `phase2c_meter (head)`

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/alembic/versions/20260531_0006_phase2c_meter.py backend/tests/unit/test_meter_migration.py
git commit -m "$(printf 'feat(phase-2c): add alembic migration for Meter tables\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: RBAC 权限码 + 角色 + 契约测试

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase2c.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_phase2c.py`:
```python
from app import permissions as perms


def test_phase2c_codes_registered():
    for code in ["meter.view", "meter.create", "meter.edit", "meter.delete",
                 "reading.view", "reading.create"]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_meter():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_meter():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["meter.view", "meter.create", "meter.edit", "meter.delete",
                 "reading.view", "reading.create"]:
        assert code in admin["permissions"]


def test_technician_meter_view_and_reading_rw():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "meter.view" in tech["permissions"]
    assert "reading.view" in tech["permissions"]
    assert "reading.create" in tech["permissions"]
    assert "meter.create" not in tech["permissions"]
    assert "meter.edit" not in tech["permissions"]
    assert "meter.delete" not in tech["permissions"]


def test_requester_unchanged_no_meter():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_meter_view_and_reading_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "meter.view" in viewer["permissions"]
    assert "reading.view" in viewer["permissions"]
    assert "meter.create" not in viewer["permissions"]
    assert "reading.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase2c.py -q`
Expected: FAIL（meter.* 未注册）

- [ ] **Step 3: 改 `app/permissions.py`**

先 Read 文件定位锚点。在 `PREVENTIVE_MAINTENANCE_DELETE = "preventive_maintenance.delete"` 行之后插入：
```python

# --- 计量（Phase 2C）---
METER_VIEW = "meter.view"
METER_CREATE = "meter.create"
METER_EDIT = "meter.edit"
METER_DELETE = "meter.delete"
READING_VIEW = "reading.view"
READING_CREATE = "reading.create"
```
在 `_PREVENTIVE_MAINTENANCE = [...]` 块之后插入：
```python
_METER = [METER_VIEW, METER_CREATE, METER_EDIT, METER_DELETE]
_READING = [READING_VIEW, READING_CREATE]
```
把 `ALL_PERMISSIONS` 定义改为（在末尾追加 `+ _METER + _READING`）：
```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE
    + _METER + _READING
)
```
在 technician 角色的 permissions 列表中，`PREVENTIVE_MAINTENANCE_VIEW,` 行之后插入：
```python
        METER_VIEW, READING_VIEW, READING_CREATE,
```
（admin/super_admin 自动含全部；viewer 自动经 `.endswith(".view")` 含 meter.view + reading.view；requester 不变。）

- [ ] **Step 4: 跑测试确认通过 + 既有契约不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase2c.py tests/ -q -k "permission or auth_service or roles"`
Expected: PASS（含 phase2c 新测 + 既有契约测试仍绿）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/permissions.py backend/tests/test_permissions_phase2c.py
git commit -m "$(printf 'feat(phase-2c): add meter.* and reading.* permissions + role defaults\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/meter.py`
- Test: `backend/tests/unit/test_meter_schemas.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_schemas.py`:
```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.meter_comparator import MeterComparator
from app.schemas.meter import MeterCreate, TriggerCreate, TriggerUpdate, MeterReadingCreate


def test_meter_create_defaults():
    m = MeterCreate(name="温度表", unit="℃")
    assert m.unit == "℃" and m.update_frequency_days is None
    assert m.asset_id is None


def test_meter_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        MeterCreate(name="", unit="℃")


def test_trigger_create_defaults():
    t = TriggerCreate(name="高温", comparator="MORE_THAN", threshold=Decimal("100"),
                      title="处理高温")
    assert t.comparator == MeterComparator.MORE_THAN
    assert t.priority.value == "NONE"
    assert t.assignee_ids == [] and t.team_ids == []


def test_trigger_update_all_optional():
    assert TriggerUpdate().model_dump(exclude_unset=True) == {}


def test_reading_create_requires_value():
    r = MeterReadingCreate(value=Decimal("12.5"))
    assert r.value == Decimal("12.5") and r.reading_at is None
    with pytest.raises(ValidationError):
        MeterReadingCreate()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_schemas.py -q`
Expected: FAIL（ModuleNotFoundError: app.schemas.meter）

- [ ] **Step 3: 写实现**

`backend/app/schemas/meter.py`:
```python
"""Meter schema（Phase 2C）。is_armed/last_* 不可写（由 service 维护）。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.meter_comparator import MeterComparator
from app.models.work_order_status import WorkOrderPriority


class MeterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="", max_length=50)
    update_frequency_days: int | None = Field(default=None, ge=1)
    asset_id: str | None = None
    location_id: str | None = None


class MeterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    unit: str | None = Field(default=None, max_length=50)
    update_frequency_days: int | None = Field(default=None, ge=1)
    asset_id: str | None = None
    location_id: str | None = None


class MeterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    unit: str
    update_frequency_days: int | None = None
    asset_id: str | None = None
    location_id: str | None = None


class MeterReadingCreate(BaseModel):
    value: Decimal
    reading_at: datetime | None = None


class MeterReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meter_id: str
    value: Decimal
    reading_at: datetime
    recorded_by_user_id: str | None = None


class TriggerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    comparator: MeterComparator
    threshold: Decimal
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []


class TriggerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    comparator: MeterComparator | None = None
    threshold: Decimal | None = None
    priority: WorkOrderPriority | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] | None = None
    team_ids: list[str] | None = None


class TriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meter_id: str
    name: str
    comparator: MeterComparator
    threshold: Decimal
    is_armed: bool
    is_enabled: bool
    priority: WorkOrderPriority
    title: str
    description: str
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    last_triggered_at: datetime | None = None
    last_work_order_id: str | None = None


class ReadingResult(BaseModel):
    reading: MeterReadingRead
    generated_work_order_ids: list[str] = []
```

> 注：`TriggerRead.assignee_ids`/`team_ids` 不是 ORM 属性，由 router 在 model_validate 后用 service 填充（见 Task 11 的 `_read_trigger`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_schemas.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/schemas/meter.py backend/tests/unit/test_meter_schemas.py
git commit -m "$(printf 'feat(phase-2c): add Meter pydantic schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: meter_trigger_service 纯函数（条件 + 边沿决策）

**Files:**
- Create: `backend/app/services/meter_trigger_service.py`（先只放纯函数，后续 Task 增补）
- Test: `backend/tests/unit/test_meter_decision.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_decision.py`:
```python
from decimal import Decimal

from app.models.meter_comparator import MeterComparator as C
from app.services.meter_trigger_service import _condition_met, _decide


def test_condition_met_strict_inequality():
    assert _condition_met(C.MORE_THAN, Decimal("100.0001"), Decimal("100")) is True
    assert _condition_met(C.MORE_THAN, Decimal("100"), Decimal("100")) is False  # 相等不算
    assert _condition_met(C.LESS_THAN, Decimal("99.9999"), Decimal("100")) is True
    assert _condition_met(C.LESS_THAN, Decimal("100"), Decimal("100")) is False


def test_decide_fire_when_met_and_armed():
    assert _decide(is_armed=True, met=True) == "FIRE"


def test_decide_rearm_when_unmet_and_disarmed():
    assert _decide(is_armed=False, met=False) == "REARM"


def test_decide_noop_persisting_met():
    assert _decide(is_armed=False, met=True) == "NOOP"   # 持续满足，已发火抑制


def test_decide_noop_persisting_unmet():
    assert _decide(is_armed=True, met=False) == "NOOP"   # 持续未满足
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_decision.py -q`
Expected: FAIL（ModuleNotFoundError / ImportError）

- [ ] **Step 3: 写实现**

`backend/app/services/meter_trigger_service.py`:
```python
"""仪表触发器服务：边沿评估纯函数、触发器 CRUD、按 trigger 生单。

读数提交时由 meter_service 调用：_condition_met 判定阈值，_decide 给出
FIRE/REARM/NOOP；FIRE 走 generate_from_trigger 复用工单服务。
工单服务在函数内 import 避免循环依赖。
"""
from __future__ import annotations

from decimal import Decimal

from app.models.meter_comparator import MeterComparator


def _condition_met(comparator: MeterComparator, value: Decimal, threshold: Decimal) -> bool:
    """严格不等：MORE_THAN→value>threshold；LESS_THAN→value<threshold。相等不算满足。"""
    if comparator == MeterComparator.MORE_THAN:
        return value > threshold
    return value < threshold


def _decide(*, is_armed: bool, met: bool) -> str:
    """边沿状态机：满足且武装→FIRE；未满足且已解武装→REARM；其余 NOOP。"""
    if met and is_armed:
        return "FIRE"
    if (not met) and (not is_armed):
        return "REARM"
    return "NOOP"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_decision.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/meter_trigger_service.py backend/tests/unit/test_meter_decision.py
git commit -m "$(printf 'feat(phase-2c): add meter trigger edge-decision pure functions\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: meter_trigger_service CRUD + 关联查询

**Files:**
- Modify: `backend/app/services/meter_trigger_service.py`
- Test: `backend/tests/unit/test_meter_trigger_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_trigger_service.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.schemas.meter import TriggerCreate, TriggerUpdate
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter(db):
    m = Meter(custom_id="MTR000001", name="温度", unit="℃", company_id=CO)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _payload(**kw):
    base = dict(name="高温", comparator=MeterComparator.MORE_THAN,
                threshold=Decimal("100"), title="处理高温")
    base.update(kw)
    return TriggerCreate(**base)


def test_create_trigger_armed_and_relations(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(assignee_ids=["u-1", "u-2"], team_ids=["t-1"]),
                          CO, actor_user_id="a")
    assert t.is_armed is True and t.is_enabled is True
    assert set(ts.assignee_ids(db, t.id)) == {"u-1", "u-2"}
    assert ts.team_ids(db, t.id) == ["t-1"]


def test_list_triggers_by_meter(db: Session):
    m = _meter(db)
    ts.create_trigger(db, m.id, _payload(name="A"), CO, actor_user_id="a")
    ts.create_trigger(db, m.id, _payload(name="B"), CO, actor_user_id="a")
    assert len(ts.list_triggers(db, m.id)) == 2


def test_update_threshold_rearms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(db, t, TriggerUpdate(threshold=Decimal("200")), CO, actor_user_id="a")
    assert t.is_armed is True and t.threshold == Decimal("200")


def test_update_comparator_rearms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(db, t, TriggerUpdate(comparator=MeterComparator.LESS_THAN),
                      CO, actor_user_id="a")
    assert t.is_armed is True


def test_update_presets_only_keeps_armed(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    t.is_armed = False
    db.commit()
    ts.update_trigger(db, t, TriggerUpdate(title="改标题", assignee_ids=["u-9"]),
                      CO, actor_user_id="a")
    assert t.is_armed is False                       # 仅改预设不动武装
    assert ts.assignee_ids(db, t.id) == ["u-9"]      # 关联全量替换


def test_enable_disable(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    ts.disable_trigger(db, t, CO, actor_user_id="a")
    assert t.is_enabled is False
    ts.enable_trigger(db, t, CO, actor_user_id="a")
    assert t.is_enabled is True


def test_delete_soft(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, _payload(), CO, actor_user_id="a")
    ts.delete_trigger(db, t)
    assert ts.get_trigger(db, t.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_trigger_service.py -q`
Expected: FAIL（AttributeError: create_trigger）

- [ ] **Step 3: 增补 CRUD**

在 `backend/app/services/meter_trigger_service.py` 顶部 import 区补充（与现有合并）：
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.meter_trigger import (
    MeterTrigger,
    MeterTriggerAssignee,
    MeterTriggerTeam,
)
from app.schemas.meter import TriggerCreate, TriggerUpdate
```
在文件末尾追加：
```python
def assignee_ids(db: Session, trigger_id: str) -> list[str]:
    return list(db.execute(
        select(MeterTriggerAssignee.user_id)
        .where(MeterTriggerAssignee.trigger_id == trigger_id)
        .order_by(MeterTriggerAssignee.user_id)).scalars().all())


def team_ids(db: Session, trigger_id: str) -> list[str]:
    return list(db.execute(
        select(MeterTriggerTeam.team_id)
        .where(MeterTriggerTeam.trigger_id == trigger_id)
        .order_by(MeterTriggerTeam.team_id)).scalars().all())


def _set_relations(db: Session, trigger_id: str, company_id: str,
                   user_ids: list[str], team_id_list: list[str]) -> None:
    for uid in dict.fromkeys(user_ids):
        db.add(MeterTriggerAssignee(trigger_id=trigger_id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(team_id_list):
        db.add(MeterTriggerTeam(trigger_id=trigger_id, team_id=tid, company_id=company_id))


def create_trigger(db: Session, meter_id: str, payload: TriggerCreate, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    trig = MeterTrigger(
        meter_id=meter_id, name=payload.name, comparator=payload.comparator,
        threshold=payload.threshold, priority=payload.priority, title=payload.title,
        description=payload.description, primary_user_id=payload.primary_user_id,
        procedure_id=payload.procedure_id, company_id=company_id,
    )
    db.add(trig)
    db.flush()
    _set_relations(db, trig.id, company_id, payload.assignee_ids, payload.team_ids)
    db.commit()
    db.refresh(trig)
    return trig


def list_triggers(db: Session, meter_id: str) -> list[MeterTrigger]:
    return list(db.execute(
        select(MeterTrigger).where(
            MeterTrigger.meter_id == meter_id,
            MeterTrigger.is_active.is_(True),
        ).order_by(MeterTrigger.created_at, MeterTrigger.id)).scalars().all())


def get_trigger(db: Session, trigger_id: str) -> MeterTrigger | None:
    t = db.get(MeterTrigger, trigger_id)
    if t is None or not t.is_active:
        return None
    return t


def update_trigger(db: Session, trig: MeterTrigger, payload: TriggerUpdate, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    data = payload.model_dump(exclude_unset=True)
    new_assignees = data.pop("assignee_ids", None)
    new_teams = data.pop("team_ids", None)
    for k, v in data.items():
        setattr(trig, k, v)
    if "threshold" in data or "comparator" in data:   # 改阈值/比较符 -> 重新武装
        trig.is_armed = True
    if new_assignees is not None:
        db.execute(MeterTriggerAssignee.__table__.delete()
                   .where(MeterTriggerAssignee.trigger_id == trig.id))
        for uid in dict.fromkeys(new_assignees):
            db.add(MeterTriggerAssignee(trigger_id=trig.id, user_id=uid, company_id=company_id))
    if new_teams is not None:
        db.execute(MeterTriggerTeam.__table__.delete()
                   .where(MeterTriggerTeam.trigger_id == trig.id))
        for tid in dict.fromkeys(new_teams):
            db.add(MeterTriggerTeam(trigger_id=trig.id, team_id=tid, company_id=company_id))
    db.commit()
    db.refresh(trig)
    return trig


def delete_trigger(db: Session, trig: MeterTrigger) -> None:
    trig.is_active = False
    trig.deleted_at = utcnow()
    db.commit()


def enable_trigger(db: Session, trig: MeterTrigger, company_id: str,
                   actor_user_id: str | None) -> MeterTrigger:
    trig.is_enabled = True
    db.commit()
    db.refresh(trig)
    return trig


def disable_trigger(db: Session, trig: MeterTrigger, company_id: str,
                    actor_user_id: str | None) -> MeterTrigger:
    trig.is_enabled = False
    db.commit()
    db.refresh(trig)
    return trig
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_trigger_service.py tests/unit/test_meter_decision.py -q`
Expected: PASS（7 + 5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/meter_trigger_service.py backend/tests/unit/test_meter_trigger_service.py
git commit -m "$(printf 'feat(phase-2c): add meter trigger CRUD + relations (re-arm on threshold edit)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: meter_trigger_service.generate_from_trigger（按触发器生单）

**Files:**
- Modify: `backend/app/services/meter_trigger_service.py`
- Test: `backend/tests/unit/test_meter_generate.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_generate.py`:
```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.models.meter_reading import MeterReading
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.schemas.meter import TriggerCreate
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter(db):
    m = Meter(custom_id="MTR000001", name="温度", unit="℃", company_id=CO)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_generate_from_trigger_creates_wo_and_disarms(db: Session):
    m = _meter(db)
    t = ts.create_trigger(db, m.id, TriggerCreate(
        name="高温", comparator=MeterComparator.MORE_THAN, threshold=Decimal("100"),
        title="处理高温", assignee_ids=["u-1"], team_ids=["t-1"], primary_user_id="pu",
    ), CO, actor_user_id="a")
    reading = MeterReading(meter_id=m.id, value=Decimal("150"), company_id=CO,
                           reading_at=datetime(2026, 6, 1, 9, 0))
    db.add(reading)
    db.flush()
    wo = ts.generate_from_trigger(db, t, reading=reading, actor_user_id=None)
    assert isinstance(wo, WorkOrder)
    assert wo.title == "处理高温" and wo.primary_user_id == "pu"
    assert wo.due_date is None                       # 反应式工单无截止日
    assert t.is_armed is False                       # 发火后解除武装
    assert t.last_work_order_id == wo.id
    assert t.last_triggered_at == datetime(2026, 6, 1, 9, 0)
    a = db.query(WorkOrderAssignee).filter_by(work_order_id=wo.id).all()
    tm = db.query(WorkOrderTeam).filter_by(work_order_id=wo.id).all()
    assert {x.user_id for x in a} == {"u-1"}
    assert {x.team_id for x in tm} == {"t-1"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_generate.py -q`
Expected: FAIL（AttributeError: generate_from_trigger）

- [ ] **Step 3: 增补 generate_from_trigger**

在 `backend/app/services/meter_trigger_service.py` 末尾追加：
```python
def generate_from_trigger(db: Session, trig: MeterTrigger, *, reading,
                          actor_user_id: str | None):
    """复制 trigger 预设生成工单，置 last_* 并解除武装。返回 WorkOrder。

    工单服务在函数内 import 避免模块级循环依赖。due_date 留空（反应式工单）。
    create_work_order 内部 commit；trigger 字段变更随调用方末尾 commit 落地。
    """
    from app.schemas.work_order import WorkOrderCreate
    from app.services import work_order_execution_service as exe
    from app.services import work_order_service as wos

    wo_payload = WorkOrderCreate(
        title=trig.title, description=trig.description, priority=trig.priority,
        due_date=None, asset_id=None, location_id=None,
        primary_user_id=trig.primary_user_id,
        assignee_ids=assignee_ids(db, trig.id), team_ids=team_ids(db, trig.id),
    )
    wo = wos.create_work_order(db, wo_payload, trig.company_id, actor_user_id=actor_user_id)
    if trig.procedure_id is not None:
        exe.attach_procedure(db, wo, trig.procedure_id, trig.company_id,
                             actor_user_id=actor_user_id)
    trig.last_triggered_at = reading.reading_at
    trig.last_work_order_id = wo.id
    trig.is_armed = False
    return wo
```

> 注：WO 的 asset/location 本期留空（trigger 不冗余存 meter 的资产；如需可后期从 meter 透传）。`create_work_order` 内部 commit 落地 WO 与指派；`generate_from_trigger` 不自行 commit，由调用方（Task 10 submit_reading）末尾统一 commit trigger 字段变更。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_generate.py -q`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/meter_trigger_service.py backend/tests/unit/test_meter_generate.py
git commit -m "$(printf 'feat(phase-2c): add generate_from_trigger (copy presets, disarm)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: meter_service — Meter CRUD + 读数查询

**Files:**
- Create: `backend/app/services/meter_service.py`
- Test: `backend/tests/unit/test_meter_service.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_service.py`:
```python
from sqlalchemy.orm import Session

from app.schemas.meter import MeterCreate, MeterUpdate
from app.services import meter_service as svc

CO = "co-1"


def test_create_meter_assigns_custom_id(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度", unit="℃", update_frequency_days=7),
                         CO, actor_user_id="a")
    assert m.custom_id == "MTR000001"
    assert m.unit == "℃" and m.update_frequency_days == 7


def test_list_and_filter_meters(db: Session):
    svc.create_meter(db, MeterCreate(name="A", asset_id="as-1"), CO, actor_user_id="a")
    svc.create_meter(db, MeterCreate(name="B", asset_id="as-2"), CO, actor_user_id="a")
    assert len(svc.list_meters(db)) == 2
    got = svc.list_meters(db, asset_id="as-1")
    assert len(got) == 1 and got[0].name == "A"


def test_update_meter(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    svc.update_meter(db, m, MeterUpdate(name="改名", unit="bar"), CO, actor_user_id="a")
    assert m.name == "改名" and m.unit == "bar"


def test_delete_meter_soft(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    svc.delete_meter(db, m)
    assert svc.get_meter(db, m.id) is None


def test_list_readings_empty(db: Session):
    m = svc.create_meter(db, MeterCreate(name="温度"), CO, actor_user_id="a")
    assert svc.list_readings(db, m.id) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_service.py -q`
Expected: FAIL（ModuleNotFoundError: app.services.meter_service）

- [ ] **Step 3: 写实现**

`backend/app/services/meter_service.py`:
```python
"""仪表服务：Meter CRUD、customId、读数提交（同步评估触发器）、读数查询。

submit_reading 编排：插入读数→评估该 meter 全部启用 trigger（边沿决策）→
FIRE 生单、REARM 武装→commit。触发器评估委托 meter_trigger_service。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.schemas.meter import MeterCreate, MeterReadingCreate, MeterUpdate
from app.services import meter_trigger_service as ts
from app.services import sequence_service


def create_meter(db: Session, payload: MeterCreate, company_id: str,
                 actor_user_id: str | None) -> Meter:
    seq = sequence_service.next_value(db, "meter", company_id)
    m = Meter(
        custom_id=sequence_service.format_custom_id("MTR", seq),
        name=payload.name, unit=payload.unit,
        update_frequency_days=payload.update_frequency_days,
        asset_id=payload.asset_id, location_id=payload.location_id,
        company_id=company_id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def list_meters(db: Session, *, asset_id: str | None = None,
                location_id: str | None = None) -> list[Meter]:
    stmt = select(Meter).where(Meter.is_active.is_(True))
    if asset_id is not None:
        stmt = stmt.where(Meter.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(Meter.location_id == location_id)
    return list(db.execute(stmt.order_by(Meter.custom_id)).scalars().all())


def get_meter(db: Session, meter_id: str) -> Meter | None:
    m = db.get(Meter, meter_id)
    if m is None or not m.is_active:
        return None
    return m


def update_meter(db: Session, m: Meter, payload: MeterUpdate, company_id: str,
                 actor_user_id: str | None) -> Meter:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


def delete_meter(db: Session, m: Meter) -> None:
    m.is_active = False
    m.deleted_at = utcnow()
    db.commit()


def list_readings(db: Session, meter_id: str) -> list[MeterReading]:
    return list(db.execute(
        select(MeterReading).where(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.reading_at, MeterReading.id)).scalars().all())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_service.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/meter_service.py backend/tests/unit/test_meter_service.py
git commit -m "$(printf 'feat(phase-2c): add meter service CRUD + readings query\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: meter_service.submit_reading（同步评估触发器）

**Files:**
- Modify: `backend/app/services/meter_service.py`
- Test: `backend/tests/unit/test_meter_submit_reading.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_meter_submit_reading.py`:
```python
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.meter import Meter
from app.models.meter_comparator import MeterComparator
from app.models.work_order import WorkOrder
from app.schemas.meter import MeterCreate, MeterReadingCreate, TriggerCreate
from app.services import meter_service as svc
from app.services import meter_trigger_service as ts

CO = "co-1"


def _meter_with_trigger(db, **trig_kw):
    m = svc.create_meter(db, MeterCreate(name="温度", unit="℃"), CO, actor_user_id="a")
    base = dict(name="高温", comparator=MeterComparator.MORE_THAN,
                threshold=Decimal("100"), title="处理高温")
    base.update(trig_kw)
    t = ts.create_trigger(db, m.id, TriggerCreate(**base), CO, actor_user_id="a")
    return m, t


def test_reading_below_threshold_no_wo(db: Session):
    m, t = _meter_with_trigger(db)
    reading, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("50")),
                                      CO, actor_user_id="a")
    assert wos == []
    db.refresh(t)
    assert t.is_armed is True                        # 未满足，保持武装
    assert db.query(WorkOrder).count() == 0


def test_reading_crosses_threshold_fires_once(db: Session):
    m, t = _meter_with_trigger(db)
    _, wos1 = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                 CO, actor_user_id="a")
    assert len(wos1) == 1
    db.refresh(t)
    assert t.is_armed is False                       # 发火后解除武装
    # 持续超阈：不重复发火
    _, wos2 = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("160")),
                                 CO, actor_user_id="a")
    assert wos2 == []
    assert db.query(WorkOrder).count() == 1


def test_reading_falls_back_then_rearms_and_refires(db: Session):
    m, t = _meter_with_trigger(db)
    svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")), CO, actor_user_id="a")
    svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("50")), CO, actor_user_id="a")
    db.refresh(t)
    assert t.is_armed is True                         # 回落重新武装
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert len(wos) == 1                              # 再次发火
    assert db.query(WorkOrder).count() == 2


def test_disabled_trigger_skipped(db: Session):
    m, t = _meter_with_trigger(db)
    ts.disable_trigger(db, t, CO, actor_user_id="a")
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert wos == []
    db.refresh(t)
    assert t.is_armed is True                         # disabled 既不发火也不改武装态


def test_one_reading_multiple_triggers(db: Session):
    m, _ = _meter_with_trigger(db, name="高温50", threshold=Decimal("50"))
    ts.create_trigger(db, m.id, TriggerCreate(
        name="高温100", comparator=MeterComparator.MORE_THAN,
        threshold=Decimal("100"), title="处理"), CO, actor_user_id="a")
    _, wos = svc.submit_reading(db, m, MeterReadingCreate(value=Decimal("150")),
                                CO, actor_user_id="a")
    assert len(wos) == 2                              # 两个 trigger 同时满足
    assert db.query(WorkOrder).count() == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_submit_reading.py -q`
Expected: FAIL（AttributeError: submit_reading）

- [ ] **Step 3: 增补 submit_reading**

在 `backend/app/services/meter_service.py` 顶部 import 区补充（与现有合并）：
```python
from app.models.meter_trigger import MeterTrigger
```
在文件末尾追加：
```python
def submit_reading(db: Session, m: Meter, payload: MeterReadingCreate, company_id: str,
                   actor_user_id: str | None):
    """插入读数并同步评估该 meter 全部启用 trigger（边沿决策）。

    返回 (reading, generated_work_orders)。FIRE 复用 generate_from_trigger 生单
    （内部 commit 工单）；trigger 状态与读数末尾统一 commit。
    """
    reading = MeterReading(
        meter_id=m.id, value=payload.value,
        reading_at=payload.reading_at or utcnow(),
        recorded_by_user_id=actor_user_id, company_id=company_id,
    )
    db.add(reading)
    db.flush()
    triggers = list(db.execute(
        select(MeterTrigger).where(
            MeterTrigger.meter_id == m.id,
            MeterTrigger.is_active.is_(True),
            MeterTrigger.is_enabled.is_(True),
        ).order_by(MeterTrigger.created_at, MeterTrigger.id)).scalars().all())
    generated = []
    for trig in triggers:
        met = ts._condition_met(trig.comparator, reading.value, trig.threshold)
        action = ts._decide(is_armed=trig.is_armed, met=met)
        if action == "FIRE":
            wo = ts.generate_from_trigger(db, trig, reading=reading,
                                          actor_user_id=actor_user_id)
            generated.append(wo)
        elif action == "REARM":
            trig.is_armed = True
    db.commit()
    db.refresh(reading)
    return reading, generated
```

> 注：`generate_from_trigger` 调用的 `create_work_order` 内部 commit，会一并落地此前 flush 的读数；末尾 `db.commit()` 落地 trigger 武装态变更与无发火时的读数。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_meter_submit_reading.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/meter_service.py backend/tests/unit/test_meter_submit_reading.py
git commit -m "$(printf 'feat(phase-2c): add submit_reading with synchronous edge-trigger evaluation\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: Router + main 挂载

**Files:**
- Create: `backend/app/routers/meters.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_meter_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_meter_api.py`:
```python
"""Meter API 集成测试（Phase 2C）。经 auth API 建主体，不手工 db.add(User)。"""
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


def _meter(client, token, **kw):
    body = {"name": "温度表", "unit": "℃"}
    body.update(kw)
    return client.post("/api/v1/meters", json=body, headers=_h(token))


def _trigger_body(**kw):
    body = {"name": "高温", "comparator": "MORE_THAN", "threshold": "100",
            "title": "处理高温"}
    body.update(kw)
    return body


def test_meter_crud(client):
    t = _admin(client)
    r = _meter(client, t)
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["custom_id"] == "MTR000001"
    got = client.get(f"/api/v1/meters/{mid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["unit"] == "℃"
    upd = client.patch(f"/api/v1/meters/{mid}", json={"name": "改名"}, headers=_h(t))
    assert upd.json()["name"] == "改名"
    assert client.delete(f"/api/v1/meters/{mid}", headers=_h(t)).status_code == 204


def test_trigger_crud_and_enable_disable(client):
    t = _admin(client)
    mid = _meter(client, t).json()["id"]
    r = client.post(f"/api/v1/meters/{mid}/triggers", json=_trigger_body(), headers=_h(t))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["is_armed"] is True
    assert client.post(f"/api/v1/meters/{mid}/triggers/{tid}/disable",
                       headers=_h(t)).json()["is_enabled"] is False
    assert client.post(f"/api/v1/meters/{mid}/triggers/{tid}/enable",
                       headers=_h(t)).json()["is_enabled"] is True
    lst = client.get(f"/api/v1/meters/{mid}/triggers", headers=_h(t))
    assert len(lst.json()) == 1


def test_submit_reading_fires_and_returns_wo_ids(client):
    t = _admin(client)
    mid = _meter(client, t).json()["id"]
    client.post(f"/api/v1/meters/{mid}/triggers",
                json=_trigger_body(assignee_ids=["x"]), headers=_h(t))
    r = client.post(f"/api/v1/meters/{mid}/readings", json={"value": "150"}, headers=_h(t))
    assert r.status_code == 201, r.text
    assert len(r.json()["generated_work_order_ids"]) == 1
    # 读数列表可见
    readings = client.get(f"/api/v1/meters/{mid}/readings", headers=_h(t))
    assert len(readings.json()) == 1


def test_technician_can_read_but_not_configure(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    mid = _meter(client, admin).json()["id"]
    # 不能建仪表
    assert _meter(client, tech, name="x").status_code == 403
    # 不能建触发器
    assert client.post(f"/api/v1/meters/{mid}/triggers", json=_trigger_body(),
                       headers=_h(tech)).status_code == 403
    # 能提交读数
    assert client.post(f"/api/v1/meters/{mid}/readings", json={"value": "1"},
                       headers=_h(tech)).status_code == 201


def test_tenant_isolation(client):
    a = _admin(client)
    mid = _meter(client, a).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/meters/{mid}", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_meter_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/meters.py`:
```python
"""计量 API（/api/v1/meters）：仪表、读数、触发器。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.meter import Meter
from app.models.meter_trigger import MeterTrigger
from app.models.user import User
from app.schemas.meter import (
    MeterCreate,
    MeterRead,
    MeterReadingCreate,
    MeterReadingRead,
    MeterUpdate,
    ReadingResult,
    TriggerCreate,
    TriggerRead,
    TriggerUpdate,
)
from app.services import meter_service as svc
from app.services import meter_trigger_service as ts

router = APIRouter(prefix="/api/v1/meters", tags=["meters"])


def _ensure_meter(m: Meter | None, company_id: str) -> Meter:
    if m is None or m.company_id != company_id:
        raise not_found("METER_NOT_FOUND", "仪表不存在")
    return m


def _ensure_trigger(trig: MeterTrigger | None, meter_id: str, company_id: str) -> MeterTrigger:
    if trig is None or trig.company_id != company_id or trig.meter_id != meter_id:
        raise not_found("METER_TRIGGER_NOT_FOUND", "触发器不存在")
    return trig


def _read_trigger(db: Session, trig: MeterTrigger) -> TriggerRead:
    data = TriggerRead.model_validate(trig)
    data.assignee_ids = ts.assignee_ids(db, trig.id)
    data.team_ids = ts.team_ids(db, trig.id)
    return data


# ---- 仪表 ----
@router.get("", response_model=list[MeterRead])
def list_meters(asset_id: str | None = None, location_id: str | None = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.METER_VIEW))):
    return svc.list_meters(db, asset_id=asset_id, location_id=location_id)


@router.post("", response_model=MeterRead, status_code=status.HTTP_201_CREATED)
def create_meter(payload: MeterCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.METER_CREATE))):
    return svc.create_meter(db, payload, current_user.company_id, actor_user_id=current_user.id)


@router.get("/{meter_id}", response_model=MeterRead)
def get_meter(meter_id: str, db: Session = Depends(get_db),
              current_user: User = Depends(require_permission(permissions.METER_VIEW))):
    return _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)


@router.patch("/{meter_id}", response_model=MeterRead)
def update_meter(meter_id: str, payload: MeterUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.METER_EDIT))):
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return svc.update_meter(db, m, payload, current_user.company_id, actor_user_id=current_user.id)


@router.delete("/{meter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meter(meter_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(require_permission(permissions.METER_DELETE))):
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    svc.delete_meter(db, m)


# ---- 读数 ----
@router.get("/{meter_id}/readings", response_model=list[MeterReadingRead])
def list_readings(meter_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.READING_VIEW))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return svc.list_readings(db, meter_id)


@router.post("/{meter_id}/readings", response_model=ReadingResult,
             status_code=status.HTTP_201_CREATED)
def submit_reading(meter_id: str, payload: MeterReadingCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.READING_CREATE))):
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    reading, wos = svc.submit_reading(db, m, payload, current_user.company_id,
                                      actor_user_id=current_user.id)
    return ReadingResult(reading=MeterReadingRead.model_validate(reading),
                         generated_work_order_ids=[wo.id for wo in wos])


# ---- 触发器 ----
@router.get("/{meter_id}/triggers", response_model=list[TriggerRead])
def list_triggers(meter_id: str, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.METER_VIEW))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    return [_read_trigger(db, t) for t in ts.list_triggers(db, meter_id)]


@router.post("/{meter_id}/triggers", response_model=TriggerRead,
             status_code=status.HTTP_201_CREATED)
def create_trigger(meter_id: str, payload: TriggerCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.METER_CREATE))):
    m = _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = ts.create_trigger(db, m.id, payload, current_user.company_id,
                             actor_user_id=current_user.id)
    return _read_trigger(db, trig)


@router.get("/{meter_id}/triggers/{trigger_id}", response_model=TriggerRead)
def get_trigger(meter_id: str, trigger_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.METER_VIEW))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    return _read_trigger(db, trig)


@router.patch("/{meter_id}/triggers/{trigger_id}", response_model=TriggerRead)
def update_trigger(meter_id: str, trigger_id: str, payload: TriggerUpdate,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.METER_EDIT))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.update_trigger(db, trig, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)


@router.delete("/{meter_id}/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trigger(meter_id: str, trigger_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.METER_DELETE))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.delete_trigger(db, trig)


@router.post("/{meter_id}/triggers/{trigger_id}/enable", response_model=TriggerRead)
def enable_trigger(meter_id: str, trigger_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.METER_EDIT))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.enable_trigger(db, trig, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)


@router.post("/{meter_id}/triggers/{trigger_id}/disable", response_model=TriggerRead)
def disable_trigger(meter_id: str, trigger_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.METER_EDIT))):
    _ensure_meter(svc.get_meter(db, meter_id), current_user.company_id)
    trig = _ensure_trigger(ts.get_trigger(db, trigger_id), meter_id, current_user.company_id)
    ts.disable_trigger(db, trig, current_user.company_id, actor_user_id=current_user.id)
    return _read_trigger(db, trig)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `locations,` 行之后插入一行：
```python
    meters,
```
在 `app.include_router(preventive_maintenances.router)` 行之后插入：
```python
app.include_router(meters.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_meter_api.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/meters.py backend/app/main.py backend/tests/test_meter_api.py
git commit -m "$(printf 'feat(phase-2c): add Meter router (meters/readings/triggers) + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 12: 全量回归 + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/meter_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 763 + 新增；0 failed）。Read tee 文件确认真实摘要行（防陈旧回放）。

- [ ] **Step 2: 确认工作树与提交链干净**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git status --porcelain && git log --oneline -12
```
Expected: porcelain 为空；最近提交含 Task 1–11 各一次。

- [ ] **Step 3: alembic 单 head 校验**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads`
Expected: 仅 `phase2c_meter (head)`

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含新增 Meter 单测 + API 测 + 契约/迁移测）。
- `tb_meter` / `tb_meter_reading` / `tb_meter_trigger` / `tb_meter_trigger_assignee` / `tb_meter_trigger_team` 五表经迁移可 upgrade/downgrade。
- `/api/v1/meters` 全套端点工作；提交读数边沿命中自动生单并返回工单 id；technician 能抄表、不能建仪表/触发器；跨租户隔离 404。
- 边沿状态机正确：满足跨入发火并解武装、回落重武装、持续满足不重复发火；编辑 threshold/comparator 重新武装。
- `git status --porcelain` 干净，alembic 单 head `phase2c_meter`。
