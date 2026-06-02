# 工单补全 2A · WO3 工时成本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给工单加上工时（Labor，计时器+手填）、工时分类（TimeCategory，默认费率）、额外成本（AdditionalCost，复用 CostCategory），以及总成本实时聚合接口——全后端、净室原创。

**Architecture:** 3 张新表全挂 `TenantMixin`；TimeCategory 镜像现有 CostCategory 全切片；Labor/AdditionalCost 作为 `/api/v1/work-orders/{id}` 子资源放独立 router（不改 `work_orders.py`，照 `part_consumptions.py`）；总成本不落字段、由 `work_order_cost_service` 实时 SUM 三类明细（labor + additional + 现有 `PartConsumption`）。费率走 TimeCategory 默认 + Labor 行快照可覆盖。读=`work_order.view`，写=`work_order.edit`；TimeCategory 主数据新增 `time_category.view/manage`。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（`Mapped`/`mapped_column`）+ Pydantic v2（`computed_field`，Decimal 序列化为字符串）+ Alembic + pytest（SQLite 内存，`Base.metadata.create_all`）。门禁 ruff 0.15 / mypy 1.20，解释器 `backend/.venv/bin/python`。

**净室红线：** 全新原创命名（`tb_time_category`/`tb_work_order_labor`/`tb_work_order_additional_cost`），不复制 Atlas 代码/DDL/文案/命名；产品无 "Atlas"。

**所有命令在 `backend/` 目录下执行。**

---

## 文件结构

| 文件 | 职责 | 任务 |
|---|---|---|
| `app/models/time_category.py` | TimeCategory 模型（镜像 CostCategory）| T1 |
| `app/models/work_order_labor.py` | Labor 模型 | T2 |
| `app/models/work_order_additional_cost.py` | AdditionalCost 模型 | T4 |
| `app/schemas/work_order_cost.py` | 本组全部 schema（TimeCategory/Labor/AdditionalCost/CostSummary）| T1,T2,T4,T5 |
| `app/services/time_category_service.py` | TimeCategory CRUD（软删）| T1 |
| `app/services/work_order_labor_service.py` | Labor 业务（费率解析/计时器/手填/CRUD）| T2 |
| `app/services/work_order_additional_cost_service.py` | AdditionalCost CRUD | T4 |
| `app/services/work_order_cost_service.py` | 总成本实时聚合 | T5 |
| `app/routers/time_categories.py` | `/api/v1/time-categories`（镜像 cost_categories）| T1 |
| `app/routers/work_order_costs.py` | `/api/v1/work-orders/{id}` 下 labor + additional-costs + cost-summary | T3,T4,T5 |
| `app/permissions.py` | 新增 `time_category.*` | T1 |
| `app/models/__init__.py` | 注册 3 个新模型 | T1,T2,T4 |
| `app/main.py` | 挂载 2 个新 router | T1,T3 |
| `alembic/versions/20260602_0003_workorder_labor_cost.py` | 建 3 表迁移 | T6 |
| `tests/test_time_category_api.py` | T1 测试 | T1 |
| `tests/test_work_order_labor_service.py` | T2 测试 | T2 |
| `tests/test_work_order_labor_api.py` | T3 测试 | T3 |
| `tests/test_work_order_additional_cost_api.py` | T4 测试 | T4 |
| `tests/test_work_order_cost_summary_api.py` | T5 测试 | T5 |
| `tests/test_migration_labor_cost.py` | T6 迁移测试 | T6 |

**测试公用片段（每个 API 测试文件顶部复制；与现有测试一致）：**

```python
from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]
```

---

## Task 1: TimeCategory 全切片（模型 + schema + 服务 + 路由 + 权限）

**Files:**
- Create: `app/models/time_category.py`
- Create: `app/schemas/work_order_cost.py`
- Create: `app/services/time_category_service.py`
- Create: `app/routers/time_categories.py`
- Modify: `app/permissions.py`（新增 `time_category.*`）
- Modify: `app/models/__init__.py`（注册 TimeCategory）
- Modify: `app/main.py`（挂 time_categories.router）
- Test: `tests/test_time_category_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_time_category_api.py`：

```python
from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "tech@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_time_category_crud(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/time-categories",
        json={"name": "常规工时", "hourly_rate": "80.00"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert float(r.json()["hourly_rate"]) == 80.0
    assert client.get("/api/v1/time-categories", headers=_h(t)).status_code == 200
    upd = client.patch(
        f"/api/v1/time-categories/{cid}", json={"hourly_rate": "120"}, headers=_h(t)
    )
    assert float(upd.json()["hourly_rate"]) == 120.0
    assert client.delete(f"/api/v1/time-categories/{cid}", headers=_h(t)).status_code == 204
    # 软删后不在列表
    assert client.get("/api/v1/time-categories", headers=_h(t)).json() == []


def test_time_category_default_rate_zero(client):
    t = _admin(client)
    r = client.post("/api/v1/time-categories", json={"name": "无费率"}, headers=_h(t))
    assert r.status_code == 201, r.text
    assert float(r.json()["hourly_rate"]) == 0.0


def test_time_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post(
        "/api/v1/time-categories", json={"name": "X"}, headers=_h(a)
    ).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/time-categories/{cid}", headers=_h(b)).status_code == 404


def test_time_category_technician_cannot_manage(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    # technician 有 view 无 manage
    assert client.get("/api/v1/time-categories", headers=_h(tech)).status_code == 200
    r = client.post("/api/v1/time-categories", json={"name": "x"}, headers=_h(tech))
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_time_category_api.py -q`
Expected: FAIL（404/路由不存在）。

- [ ] **Step 3: 模型 `app/models/time_category.py`**

```python
"""工时分类（每租户）。镜像 CostCategory，带默认小时费率。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class TimeCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_time_category"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_time_category_company_name"),)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 4: schema `app/schemas/work_order_cost.py`（本任务先放 TimeCategory 段）**

```python
"""工单工时成本 schema（TimeCategory / Labor / AdditionalCost / CostSummary）。"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TimeCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    description: str = ""


class TimeCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    description: str | None = None


class TimeCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    hourly_rate: Decimal
    description: str
```

- [ ] **Step 5: 服务 `app/services/time_category_service.py`（镜像 cost_category_service）**

```python
"""工时分类服务：CRUD（软删）。镜像 cost_category_service。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.time_category import TimeCategory
from app.schemas.work_order_cost import TimeCategoryCreate, TimeCategoryUpdate


def create_time_category(
    db: Session, payload: TimeCategoryCreate, company_id: str, actor_user_id: str | None
) -> TimeCategory:
    cat = TimeCategory(
        name=payload.name,
        hourly_rate=payload.hourly_rate,
        description=payload.description,
        company_id=company_id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_time_categories(db: Session) -> list[TimeCategory]:
    return list(
        db.execute(
            select(TimeCategory)
            .where(TimeCategory.is_active.is_(True))
            .order_by(TimeCategory.name, TimeCategory.id)
        )
        .scalars()
        .all()
    )


def get_time_category(db: Session, category_id: str) -> TimeCategory | None:
    c = db.get(TimeCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_time_category(
    db: Session,
    cat: TimeCategory,
    payload: TimeCategoryUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> TimeCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_time_category(db: Session, cat: TimeCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
```

- [ ] **Step 6: 权限 `app/permissions.py`**

紧接 `COST_CATEGORY_MANAGE = "cost_category.manage"`（约第 83 行）之后新增：

```python
TIME_CATEGORY_VIEW = "time_category.view"
TIME_CATEGORY_MANAGE = "time_category.manage"
```

在 `_COST_CATEGORY = [COST_CATEGORY_VIEW, COST_CATEGORY_MANAGE]` 之后新增分组：

```python
_TIME_CATEGORY = [TIME_CATEGORY_VIEW, TIME_CATEGORY_MANAGE]
```

`ALL_PERMISSIONS` 的求和表达式里，在 `+ _COST_CATEGORY` 之后加入 `+ _TIME_CATEGORY`：

```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM
    + _BASE_DOMAIN
    + _WORKORDER
    + _REQUEST
    + _PREVENTIVE_MAINTENANCE
    + _METER
    + _READING
    + _PART
    + _PART_CATEGORY
    + _VENDOR
    + _CUSTOMER
    + _COST_CATEGORY
    + _TIME_CATEGORY
    + _PURCHASE_ORDER
    + _ANALYTICS
)
```

在 `technician` 内置角色 permissions 列表里，紧接 `COST_CATEGORY_VIEW,` 之后加入 `TIME_CATEGORY_VIEW,`（technician 只读工时分类，靠 `WORK_ORDER_EDIT` 写工时）。

- [ ] **Step 7: 路由 `app/routers/time_categories.py`（镜像 cost_categories.py）**

```python
"""工时分类 API（/api/v1/time-categories）。镜像 cost-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.time_category import TimeCategory
from app.models.user import User
from app.schemas.work_order_cost import (
    TimeCategoryCreate,
    TimeCategoryRead,
    TimeCategoryUpdate,
)
from app.services import time_category_service as svc

router = APIRouter(prefix="/api/v1/time-categories", tags=["time-categories"])


def _ensure(c: TimeCategory | None, company_id: str) -> TimeCategory:
    if c is None or c.company_id != company_id:
        raise not_found("TIME_CATEGORY_NOT_FOUND", "工时分类不存在")
    return c


@router.get("", response_model=list[TimeCategoryRead])
def list_time_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_VIEW)),
) -> list[TimeCategory]:
    return svc.list_time_categories(db)


@router.post("", response_model=TimeCategoryRead, status_code=status.HTTP_201_CREATED)
def create_time_category(
    payload: TimeCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> TimeCategory:
    return svc.create_time_category(
        db, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.get("/{category_id}", response_model=TimeCategoryRead)
def get_time_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_VIEW)),
) -> TimeCategory:
    return _ensure(svc.get_time_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=TimeCategoryRead)
def update_time_category(
    category_id: str,
    payload: TimeCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> TimeCategory:
    c = _ensure(svc.get_time_category(db, category_id), current_user.company_id)
    return svc.update_time_category(
        db, c, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_time_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> None:
    c = _ensure(svc.get_time_category(db, category_id), current_user.company_id)
    svc.delete_time_category(db, c)
```

- [ ] **Step 8: 注册模型与路由**

`app/models/__init__.py`：在 `from app.models.team import ...` 区域按字母序加入导入（紧邻已有 import 序），并在 `__all__` 加 `"TimeCategory"`：

```python
from app.models.time_category import TimeCategory
```
（`__all__` 列表里加 `"TimeCategory",`，紧邻 `"Team"` 等条目，保持与现有风格一致。）

`app/main.py`：在 import 区加入 `time_categories`（与 `cost_categories` 同区），并在路由挂载区 `app.include_router(cost_categories.router)` 附近加：

```python
app.include_router(time_categories.router)
```

- [ ] **Step 9: 跑测试确认通过 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_time_category_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 4 passed；ruff/mypy 全绿。

- [ ] **Step 10: Commit**

```bash
git add app/models/time_category.py app/schemas/work_order_cost.py \
  app/services/time_category_service.py app/routers/time_categories.py \
  app/permissions.py app/models/__init__.py app/main.py \
  tests/test_time_category_api.py
git commit -m "$(cat <<'EOF'
feat(workorder): TimeCategory master data (2A)

工时分类 per-company，带默认小时费率；CRUD 软删，镜像 CostCategory。
新增权限 time_category.view/manage；technician 仅 view。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Labor 模型 + 服务（费率解析 / 计时器 / 手填 / CRUD）

**Files:**
- Create: `app/models/work_order_labor.py`
- Modify: `app/schemas/work_order_cost.py`（加 Labor 段）
- Create: `app/services/work_order_labor_service.py`
- Modify: `app/models/__init__.py`（注册 Labor）
- Test: `tests/test_work_order_labor_service.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_labor_service.py`（service 级，用 `db`/`factory` fixture 与 tenant 上下文）：

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app import tenant
from app.errors import HTTPExceptionShim  # 占位：见下方说明，实际用 fastapi.HTTPException
from app.models.company import Company
from app.models.time_category import TimeCategory
from app.models.work_order import WorkOrder
from app.services import sequence_service
from app.services import work_order_labor_service as labor
```

> 说明：上面 `HTTPExceptionShim` 仅占位提示；实际请 `from fastapi import HTTPException` 并捕获。改为如下完整文件：

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.time_category import TimeCategory
from app.models.work_order import WorkOrder
from app.schemas.work_order_cost import LaborCreate, LaborTimerStart, LaborUpdate
from app.services import sequence_service
from app.services import work_order_labor_service as labor


def _company(db, slug="acme"):
    c = Company(name=slug.title(), slug=slug)
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    return c.id


def _wo(db, company_id, title="检修"):
    seq = sequence_service.next_value(db, "work_order", company_id)
    wo = WorkOrder(
        custom_id=sequence_service.format_custom_id("WO", seq),
        title=title,
        company_id=company_id,
    )
    db.add(wo)
    db.commit()
    return wo


def test_manual_labor_cost(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=3600, hourly_rate=Decimal("80")), cid, actor_user_id=None
    )
    # 1 小时 * 80 = 80
    assert row.duration_seconds == 3600
    assert row.hourly_rate == Decimal("80")
    assert labor.compute_cost(row) == Decimal("80.00")


def test_rate_defaults_from_category(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=1800, time_category_id=cat.id), cid, actor_user_id=None
    )
    # 分类默认费率快照
    assert row.hourly_rate == Decimal("100")
    assert labor.compute_cost(row) == Decimal("50.00")


def test_explicit_rate_overrides_category(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db,
        wo,
        LaborCreate(duration_seconds=3600, time_category_id=cat.id, hourly_rate=Decimal("60")),
        cid,
        actor_user_id=None,
    )
    assert row.hourly_rate == Decimal("60")


def test_category_changing_does_not_touch_snapshot(db):
    cid = _company(db)
    wo = _wo(db, cid)
    cat = TimeCategory(name="常规", hourly_rate=Decimal("100"), company_id=cid)
    db.add(cat)
    db.commit()
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=3600, time_category_id=cat.id), cid, actor_user_id=None
    )
    cat.hourly_rate = Decimal("999")
    db.commit()
    db.refresh(row)
    assert row.hourly_rate == Decimal("100")  # 快照不变


def test_unknown_category_404(db):
    cid = _company(db)
    wo = _wo(db, cid)
    with pytest.raises(HTTPException) as e:
        labor.create_labor(
            db, wo, LaborCreate(duration_seconds=10, time_category_id="nope"), cid, actor_user_id=None
        )
    assert e.value.status_code == 404


def test_timer_start_stop(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.start_timer(db, wo, LaborTimerStart(hourly_rate=Decimal("60")), cid, actor_user_id="u1")
    assert row.started_at is not None and row.stopped_at is None
    assert labor.is_running(row) is True
    assert labor.compute_cost(row) == Decimal("0.00")  # 运行中不入账
    # 手工把 started_at 往前挪 1 小时，stop 后应得 3600s
    from datetime import timedelta

    row.started_at = row.started_at - timedelta(hours=1)
    db.commit()
    stopped = labor.stop_timer(db, row)
    assert stopped.stopped_at is not None
    assert stopped.duration_seconds == pytest.approx(3600, abs=5)


def test_timer_double_start_conflict(db):
    cid = _company(db)
    wo = _wo(db, cid)
    labor.start_timer(db, wo, LaborTimerStart(user_id="u1"), cid, actor_user_id="u1")
    with pytest.raises(HTTPException) as e:
        labor.start_timer(db, wo, LaborTimerStart(user_id="u1"), cid, actor_user_id="u1")
    assert e.value.status_code == 409


def test_stop_non_running_400(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=600, hourly_rate=Decimal("10")), cid, actor_user_id=None
    )
    with pytest.raises(HTTPException) as e:
        labor.stop_timer(db, row)
    assert e.value.status_code == 400


def test_update_and_delete(db):
    cid = _company(db)
    wo = _wo(db, cid)
    row = labor.create_labor(
        db, wo, LaborCreate(duration_seconds=600, hourly_rate=Decimal("10")), cid, actor_user_id=None
    )
    labor.update_labor(db, row, LaborUpdate(duration_seconds=1200, hourly_rate=Decimal("20")))
    assert row.duration_seconds == 1200
    assert row.hourly_rate == Decimal("20")
    labor.delete_labor(db, row)
    assert labor.list_labor(db, wo.id) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_work_order_labor_service.py -q`
Expected: FAIL（模块/类不存在）。

- [ ] **Step 3: 模型 `app/models/work_order_labor.py`**

```python
"""工单工时（每租户）。计时器（started/stopped）与手填（duration_seconds）二合一。

成本计算唯一依据为 duration_seconds；运行中（stopped_at 为空）行 duration 为 0、
不入账，stop 时才落定。hourly_rate 为创建时快照，不随 TimeCategory 改动而变。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderLabor(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_labor"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), default=None, index=True
    )
    time_category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_time_category.id", ondelete="RESTRICT"), default=None
    )
    started_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    stopped_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 4: schema 追加 Labor 段（追加到 `app/schemas/work_order_cost.py` 末尾）**

```python
from datetime import datetime  # 置于文件顶部 import 区


class LaborCreate(BaseModel):
    """手填一条工时（duration_seconds 必填）。"""

    duration_seconds: int = Field(ge=0)
    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    notes: str = ""


class LaborTimerStart(BaseModel):
    """开计时器。"""

    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    notes: str = ""


class LaborUpdate(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0)
    time_category_id: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    user_id: str | None = None
    notes: str | None = None


class LaborRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_order_id: str
    user_id: str | None = None
    time_category_id: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    duration_seconds: int
    hourly_rate: Decimal
    notes: str

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def running(self) -> bool:
        return self.started_at is not None and self.stopped_at is None

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def cost(self) -> Decimal:
        from decimal import ROUND_HALF_UP

        if self.running:
            return Decimal("0.00")
        raw = Decimal(self.duration_seconds) / Decimal(3600) * self.hourly_rate
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @computed_field  # type: ignore[prop-decorator]  # pydantic computed_field
    @property
    def running_elapsed_seconds(self) -> int | None:
        if not self.running or self.started_at is None:
            return None
        from app.models.base import utcnow

        return max(0, int((utcnow() - self.started_at).total_seconds()))
```

文件顶部 import 行改为：

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field
```

- [ ] **Step 5: 服务 `app/services/work_order_labor_service.py`**

```python
"""工单工时服务：费率解析、计时器（start/stop）、手填、CRUD。

成本计算（compute_cost）为纯函数，不依赖 now()；运行中行计 0。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found
from app.models.base import utcnow
from app.models.time_category import TimeCategory
from app.models.work_order import WorkOrder
from app.models.work_order_labor import WorkOrderLabor
from app.schemas.work_order_cost import LaborCreate, LaborTimerStart, LaborUpdate

_CENT = Decimal("0.01")


def is_running(row: WorkOrderLabor) -> bool:
    return row.started_at is not None and row.stopped_at is None


def compute_cost(row: WorkOrderLabor) -> Decimal:
    if is_running(row):
        return Decimal("0.00")
    raw = Decimal(row.duration_seconds) / Decimal(3600) * row.hourly_rate
    return raw.quantize(_CENT, rounding=ROUND_HALF_UP)


def _resolve_rate(
    db: Session,
    company_id: str,
    time_category_id: str | None,
    hourly_rate: Decimal | None,
) -> Decimal:
    cat: TimeCategory | None = None
    if time_category_id is not None:
        cat = db.get(TimeCategory, time_category_id)
        if cat is None or cat.company_id != company_id or not cat.is_active:
            raise not_found("TIME_CATEGORY_NOT_FOUND", "工时分类不存在")
    if hourly_rate is not None:
        return hourly_rate
    if cat is not None:
        return cat.hourly_rate
    return Decimal("0")


def list_labor(db: Session, work_order_id: str) -> list[WorkOrderLabor]:
    return list(
        db.execute(
            select(WorkOrderLabor)
            .where(WorkOrderLabor.work_order_id == work_order_id)
            .order_by(WorkOrderLabor.created_at, WorkOrderLabor.id)
        )
        .scalars()
        .all()
    )


def create_labor(
    db: Session,
    wo: WorkOrder,
    payload: LaborCreate,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderLabor:
    rate = _resolve_rate(db, company_id, payload.time_category_id, payload.hourly_rate)
    row = WorkOrderLabor(
        work_order_id=wo.id,
        user_id=payload.user_id if payload.user_id is not None else actor_user_id,
        time_category_id=payload.time_category_id,
        started_at=payload.started_at,
        stopped_at=payload.stopped_at,
        duration_seconds=payload.duration_seconds,
        hourly_rate=rate,
        notes=payload.notes,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start_timer(
    db: Session,
    wo: WorkOrder,
    payload: LaborTimerStart,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderLabor:
    uid = payload.user_id if payload.user_id is not None else actor_user_id
    # 同 (work_order, user) 至多一个运行中计时器
    existing = db.execute(
        select(WorkOrderLabor).where(
            WorkOrderLabor.work_order_id == wo.id,
            WorkOrderLabor.user_id == uid,
            WorkOrderLabor.started_at.is_not(None),
            WorkOrderLabor.stopped_at.is_(None),
        )
    ).first()
    if existing is not None:
        raise conflict("LABOR_TIMER_RUNNING", "已有运行中的计时器")
    rate = _resolve_rate(db, company_id, payload.time_category_id, payload.hourly_rate)
    row = WorkOrderLabor(
        work_order_id=wo.id,
        user_id=uid,
        time_category_id=payload.time_category_id,
        started_at=utcnow(),
        stopped_at=None,
        duration_seconds=0,
        hourly_rate=rate,
        notes=payload.notes,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def stop_timer(db: Session, row: WorkOrderLabor) -> WorkOrderLabor:
    if not is_running(row):
        raise bad_request("LABOR_NOT_RUNNING", "该工时不是运行中的计时器")
    row.stopped_at = utcnow()
    assert row.started_at is not None  # is_running 保证
    row.duration_seconds = max(0, int((row.stopped_at - row.started_at).total_seconds()))
    db.commit()
    db.refresh(row)
    return row


def update_labor(
    db: Session,
    row: WorkOrderLabor,
    payload: LaborUpdate,
) -> WorkOrderLabor:
    data = payload.model_dump(exclude_unset=True)
    # time_category_id 改动时若未显式给 hourly_rate，仍保留原快照（不自动改价）。
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_labor(db: Session, row: WorkOrderLabor) -> None:
    db.delete(row)
    db.commit()
```

> mypy 注意：`stop_timer` 里用 `assert row.started_at is not None` 收窄 `datetime | None`。

- [ ] **Step 6: 注册模型**

`app/models/__init__.py`：加入

```python
from app.models.work_order_labor import WorkOrderLabor
```
并在 `__all__` 加 `"WorkOrderLabor",`（紧邻已有 `WorkOrder*` 条目）。

- [ ] **Step 7: 跑测试 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_work_order_labor_service.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 passed；ruff/mypy 全绿。

- [ ] **Step 8: Commit**

```bash
git add app/models/work_order_labor.py app/schemas/work_order_cost.py \
  app/services/work_order_labor_service.py app/models/__init__.py \
  tests/test_work_order_labor_service.py
git commit -m "$(cat <<'EOF'
feat(workorder): Labor model + service (timer/manual, rate snapshot) (2A)

工时计时器(start/stop)+手填二合一；费率从 TimeCategory 默认取、行快照可覆盖；
运行中计 0、stop 落定 duration_seconds；成本计算纯函数不依赖 now()。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Labor 路由（`/api/v1/work-orders/{id}/labor`）

**Files:**
- Create: `app/routers/work_order_costs.py`（本任务先建 labor 段）
- Modify: `app/main.py`（挂 work_order_costs.router）
- Test: `tests/test_work_order_labor_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_labor_api.py`：

```python
from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def _viewer_token(client, admin):
    # 自建只读角色（仅 work_order.view），用于 403 验证
    rid = client.post(
        "/api/v1/roles",
        headers=_h(admin),
        json={"code": "wo_viewer", "name": "工单只读", "permissions": ["work_order.view"]},
    ).json()["id"]
    client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={"email": "v@acme.com", "password": "secret123", "name": "V", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "v@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_manual_labor_crud(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 3600, "hourly_rate": "80"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert float(r.json()["cost"]) == 80.0
    assert r.json()["running"] is False
    lst = client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(t)).json()
    assert len(lst) == 1
    upd = client.patch(
        f"/api/v1/work-orders/{wo}/labor/{lid}",
        json={"duration_seconds": 1800},
        headers=_h(t),
    )
    assert upd.json()["duration_seconds"] == 1800
    assert client.delete(f"/api/v1/work-orders/{wo}/labor/{lid}", headers=_h(t)).status_code == 204


def test_timer_start_stop(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    start = client.post(
        f"/api/v1/work-orders/{wo}/labor/start", json={"hourly_rate": "60"}, headers=_h(t)
    )
    assert start.status_code == 201, start.text
    lid = start.json()["id"]
    assert start.json()["running"] is True
    assert float(start.json()["cost"]) == 0.0
    stop = client.post(f"/api/v1/work-orders/{wo}/labor/{lid}/stop", headers=_h(t))
    assert stop.status_code == 200, stop.text
    assert stop.json()["running"] is False


def test_timer_double_start_409(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    client.post(f"/api/v1/work-orders/{wo}/labor/start", json={}, headers=_h(t))
    r = client.post(f"/api/v1/work-orders/{wo}/labor/start", json={}, headers=_h(t))
    assert r.status_code == 409


def test_stop_non_running_400(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    lid = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(t),
    ).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wo}/labor/{lid}/stop", headers=_h(t))
    assert r.status_code == 400


def test_labor_tenant_isolation(client):
    a = _admin(client)
    wo = _wo_id(client, a)
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(a),
    )
    b = _admin(client, company="Beta", email="admin@beta.com")
    # B 访问 A 的工单 → 404
    assert client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(b)).status_code == 404


def test_labor_requires_edit_permission(client):
    admin = _admin(client)
    wo = _wo_id(client, admin)
    viewer = _viewer_token(client, admin)
    assert client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(viewer)).status_code == 200
    r = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(viewer),
    )
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_work_order_labor_api.py -q`
Expected: FAIL（404，路由未挂）。

- [ ] **Step 3: 路由 `app/routers/work_order_costs.py`（labor 段）**

```python
"""工单成本子资源 API（/api/v1/work-orders/{id}）：工时 / 额外成本 / 总成本汇总。

独立 router，不改 work_orders.py（照 part_consumptions.py）。
读=work_order.view，写=work_order.edit。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_labor import WorkOrderLabor
from app.schemas.work_order_cost import (
    LaborCreate,
    LaborRead,
    LaborTimerStart,
    LaborUpdate,
)
from app.services import work_order_labor_service as labor
from app.services import work_order_service as wos

router = APIRouter(prefix="/api/v1/work-orders/{work_order_id}", tags=["work-order-costs"])


def _ensure_wo(db: Session, work_order_id: str, company_id: str) -> WorkOrder:
    wo = wos.get_work_order(db, work_order_id)
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


def _ensure_labor(
    db: Session, labor_id: str, work_order_id: str, company_id: str
) -> WorkOrderLabor:
    row = db.get(WorkOrderLabor, labor_id)
    if (
        row is None
        or row.work_order_id != work_order_id
        or row.company_id != company_id
    ):
        raise not_found("LABOR_NOT_FOUND", "工时记录不存在")
    return row


@router.get("/labor", response_model=list[LaborRead])
def list_labor(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[WorkOrderLabor]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.list_labor(db, work_order_id)


@router.post("/labor", response_model=LaborRead, status_code=status.HTTP_201_CREATED)
def create_labor(
    work_order_id: str,
    payload: LaborCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.create_labor(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.post("/labor/start", response_model=LaborRead, status_code=status.HTTP_201_CREATED)
def start_timer(
    work_order_id: str,
    payload: LaborTimerStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return labor.start_timer(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.post("/labor/{labor_id}/stop", response_model=LaborRead)
def stop_timer(
    work_order_id: str,
    labor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    return labor.stop_timer(db, row)


@router.patch("/labor/{labor_id}", response_model=LaborRead)
def update_labor(
    work_order_id: str,
    labor_id: str,
    payload: LaborUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderLabor:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    return labor.update_labor(db, row, payload)


@router.delete("/labor/{labor_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_labor(
    work_order_id: str,
    labor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_labor(db, labor_id, work_order_id, current_user.company_id)
    labor.delete_labor(db, row)
```

> 路由顺序注意：`/labor/start` 必须在 `/labor/{labor_id}/stop` 之前不冲突；FastAPI 按声明匹配，`/labor/start`（静态）与 `/labor/{labor_id}/stop` 路径段数不同，不冲突。

- [ ] **Step 4: 挂载路由**

`app/main.py`：import 区加 `work_order_costs`，挂载区加：

```python
app.include_router(work_order_costs.router)
```

- [ ] **Step 5: 跑测试 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_work_order_labor_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 passed；门禁全绿。

- [ ] **Step 6: Commit**

```bash
git add app/routers/work_order_costs.py app/main.py tests/test_work_order_labor_api.py
git commit -m "$(cat <<'EOF'
feat(workorder): Labor REST endpoints (timer/manual CRUD) (2A)

/api/v1/work-orders/{id}/labor + /labor/start + /labor/{id}/stop；
写=work_order.edit 读=work_order.view；跨租户 404、双开计时器 409、停非运行 400。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: AdditionalCost 全切片（模型 + schema + 服务 + 路由）

**Files:**
- Create: `app/models/work_order_additional_cost.py`
- Modify: `app/schemas/work_order_cost.py`（加 AdditionalCost 段）
- Create: `app/services/work_order_additional_cost_service.py`
- Modify: `app/routers/work_order_costs.py`（加 additional-costs 段）
- Modify: `app/models/__init__.py`（注册）
- Test: `tests/test_work_order_additional_cost_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_additional_cost_api.py`：

```python
from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def test_additional_cost_crud(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # 复用现有成本分类
    cat = client.post("/api/v1/cost-categories", json={"name": "差旅"}, headers=_h(t)).json()["id"]
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "打车", "amount": "33.50", "cost_category_id": cat},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert float(r.json()["amount"]) == 33.5
    assert r.json()["cost_category_id"] == cat
    lst = client.get(f"/api/v1/work-orders/{wo}/additional-costs", headers=_h(t)).json()
    assert len(lst) == 1
    upd = client.patch(
        f"/api/v1/work-orders/{wo}/additional-costs/{aid}",
        json={"amount": "40"},
        headers=_h(t),
    )
    assert float(upd.json()["amount"]) == 40.0
    assert (
        client.delete(
            f"/api/v1/work-orders/{wo}/additional-costs/{aid}", headers=_h(t)
        ).status_code
        == 204
    )


def test_additional_cost_no_category(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "杂费", "amount": "10"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    assert r.json()["cost_category_id"] is None


def test_additional_cost_negative_amount_422(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "x", "amount": "-1"},
        headers=_h(t),
    )
    assert r.status_code == 422


def test_additional_cost_tenant_isolation(client):
    a = _admin(client)
    wo = _wo_id(client, a)
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "x", "amount": "1"},
        headers=_h(a),
    )
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert (
        client.get(f"/api/v1/work-orders/{wo}/additional-costs", headers=_h(b)).status_code == 404
    )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_work_order_additional_cost_api.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 模型 `app/models/work_order_additional_cost.py`**

```python
"""工单额外成本（每租户）。cost_category_id 复用现有 CostCategory（可空）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderAdditionalCost(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_additional_cost"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    cost_category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_cost_category.id", ondelete="RESTRICT"), default=None
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
```

- [ ] **Step 4: schema 追加 AdditionalCost 段（追加到 `app/schemas/work_order_cost.py`）**

```python
class AdditionalCostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    amount: Decimal = Field(ge=0)
    cost_category_id: str | None = None
    description: str = ""


class AdditionalCostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    amount: Decimal | None = Field(default=None, ge=0)
    cost_category_id: str | None = None
    description: str | None = None


class AdditionalCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_order_id: str
    cost_category_id: str | None = None
    title: str
    amount: Decimal
    description: str
    created_by_user_id: str | None = None
```

- [ ] **Step 5: 服务 `app/services/work_order_additional_cost_service.py`**

```python
"""工单额外成本服务：CRUD（硬删）。cost_category 复用现有 CostCategory。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.cost_category import CostCategory
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.schemas.work_order_cost import AdditionalCostCreate, AdditionalCostUpdate


def _validate_category(db: Session, company_id: str, cost_category_id: str | None) -> None:
    if cost_category_id is None:
        return
    cat = db.get(CostCategory, cost_category_id)
    if cat is None or cat.company_id != company_id or not cat.is_active:
        raise not_found("COST_CATEGORY_NOT_FOUND", "成本分类不存在")


def list_additional_costs(db: Session, work_order_id: str) -> list[WorkOrderAdditionalCost]:
    return list(
        db.execute(
            select(WorkOrderAdditionalCost)
            .where(WorkOrderAdditionalCost.work_order_id == work_order_id)
            .order_by(WorkOrderAdditionalCost.created_at, WorkOrderAdditionalCost.id)
        )
        .scalars()
        .all()
    )


def create_additional_cost(
    db: Session,
    wo: WorkOrder,
    payload: AdditionalCostCreate,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderAdditionalCost:
    _validate_category(db, company_id, payload.cost_category_id)
    row = WorkOrderAdditionalCost(
        work_order_id=wo.id,
        cost_category_id=payload.cost_category_id,
        title=payload.title,
        amount=payload.amount,
        description=payload.description,
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_additional_cost(
    db: Session,
    row: WorkOrderAdditionalCost,
    payload: AdditionalCostUpdate,
    company_id: str,
) -> WorkOrderAdditionalCost:
    data = payload.model_dump(exclude_unset=True)
    if "cost_category_id" in data:
        _validate_category(db, company_id, data["cost_category_id"])
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_additional_cost(db: Session, row: WorkOrderAdditionalCost) -> None:
    db.delete(row)
    db.commit()
```

- [ ] **Step 6: 路由追加（追加到 `app/routers/work_order_costs.py`）**

import 区补充：

```python
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.schemas.work_order_cost import (
    AdditionalCostCreate,
    AdditionalCostRead,
    AdditionalCostUpdate,
)
from app.services import work_order_additional_cost_service as addcost
```

新增 `_ensure_cost` 助手与端点：

```python
def _ensure_cost(
    db: Session, cost_id: str, work_order_id: str, company_id: str
) -> WorkOrderAdditionalCost:
    row = db.get(WorkOrderAdditionalCost, cost_id)
    if (
        row is None
        or row.work_order_id != work_order_id
        or row.company_id != company_id
    ):
        raise not_found("ADDITIONAL_COST_NOT_FOUND", "额外成本不存在")
    return row


@router.get("/additional-costs", response_model=list[AdditionalCostRead])
def list_additional_costs(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[WorkOrderAdditionalCost]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return addcost.list_additional_costs(db, work_order_id)


@router.post(
    "/additional-costs", response_model=AdditionalCostRead, status_code=status.HTTP_201_CREATED
)
def create_additional_cost(
    work_order_id: str,
    payload: AdditionalCostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderAdditionalCost:
    wo = _ensure_wo(db, work_order_id, current_user.company_id)
    return addcost.create_additional_cost(
        db, wo, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.patch("/additional-costs/{cost_id}", response_model=AdditionalCostRead)
def update_additional_cost(
    work_order_id: str,
    cost_id: str,
    payload: AdditionalCostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> WorkOrderAdditionalCost:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_cost(db, cost_id, work_order_id, current_user.company_id)
    return addcost.update_additional_cost(db, row, payload, current_user.company_id)


@router.delete(
    "/additional-costs/{cost_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_additional_cost(
    work_order_id: str,
    cost_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT)),
) -> None:
    _ensure_wo(db, work_order_id, current_user.company_id)
    row = _ensure_cost(db, cost_id, work_order_id, current_user.company_id)
    addcost.delete_additional_cost(db, row)
```

- [ ] **Step 7: 注册模型**

`app/models/__init__.py`：加入

```python
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
```
并在 `__all__` 加 `"WorkOrderAdditionalCost",`。

- [ ] **Step 8: 跑测试 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_work_order_additional_cost_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 passed；门禁全绿。

- [ ] **Step 9: Commit**

```bash
git add app/models/work_order_additional_cost.py app/schemas/work_order_cost.py \
  app/services/work_order_additional_cost_service.py app/routers/work_order_costs.py \
  app/models/__init__.py tests/test_work_order_additional_cost_api.py
git commit -m "$(cat <<'EOF'
feat(workorder): AdditionalCost CRUD, reuse CostCategory (2A)

工单额外成本明细，cost_category_id 复用现有 CostCategory；硬删，写=work_order.edit。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 总成本聚合（`work_order_cost_service` + `/cost-summary`）

**Files:**
- Create: `app/services/work_order_cost_service.py`
- Modify: `app/schemas/work_order_cost.py`（加 CostSummaryRead）
- Modify: `app/routers/work_order_costs.py`（加 /cost-summary）
- Test: `tests/test_work_order_cost_summary_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_cost_summary_api.py`：

```python
from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def test_empty_summary_all_zero(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert float(body["labor_total"]) == 0.0
    assert float(body["additional_total"]) == 0.0
    assert float(body["parts_total"]) == 0.0
    assert float(body["total"]) == 0.0


def test_summary_aggregates_three_sources(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # labor: 2h * 50 = 100
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 7200, "hourly_rate": "50"},
        headers=_h(t),
    )
    # additional: 33.50
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "差旅", "amount": "33.50"},
        headers=_h(t),
    )
    # parts: 3 * 12.5 = 37.5
    pid = client.post(
        "/api/v1/parts",
        json={"name": "轴承", "cost": "12.5", "quantity": "10"},
        headers=_h(t),
    ).json()["id"]
    client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "3"},
        headers=_h(t),
    )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 100.0
    assert float(body["additional_total"]) == 33.5
    assert float(body["parts_total"]) == 37.5
    assert float(body["total"]) == 171.0  # 100 + 33.5 + 37.5


def test_running_timer_excluded_from_summary(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    client.post(f"/api/v1/work-orders/{wo}/labor/start", json={"hourly_rate": "99"}, headers=_h(t))
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 0.0  # 运行中不入账


def test_summary_subtotals_sum_to_total(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # 造会产生分位舍入的 labor：1 秒 * 36 = 0.01；3 条
    for _ in range(3):
        client.post(
            f"/api/v1/work-orders/{wo}/labor",
            json={"duration_seconds": 1, "hourly_rate": "36"},
            headers=_h(t),
        )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    s = float(body["labor_total"]) + float(body["additional_total"]) + float(body["parts_total"])
    assert abs(s - float(body["total"])) < 1e-9  # 明细之和 == 总计


def test_summary_tenant_isolation(client):
    a = _admin(client)
    wo = _wo_id(client, a)
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(b)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_work_order_cost_summary_api.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 服务 `app/services/work_order_cost_service.py`**

```python
"""工单总成本实时聚合：labor + additional + parts(现有 PartConsumption)。

不落字段；三个小计各自 2dp 量化，total = 已量化小计之和（保证明细之和==总计）。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor
from app.services import work_order_labor_service as labor

_CENT = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_UP)


def cost_summary(db: Session, work_order_id: str) -> dict[str, Decimal]:
    labor_rows = (
        db.execute(select(WorkOrderLabor).where(WorkOrderLabor.work_order_id == work_order_id))
        .scalars()
        .all()
    )
    add_rows = (
        db.execute(
            select(WorkOrderAdditionalCost).where(
                WorkOrderAdditionalCost.work_order_id == work_order_id
            )
        )
        .scalars()
        .all()
    )
    part_rows = (
        db.execute(select(PartConsumption).where(PartConsumption.work_order_id == work_order_id))
        .scalars()
        .all()
    )

    labor_total = sum((labor.compute_cost(r) for r in labor_rows), Decimal("0"))
    additional_total = sum((r.amount for r in add_rows), Decimal("0"))
    parts_total = sum((r.quantity * r.unit_cost for r in part_rows), Decimal("0"))

    lt, at, pt = _q(labor_total), _q(additional_total), _q(parts_total)
    return {
        "labor_total": lt,
        "additional_total": at,
        "parts_total": pt,
        "total": lt + at + pt,
    }
```

> 注：`labor.compute_cost` 已按行 2dp 量化；`labor_total` 为这些已量化行之和（再 `_q` 幂等）。这保证每行展示 cost 与汇总一致。

- [ ] **Step 4: schema 追加 CostSummaryRead**

```python
class CostSummaryRead(BaseModel):
    labor_total: Decimal
    additional_total: Decimal
    parts_total: Decimal
    total: Decimal
```

- [ ] **Step 5: 路由追加 `/cost-summary`（追加到 `work_order_costs.py`）**

import 区补充：

```python
from app.schemas.work_order_cost import CostSummaryRead
from app.services import work_order_cost_service as costsvc
```

端点：

```python
@router.get("/cost-summary", response_model=CostSummaryRead)
def cost_summary(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> dict[str, object]:
    _ensure_wo(db, work_order_id, current_user.company_id)
    return costsvc.cost_summary(db, work_order_id)
```

- [ ] **Step 6: 跑测试 + 门禁 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_work_order_cost_summary_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 passed；门禁全绿。

然后全量回归（确认未碰坏既有）：
Run: `.venv/bin/python -m pytest -q`
Expected: 全 passed。

- [ ] **Step 7: Commit**

```bash
git add app/services/work_order_cost_service.py app/schemas/work_order_cost.py \
  app/routers/work_order_costs.py tests/test_work_order_cost_summary_api.py
git commit -m "$(cat <<'EOF'
feat(workorder): real-time cost summary aggregation (2A)

GET /work-orders/{id}/cost-summary：labor + additional + parts(PartConsumption)；
不落字段，三小计各 2dp 量化、total=已量化小计之和；运行中计时器不入账。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Alembic 迁移（建 3 表，末置）

**Files:**
- Create: `alembic/versions/20260602_0003_workorder_labor_cost.py`
- Test: `tests/unit/test_migration_labor_cost.py`

- [ ] **Step 1: 写迁移 `alembic/versions/20260602_0003_workorder_labor_cost.py`**

down_revision = `"universal_attachment"`（当前 head）。

```python
"""workorder labor cost: tb_time_category + tb_work_order_labor + tb_work_order_additional_cost

Revision ID: workorder_labor_cost
Revises: universal_attachment
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test). 新建工单工时成本三表：
- tb_time_category（工时分类，per-company，默认小时费率）;
- tb_work_order_labor（工时，计时器+手填，费率快照）;
- tb_work_order_additional_cost（额外成本，复用 tb_cost_category）。

全新表、无数据平移。MySQL 全链 alembic 重放受既有 initial_schema 的 TEXT
server_default 问题阻塞（与本迁移无关）；本迁移 DDL 待按实际版本以最小 fixture 手验。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "workorder_labor_cost"
down_revision: str | Sequence[str] | None = "universal_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tb_time_category -----------------------------------------------------
    op.create_table(
        "tb_time_category",
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_time_category_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_time_category")),
        sa.UniqueConstraint("company_id", "name", name="uq_time_category_company_name"),
    )
    op.create_index(
        op.f("ix_tb_time_category_company_id"), "tb_time_category", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_tb_time_category_created_at"), "tb_time_category", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_tb_time_category_is_active"), "tb_time_category", ["is_active"], unique=False
    )

    # --- tb_work_order_labor --------------------------------------------------
    op.create_table(
        "tb_work_order_labor",
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("time_category_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", DATETIME6, nullable=True),
        sa.Column("stopped_at", DATETIME6, nullable=True),
        sa.Column("duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hourly_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["tb_work_order.id"],
            name=op.f("fk_tb_work_order_labor_work_order_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["tb_user.id"],
            name=op.f("fk_tb_work_order_labor_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["time_category_id"],
            ["tb_time_category.id"],
            name=op.f("fk_tb_work_order_labor_time_category_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_work_order_labor_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_labor")),
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_company_id"),
        "tb_work_order_labor",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_created_at"),
        "tb_work_order_labor",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_user_id"),
        "tb_work_order_labor",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_work_order_id"),
        "tb_work_order_labor",
        ["work_order_id"],
        unique=False,
    )

    # --- tb_work_order_additional_cost ----------------------------------------
    op.create_table(
        "tb_work_order_additional_cost",
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("cost_category_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["tb_work_order.id"],
            name=op.f("fk_tb_work_order_additional_cost_work_order_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_category_id"],
            ["tb_cost_category.id"],
            name=op.f("fk_tb_work_order_additional_cost_cost_category_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_work_order_additional_cost_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_additional_cost")),
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_company_id"),
        "tb_work_order_additional_cost",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_created_at"),
        "tb_work_order_additional_cost",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_work_order_id"),
        "tb_work_order_additional_cost",
        ["work_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tb_work_order_additional_cost_work_order_id"),
        table_name="tb_work_order_additional_cost",
    )
    op.drop_index(
        op.f("ix_tb_work_order_additional_cost_created_at"),
        table_name="tb_work_order_additional_cost",
    )
    op.drop_index(
        op.f("ix_tb_work_order_additional_cost_company_id"),
        table_name="tb_work_order_additional_cost",
    )
    op.drop_table("tb_work_order_additional_cost")

    op.drop_index(
        op.f("ix_tb_work_order_labor_work_order_id"), table_name="tb_work_order_labor"
    )
    op.drop_index(op.f("ix_tb_work_order_labor_user_id"), table_name="tb_work_order_labor")
    op.drop_index(op.f("ix_tb_work_order_labor_created_at"), table_name="tb_work_order_labor")
    op.drop_index(op.f("ix_tb_work_order_labor_company_id"), table_name="tb_work_order_labor")
    op.drop_table("tb_work_order_labor")

    op.drop_index(op.f("ix_tb_time_category_is_active"), table_name="tb_time_category")
    op.drop_index(op.f("ix_tb_time_category_created_at"), table_name="tb_time_category")
    op.drop_index(op.f("ix_tb_time_category_company_id"), table_name="tb_time_category")
    op.drop_table("tb_time_category")
```

- [ ] **Step 2: 写迁移测试 `tests/unit/test_migration_labor_cost.py`**

采用仓库现有迁移测试范式（见 `tests/unit/test_partner_migration.py`）：`importlib.import_module` 取迁移模块 + `Operations.context(ctx)` 在临时 SQLite 上跑 up/down，建最小父表满足 FK 引用。

```python
"""迁移 workorder_labor_cost 的链路与 up/down 可重放性（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0003_workorder_labor_cost")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "workorder_labor_cost"
    assert m.down_revision == "universal_attachment"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        # 最小父表（仅需 id 主键供 FK 引用；SQLite 不强校验 FK）
        for ddl in (
            "CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_user (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE tb_cost_category (id VARCHAR(36) PRIMARY KEY)",
        ):
            conn.exec_driver_sql(ddl)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            tables = set(inspect(conn).get_table_names())
            assert {
                "tb_time_category",
                "tb_work_order_labor",
                "tb_work_order_additional_cost",
            } <= tables
            _mod().downgrade()
            remaining = set(inspect(conn).get_table_names())
            assert "tb_time_category" not in remaining
            assert "tb_work_order_labor" not in remaining
            assert "tb_work_order_additional_cost" not in remaining
    eng.dispose()
```

- [ ] **Step 3: alembic 原生 up/down/up + autogenerate 零漂移**

Run（SQLite 本地库做可重放验证）：
```bash
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade -1
.venv/bin/alembic upgrade head
```
Expected: 三步均无报错；`workorder_labor_cost` 为最终 head。

零漂移检查：
```bash
.venv/bin/alembic check
```
Expected: "No new upgrade operations detected."（模型与迁移一致，无未捕获变更）。

> 若 `alembic check` 因既有 initial_schema 历史问题报与本表无关的漂移，需逐项确认漂移项**不涉及** `tb_time_category`/`tb_work_order_labor`/`tb_work_order_additional_cost`；本三表必须零漂移。

- [ ] **Step 4: 跑迁移测试 + 全量回归 + 门禁**

Run: `.venv/bin/python -m pytest tests/unit/test_migration_labor_cost.py -q && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 passed；门禁全绿。

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/20260602_0003_workorder_labor_cost.py tests/unit/test_migration_labor_cost.py
git commit -m "$(cat <<'EOF'
feat(workorder): alembic migration for labor cost tables (2A)

建 tb_time_category / tb_work_order_labor / tb_work_order_additional_cost；
up/down/up 可重放 + autogenerate 三表零漂移；MySQL DDL 待最小 fixture 手验。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 完成后

- 子轮完成报告（含迁移风险点验证结果）。
- 更新记忆：`atlas-parity-backfill` 标记第 2 组 2A 进展；`smart-cmms-progress`。
- merge/push 由人工决定（惯例：`--no-ff` 合入 main、本地暂不 push）。

## Self-Review 记录

- **Spec 覆盖**：§3.1 TimeCategory→T1；§3.2 Labor→T2/T3；§3.3 AdditionalCost→T4；§4 聚合→T5；
  §5 端点全覆盖（labor CRUD/start/stop→T3，additional→T4，cost-summary→T5，time-categories→T1）；
  §6 权限→T1（time_category.*）+ 各路由复用 work_order.edit/view；§9 测试逐项落到各 Task；§10 迁移→T6。
- **占位扫描**：T2 Step1 顶部出现过 `HTTPExceptionShim` 占位，已在同 Step 用「完整文件」版本取代（实际 `from fastapi import HTTPException`）。无其他占位。
- **类型一致**：服务函数名 `create_labor`/`start_timer`/`stop_timer`/`update_labor`/`delete_labor`/
  `list_labor`/`compute_cost`/`is_running` 在 T2 定义、T3/T5 调用一致；`cost_summary` 返回 4 键与
  `CostSummaryRead` 字段一致；模型类名 `WorkOrderLabor`/`WorkOrderAdditionalCost`/`TimeCategory` 全程一致。
