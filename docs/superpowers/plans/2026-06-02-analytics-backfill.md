# 分析补全 ⑤ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一轮补齐 8 项后端只读分析（labor/additional 成本、工单多维分布、库存 ABC、资产维护成本、请求/人员/趋势新端点）+ 2 处工单 schema 前置，使分析模块功能完整。

**Architecture:** 沿用现有 `app/services/analytics/` 纯函数聚合 + `app/routers/analytics.py` 端点 + Pydantic 响应模型。新增工单分类表与两列经独立迁移（末位任务）落库；pytest 用 SQLite `create_all` 故模型即测，迁移单独单测。成本归属抽公共纯函数供 ①④ 复用。全部金额 Decimal、时长 Python timedelta，跨方言安全；金额量化沿用 2A（小计 2dp 后求和）。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（Mapped/mapped_column）+ Pydantic v2 + Alembic + pytest（SQLite in-memory）。解释器统一 `backend/.venv/bin/python`；门禁 `ruff check app/` + `mypy app/`。

**全局约定（每个任务都适用）：**
- 工作目录 `backend/`；所有命令前缀 `.venv/bin/`。
- 每任务：写失败测试 → 跑红 → 最小实现 → 跑绿 → `ruff check app/` + `mypy app/` 绿 → commit。
- commit message 结尾附：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- 净室原创，仅中文注释/文案。
- 多租户：新表挂 `TenantMixin`；分析查询对象均为 TenantScoped 子类，ORM 事件自动按 company 隔离。

---

## File Structure

| 文件 | 责任 | 任务 |
|---|---|---|
| `app/models/work_order_category.py` | 新建：WorkOrderCategory 模型 | T1 |
| `app/schemas/work_order_category.py` | 新建：分类 CRUD schema | T1 |
| `app/services/work_order_category_service.py` | 新建：分类 CRUD 服务（软删） | T1 |
| `app/routers/work_order_categories.py` | 新建：`/api/v1/work-order-categories` | T1 |
| `app/permissions.py` | 加 `work_order_category.view/manage` | T1 |
| `app/models/__init__.py` | 注册 WorkOrderCategory | T1 |
| `app/main.py` | 挂 work_order_categories.router | T1 |
| `app/models/work_order.py` | 加 `category_id` / `created_by_user_id` 两列 | T2 |
| `app/schemas/work_order.py` | Create/Update/Read 暴露两字段 | T2 |
| `app/services/work_order_service.py` | create 落 created_by；category 跨租户校验；to_read | T2 |
| `app/routers/work_orders.py` | 无需改（经 svc） | T2 |
| `app/services/analytics/_cost_attribution.py` | 新建：按资产维护成本归属公共纯函数 | T3 |
| `app/services/analytics/cost_analytics.py` | 加 labor/additional/total + by_asset | T3 |
| `app/services/analytics/work_order_analytics.py` | 加 by_asset/user/category | T4 |
| `app/services/analytics/inventory_analytics.py` | 加 ABC | T5 |
| `app/services/analytics/asset_reliability_analytics.py` | 加维护成本 + 价值比 | T6 |
| `app/services/analytics/request_analytics.py` | 新建：请求聚合 | T7 |
| `app/services/analytics/personnel_analytics.py` | 新建：人员聚合 | T8 |
| `app/services/analytics/trend_analytics.py` | 新建：分桶时间序列 | T9 |
| `app/schemas/analytics.py` | 扩展 + 新响应模型 | T3–T9 |
| `app/routers/analytics.py` | 新端点 + CSV 导出补 | T3–T9 |
| `app/services/analytics/__init__.py` | 导出新模块 | T3,T7,T8,T9 |
| `alembic/versions/20260602_0004_analytics_backfill.py` | 新建：统一迁移 | T10 |
| `tests/test_work_order_category_api.py` 等 | 各任务测试 | 各 |
| `tests/unit/test_migration_analytics_backfill.py` | 迁移单测 | T10 |

---

## Task 1: WorkOrderCategory（表 + CRUD + 权限）

**Files:**
- Create: `app/models/work_order_category.py`
- Create: `app/schemas/work_order_category.py`
- Create: `app/services/work_order_category_service.py`
- Create: `app/routers/work_order_categories.py`
- Modify: `app/permissions.py`
- Modify: `app/models/__init__.py`
- Modify: `app/main.py`
- Test: `tests/test_work_order_category_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_category_api.py`：
```python
"""工单分类 CRUD：鉴权/RBAC/软删/重名/跨租户。镜像 time-categories。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _create(client, token, name="保养"):
    return client.post(
        "/api/v1/work-order-categories", headers=_h(token), json={"name": name}
    )


def test_requires_auth(client):
    assert client.get("/api/v1/work-order-categories").status_code == 401


def test_crud_roundtrip(client):
    t = _admin(client)
    r = _create(client, t, "保养")
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["name"] == "保养"
    assert client.get("/api/v1/work-order-categories", headers=_h(t)).json()[0]["id"] == cid
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 200
    assert (
        client.patch(
            f"/api/v1/work-order-categories/{cid}", headers=_h(t), json={"name": "校准"}
        ).json()["name"]
        == "校准"
    )
    assert (
        client.delete(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 204
    )
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 404


def test_duplicate_name_conflict(client):
    t = _admin(client)
    _create(client, t, "保养")
    assert _create(client, t, "保养").status_code == 409


def test_cross_tenant_isolation(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    cid = _create(client, ta, "A的分类").json()["id"]
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(tb)).status_code == 404
    assert client.get("/api/v1/work-order-categories", headers=_h(tb)).json() == []
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_work_order_category_api.py -q`
Expected: FAIL（404/路由不存在）。

- [ ] **Step 3: 模型**

`app/models/work_order_category.py`：
```python
"""工单分类（每租户）。镜像 TimeCategory。"""

from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class WorkOrderCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_work_order_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 4: schema**

`app/schemas/work_order_category.py`：
```python
"""工单分类 CRUD schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkOrderCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class WorkOrderCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class WorkOrderCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
```

- [ ] **Step 5: 服务**

`app/services/work_order_category_service.py`：
```python
"""工单分类服务：CRUD（软删）。镜像 time_category_service。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict
from app.models.base import utcnow
from app.models.work_order_category import WorkOrderCategory
from app.schemas.work_order_category import (
    WorkOrderCategoryCreate,
    WorkOrderCategoryUpdate,
)


def create_category(
    db: Session, payload: WorkOrderCategoryCreate, company_id: str
) -> WorkOrderCategory:
    dup = db.execute(
        select(WorkOrderCategory).where(
            WorkOrderCategory.is_active.is_(True), WorkOrderCategory.name == payload.name
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise conflict("WORK_ORDER_CATEGORY_DUPLICATE", "工单分类名称已存在")
    cat = WorkOrderCategory(
        name=payload.name, description=payload.description, company_id=company_id
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[WorkOrderCategory]:
    return list(
        db.execute(
            select(WorkOrderCategory)
            .where(WorkOrderCategory.is_active.is_(True))
            .order_by(WorkOrderCategory.name, WorkOrderCategory.id)
        )
        .scalars()
        .all()
    )


def get_category(db: Session, category_id: str) -> WorkOrderCategory | None:
    c = db.get(WorkOrderCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_category(
    db: Session, cat: WorkOrderCategory, payload: WorkOrderCategoryUpdate
) -> WorkOrderCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: WorkOrderCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
```

> 注：重名查询依赖 ORM 自动租户 scope（仅查当前 company 的 is_active 行）。

- [ ] **Step 6: 路由**

`app/routers/work_order_categories.py`：
```python
"""工单分类 API（/api/v1/work-order-categories）。镜像 time-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order_category import WorkOrderCategory
from app.schemas.work_order_category import (
    WorkOrderCategoryCreate,
    WorkOrderCategoryRead,
    WorkOrderCategoryUpdate,
)
from app.services import work_order_category_service as svc

router = APIRouter(prefix="/api/v1/work-order-categories", tags=["work-order-categories"])


def _ensure(c: WorkOrderCategory | None, company_id: str) -> WorkOrderCategory:
    if c is None or c.company_id != company_id:
        raise not_found("WORK_ORDER_CATEGORY_NOT_FOUND", "工单分类不存在")
    return c


@router.get("", response_model=list[WorkOrderCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_VIEW)),
) -> list[WorkOrderCategory]:
    return svc.list_categories(db)


@router.post("", response_model=WorkOrderCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: WorkOrderCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> WorkOrderCategory:
    return svc.create_category(db, payload, current_user.company_id)


@router.get("/{category_id}", response_model=WorkOrderCategoryRead)
def get_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_VIEW)),
) -> WorkOrderCategory:
    return _ensure(svc.get_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=WorkOrderCategoryRead)
def update_category(
    category_id: str,
    payload: WorkOrderCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> WorkOrderCategory:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    return svc.update_category(db, c, payload)


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> None:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    svc.delete_category(db, c)
```

- [ ] **Step 7: 权限**

`app/permissions.py`：在 `TIME_CATEGORY_*` 定义后加：
```python
# --- 工单分类（分析补全）---
WORK_ORDER_CATEGORY_VIEW = "work_order_category.view"
WORK_ORDER_CATEGORY_MANAGE = "work_order_category.manage"
```
在分组区 `_TIME_CATEGORY = ...` 后加：
```python
_WORK_ORDER_CATEGORY = [WORK_ORDER_CATEGORY_VIEW, WORK_ORDER_CATEGORY_MANAGE]
```
`ALL_PERMISSIONS` 元组里 `+ _TIME_CATEGORY` 后加 `+ _WORK_ORDER_CATEGORY`。technician 角色权限列表（含 `TIME_CATEGORY_VIEW` 那段）加 `WORK_ORDER_CATEGORY_VIEW,`。

- [ ] **Step 8: 注册 + 挂载**

`app/models/__init__.py`：import 加 `from app.models.work_order_category import WorkOrderCategory`，`__all__` 加 `"WorkOrderCategory",`。
`app/main.py`：import work_order_categories router 并 `app.include_router(work_order_categories.router)`（与 time_categories 同处）。

- [ ] **Step 9: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_work_order_category_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 PASS / All checks passed。

- [ ] **Step 10: commit**

```bash
git add -A && git commit -m "feat(analytics): WorkOrderCategory CRUD + permissions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 工单加列（category_id + created_by_user_id）

**Files:**
- Modify: `app/models/work_order.py`
- Modify: `app/schemas/work_order.py`
- Modify: `app/services/work_order_service.py`
- Test: `tests/test_work_order_category_fields.py`

- [ ] **Step 1: 写失败测试**

`tests/test_work_order_category_fields.py`：
```python
"""工单 category_id / created_by_user_id 接线 + 跨租户分类校验。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _me_id(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()["id"]


def _category(client, token, name="保养"):
    return client.post(
        "/api/v1/work-order-categories", headers=_h(token), json={"name": name}
    ).json()["id"]


def test_create_stamps_created_by_and_category(client):
    t = _admin(client)
    me = _me_id(client, t)
    cid = _category(client, t)
    r = client.post(
        "/api/v1/work-orders", headers=_h(t), json={"title": "维修", "category_id": cid}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category_id"] == cid
    assert body["created_by_user_id"] == me


def test_patch_category(client):
    t = _admin(client)
    cid = _category(client, t)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "x"}).json()["id"]
    r = client.patch(
        f"/api/v1/work-orders/{wid}", headers=_h(t), json={"category_id": cid}
    )
    assert r.json()["category_id"] == cid


def test_cross_tenant_category_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    cid_a = _category(client, ta, "A分类")
    r = client.post(
        "/api/v1/work-orders", headers=_h(tb), json={"title": "x", "category_id": cid_a}
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "WORK_ORDER_CATEGORY_NOT_FOUND"
```

> 先核对 `/api/v1/auth/me` 返回含 `id`（如字段名不同，按实际调整 `_me_id`）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_work_order_category_fields.py -q`
Expected: FAIL（响应无 category_id / created_by_user_id）。

- [ ] **Step 3: 模型加列**

`app/models/work_order.py` 在 `WorkOrder` 类 `request_id` 列后加（import 处确保有 `ForeignKey`、`String`）：
```python
    category_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tb_work_order_category.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
```

- [ ] **Step 4: schema 暴露**

`app/schemas/work_order.py`：
- `WorkOrderCreate` 加 `category_id: str | None = None`
- `WorkOrderUpdate` 加 `category_id: str | None = None`
- `WorkOrderRead` 加 `category_id: str | None = None` 与 `created_by_user_id: str | None = None`

- [ ] **Step 5: 服务接线 + 校验**

`app/services/work_order_service.py`：
顶部 import 加：
```python
from app.errors import bad_request, not_found
from app.models.work_order_category import WorkOrderCategory
```
（若已 import `bad_request`，合并为 `from app.errors import bad_request, not_found`。）

加校验助手：
```python
def _validate_category(db: Session, category_id: str | None, company_id: str) -> None:
    if category_id is None:
        return
    cat = db.get(WorkOrderCategory, category_id)
    if cat is None or not cat.is_active or cat.company_id != company_id:
        raise not_found("WORK_ORDER_CATEGORY_NOT_FOUND", "工单分类不存在")
```

`create_work_order`：在构造 `WorkOrder(...)` 前调用 `_validate_category(db, payload.category_id, company_id)`；构造里加 `category_id=payload.category_id, created_by_user_id=actor_user_id,`。

`update_work_order`：改签名为 `update_work_order(db, wo, payload, company_id)`（路由调用方在 `app/routers/work_orders.py:103` 补 `current_user.company_id`）；函数体开头：
```python
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _validate_category(db, data["category_id"], company_id)
    for k, v in data.items():
        setattr(wo, k, v)
```

`to_read` dict 加：
```python
        "category_id": wo.category_id,
        "created_by_user_id": wo.created_by_user_id,
```

- [ ] **Step 6: 路由调用方对齐**

`app/routers/work_orders.py` 的 patch 端点：`wo = svc.update_work_order(db, wo, payload, current_user.company_id)`。

- [ ] **Step 7: 跑绿 + 门禁 + 回归**

Run: `.venv/bin/python -m pytest tests/test_work_order_category_fields.py tests/test_work_order_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 PASS（确认未破坏既有工单测试）。

- [ ] **Step 8: commit**

```bash
git add -A && git commit -m "feat(analytics): work order category_id + created_by_user_id wiring

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 成本归属公共纯函数 + ① /costs 扩展

**Files:**
- Create: `app/services/analytics/_cost_attribution.py`
- Modify: `app/services/analytics/cost_analytics.py`
- Modify: `app/schemas/analytics.py`
- Modify: `app/services/analytics/__init__.py`（若 _cost_attribution 需导出，可不导出，内部 import）
- Test: `tests/test_analytics_cost_labor.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_cost_labor.py`：
```python
"""/costs 扩展：labor + additional + total_maintenance_cost + by_asset。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_costs_includes_labor_and_additional(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                   asset_id="asset-1")
    db.add(wo)
    db.flush()
    # 1 小时 @ 60 = 60.00 labor；additional 40.00
    db.add(WorkOrderLabor(work_order_id=wo.id, duration_seconds=3600,
                          hourly_rate=Decimal("60"), company_id=co))
    db.add(WorkOrderAdditionalCost(work_order_id=wo.id, title="耗材",
                                   amount=Decimal("40"), company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/costs", headers=_h(t)).json()
    assert body["labor_cost"] == "60.00"
    assert body["additional_cost"] == "40.00"
    assert body["total_maintenance_cost"] == "100.00"
    by_asset = {r["asset_id"]: r for r in body["maintenance_cost_by_asset"]}
    assert by_asset["asset-1"]["labor_cost"] == "60.00"
    assert by_asset["asset-1"]["total"] == "100.00"


def test_running_timer_costs_zero(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co)
    db.add(wo)
    db.flush()
    db.add(WorkOrderLabor(work_order_id=wo.id, duration_seconds=0,
                          hourly_rate=Decimal("60"), started_at=datetime.utcnow(),
                          company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/costs", headers=_h(t)).json()
    assert body["labor_cost"] == "0.00"
```

> Decimal 经 Pydantic 序列化为字符串（沿用 2A 约定）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_cost_labor.py -q`
Expected: FAIL（响应无 labor_cost 等键）。

- [ ] **Step 3: 公共纯函数**

`app/services/analytics/_cost_attribution.py`：
```python
"""按资产维护成本归属（parts + labor + additional）。

公共纯函数，供 cost_analytics 与 asset_reliability_analytics 复用。
金额一律 Decimal；labor/additional 按 created_at 落窗，parts 按 consumed_at 落窗。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor
from app.services import work_order_labor_service as labor


def cost_by_asset(
    db: Session,
    start: datetime,
    end_excl: datetime,
    *,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> dict[str | None, dict[str, Decimal]]:
    """返回 {asset_id|None: {"parts","labor","additional"}}（未量化原值）。

    asset_id/location_id 过滤经 WorkOrder 关联生效。
    """
    out: dict[str | None, dict[str, Decimal]] = defaultdict(
        lambda: {"parts": Decimal("0"), "labor": Decimal("0"), "additional": Decimal("0")}
    )

    def _wo_filter(stmt):  # type: ignore[no-untyped-def]
        if asset_id is not None:
            stmt = stmt.where(WorkOrder.asset_id == asset_id)
        if location_id is not None:
            stmt = stmt.where(WorkOrder.location_id == location_id)
        return stmt

    parts_stmt = _wo_filter(
        select(PartConsumption.quantity, PartConsumption.unit_cost, WorkOrder.asset_id)
        .join(WorkOrder, PartConsumption.work_order_id == WorkOrder.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    for qty, unit_cost, a_id in db.execute(parts_stmt).all():
        out[a_id]["parts"] += qty * unit_cost

    labor_stmt = _wo_filter(
        select(WorkOrderLabor, WorkOrder.asset_id)
        .join(WorkOrder, WorkOrderLabor.work_order_id == WorkOrder.id)
        .where(WorkOrderLabor.created_at >= start, WorkOrderLabor.created_at < end_excl)
    )
    for row, a_id in db.execute(labor_stmt).all():
        out[a_id]["labor"] += labor.compute_cost(row)

    add_stmt = _wo_filter(
        select(WorkOrderAdditionalCost.amount, WorkOrder.asset_id)
        .join(WorkOrder, WorkOrderAdditionalCost.work_order_id == WorkOrder.id)
        .where(
            WorkOrderAdditionalCost.created_at >= start,
            WorkOrderAdditionalCost.created_at < end_excl,
        )
    )
    for amount, a_id in db.execute(add_stmt).all():
        out[a_id]["additional"] += amount

    return dict(out)
```

- [ ] **Step 4: cost_analytics 扩展**

`app/services/analytics/cost_analytics.py`：
- import 顶部加：
```python
from decimal import ROUND_HALF_UP
from app.services.analytics import _cost_attribution
```
- 加量化助手（文件内）：
```python
_CENT = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_UP)
```
- 在 `return {...}` 前计算：
```python
    attrib = _cost_attribution.cost_by_asset(
        db, start, end_excl, asset_id=asset_id, location_id=location_id
    )
    labor_total = sum((v["labor"] for v in attrib.values()), Decimal("0"))
    additional_total = sum((v["additional"] for v in attrib.values()), Decimal("0"))
    maintenance_cost_by_asset = sorted(
        (
            {
                "asset_id": a_id,
                "parts_cost": _q(v["parts"]),
                "labor_cost": _q(v["labor"]),
                "additional_cost": _q(v["additional"]),
                "total": _q(v["parts"]) + _q(v["labor"]) + _q(v["additional"]),
            }
            for a_id, v in attrib.items()
        ),
        key=lambda r: cast(Decimal, r["total"]),
        reverse=True,
    )
    lt, at, pt = _q(labor_total), _q(additional_total), _q(total_consumption)
```
- `return` dict 追加键：
```python
        "labor_cost": lt,
        "additional_cost": at,
        "total_maintenance_cost": lt + at + pt,
        "maintenance_cost_by_asset": maintenance_cost_by_asset,
```
> `total_consumption` 即现有 parts 总额（已计算）。现有键保留不动。

- [ ] **Step 5: schema 扩展**

`app/schemas/analytics.py`：加：
```python
class MaintenanceCostByAssetRow(BaseModel):
    asset_id: str | None
    parts_cost: Decimal
    labor_cost: Decimal
    additional_cost: Decimal
    total: Decimal
```
`CostAnalytics` 加字段：
```python
    labor_cost: Decimal
    additional_cost: Decimal
    total_maintenance_cost: Decimal
    maintenance_cost_by_asset: list[MaintenanceCostByAssetRow]
```

- [ ] **Step 6: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_cost_labor.py tests/test_analytics_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 PASS。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(analytics): labor/additional cost in /costs + cost-by-asset

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: ② /work-orders 多维分布

**Files:**
- Modify: `app/services/analytics/work_order_analytics.py`
- Modify: `app/schemas/analytics.py`
- Test: `tests/test_analytics_wo_distribution.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_wo_distribution.py`：
```python
"""/work-orders 扩展：by_asset / by_user / by_category。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_distributions(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                     asset_id="A1", primary_user_id="U1", category_id="C1"))
    db.add(WorkOrder(custom_id="WO2", title="t", created_at=datetime.utcnow(), company_id=co,
                     asset_id="A1", primary_user_id=None, category_id=None))
    db.commit()
    body = client.get("/api/v1/analytics/work-orders", headers=_h(t)).json()
    by_asset = {r["asset_id"]: r["count"] for r in body["by_asset"]}
    assert by_asset["A1"] == 2
    by_user = {r["user_id"]: r["count"] for r in body["by_user"]}
    assert by_user["U1"] == 1 and by_user[None] == 1
    by_cat = {r["category_id"]: r["count"] for r in body["by_category"]}
    assert by_cat["C1"] == 1 and by_cat[None] == 1
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_wo_distribution.py -q`
Expected: FAIL（无 by_asset 等键）。

- [ ] **Step 3: 实现**

`app/services/analytics/work_order_analytics.py`：在构造 `return {...}` 前，对已取出的 `wos` 聚合：
```python
    from collections import defaultdict

    def _count_by(key):  # type: ignore[no-untyped-def]
        acc: dict[object, int] = defaultdict(int)
        for wo in wos:
            acc[key(wo)] += 1
        return acc

    by_asset_acc = _count_by(lambda w: w.asset_id)
    by_user_acc = _count_by(lambda w: w.primary_user_id)
    by_category_acc = _count_by(lambda w: w.category_id)
    by_asset = sorted(
        ({"asset_id": k, "count": v} for k, v in by_asset_acc.items()),
        key=lambda r: r["count"], reverse=True,
    )
    by_user = sorted(
        ({"user_id": k, "count": v} for k, v in by_user_acc.items()),
        key=lambda r: r["count"], reverse=True,
    )
    by_category = sorted(
        ({"category_id": k, "count": v} for k, v in by_category_acc.items()),
        key=lambda r: r["count"], reverse=True,
    )
```
`return` dict 追加 `"by_asset": by_asset, "by_user": by_user, "by_category": by_category,`。

> `from collections import defaultdict` 提到文件顶部 import 区（不要在函数内重复 import；此处为示意，实现时放模块顶部）。

- [ ] **Step 4: schema**

`app/schemas/analytics.py`：
```python
class CountRow(BaseModel):
    asset_id: str | None = None
    user_id: str | None = None
    category_id: str | None = None
    count: int
```
`WorkOrderAnalytics` 加：
```python
    by_asset: list[CountRow]
    by_user: list[CountRow]
    by_category: list[CountRow]
```
> 用单一 `CountRow`（三字段可空）以 DRY；各 list 只填对应键。或拆三个专用 Row（实现者择一，保持一致）。

- [ ] **Step 5: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_wo_distribution.py tests/test_analytics_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(analytics): work-order by_asset/by_user/by_category distributions

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: ③ /inventory ABC 分类

**Files:**
- Modify: `app/services/analytics/inventory_analytics.py`
- Modify: `app/schemas/analytics.py`
- Test: `tests/test_analytics_inventory_abc.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_inventory_abc.py`：
```python
"""/inventory 扩展：ABC 分级（按窗内消耗价值）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def _part(db, co, name, custom_id):
    p = Part(custom_id=custom_id, name=name, quantity=Decimal("0"), min_quantity=Decimal("0"),
             cost=Decimal("1"), company_id=co)
    db.add(p)
    db.flush()
    return p


def test_abc_classification(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co)
    db.add(wo)
    db.flush()
    big = _part(db, co, "大头", "P-1")
    small = _part(db, co, "小头", "P-2")
    # 消耗价值 big=90, small=10 → big 累计 90% 属 B 边界外? 90<=95→ big=A(<=80?)
    db.add(PartConsumption(work_order_id=wo.id, part_id=big.id, quantity=Decimal("90"),
                           unit_cost=Decimal("1"), consumed_at=datetime.utcnow(), company_id=co))
    db.add(PartConsumption(work_order_id=wo.id, part_id=small.id, quantity=Decimal("10"),
                           unit_cost=Decimal("1"), consumed_at=datetime.utcnow(), company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/inventory", headers=_h(t)).json()
    rows = {r["part_id"]: r for r in body["abc_classification"]}
    assert rows[big.id]["consumption_value"] == "90.00"
    assert rows[big.id]["cumulative_pct"] == 90.0
    assert rows[big.id]["abc_class"] == "B"   # 累计 90% ∈ (80,95] → B
    assert rows[small.id]["abc_class"] == "C"  # 累计 100% > 95 → C
    assert body["abc_summary"]["B"] == 1 and body["abc_summary"]["C"] == 1


def test_abc_empty_when_no_consumption(client, db):
    t = _admin(client)
    body = client.get("/api/v1/analytics/inventory", headers=_h(t)).json()
    assert body["abc_classification"] == []
    assert body["abc_summary"] == {"A": 0, "B": 0, "C": 0}
```

> 先核对 Part 必填字段（`quantity`/`min_quantity`/`cost`/`non_stock` 等），按 `app/models/part.py` 调整构造参数。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_inventory_abc.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`app/services/analytics/inventory_analytics.py`：在 `top_consumed` 计算后、`return` 前加（复用已取的 `consumed` 累加器需带 cost；故对消耗行同时累计价值）。新增按价值累计：
```python
    # ABC：按窗内消耗价值降序累计分级
    value_acc: dict[str, dict[str, Any]] = {}
    for part_id, custom_id, name, qty, unit_cost in db.execute(abc_stmt).all():
        slot = value_acc.setdefault(
            part_id,
            {"part_id": part_id, "custom_id": custom_id, "name": name, "value": Decimal("0")},
        )
        slot["value"] += qty * unit_cost
    ranked = sorted(value_acc.values(), key=lambda r: cast(Decimal, r["value"]), reverse=True)
    total_value = sum((cast(Decimal, r["value"]) for r in ranked), Decimal("0"))
    abc_classification: list[dict[str, Any]] = []
    abc_summary = {"A": 0, "B": 0, "C": 0}
    running = Decimal("0")
    for r in ranked:
        running += cast(Decimal, r["value"])
        cum_pct = float(running / total_value * 100) if total_value > 0 else 0.0
        cls = "A" if cum_pct <= 80 else "B" if cum_pct <= 95 else "C"
        abc_summary[cls] += 1
        abc_classification.append(
            {
                "part_id": r["part_id"],
                "custom_id": r["custom_id"],
                "name": r["name"],
                "consumption_value": cast(Decimal, r["value"]).quantize(Decimal("0.01")),
                "cumulative_pct": round(cum_pct, 2),
                "abc_class": cls,
            }
        )
```
新增查询 `abc_stmt`（带 unit_cost，复用窗口/分类过滤；可直接扩展现有 `c_stmt` 增列 `PartConsumption.unit_cost`，避免二次查询——实现者可合并）：
```python
    abc_stmt = (
        select(PartConsumption.part_id, Part.custom_id, Part.name,
               PartConsumption.quantity, PartConsumption.unit_cost)
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if category_id is not None:
        abc_stmt = abc_stmt.where(Part.category_id == category_id)
```
`return` dict 追加 `"abc_classification": abc_classification, "abc_summary": abc_summary,`。

> DRY 提示：现有 `c_stmt`（top_consumed 用）与 `abc_stmt` 仅差 `unit_cost` 一列，实现者应合并为一次查询、同时喂 `consumed`（按量）与 `value_acc`（按价值）两个累加器。

- [ ] **Step 4: schema**

`app/schemas/analytics.py`：
```python
class ABCRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    consumption_value: Decimal
    cumulative_pct: float
    abc_class: str
```
`InventoryAnalytics` 加：
```python
    abc_classification: list[ABCRow]
    abc_summary: dict[str, int]
```

- [ ] **Step 5: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_inventory_abc.py tests/test_analytics_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(analytics): inventory ABC/Pareto classification

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: ④ /asset-reliability 维护成本 + 价值比

**Files:**
- Modify: `app/services/analytics/asset_reliability_analytics.py`
- Modify: `app/schemas/analytics.py`
- Test: `tests/test_analytics_asset_cost.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_asset_cost.py`：
```python
"""/asset-reliability 扩展：total_maintenance_cost + cost_to_value_ratio。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.maintenance_asset import Asset
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_asset_maintenance_cost_and_ratio(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    a = Asset(custom_id="AS-1", name="泵", acquisition_cost=Decimal("1000"), company_id=co)
    db.add(a)
    db.flush()
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                   asset_id=a.id)
    db.add(wo)
    db.flush()
    db.add(WorkOrderAdditionalCost(work_order_id=wo.id, title="耗材",
                                   amount=Decimal("250"), company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/asset-reliability", headers=_h(t)).json()
    row = next(r for r in body["assets"] if r["asset_id"] == a.id)
    assert row["total_maintenance_cost"] == "250.00"
    assert row["acquisition_cost"] == "1000.00"
    assert row["cost_to_value_ratio"] == 0.25
    assert body["fleet_total_maintenance_cost"] == "250.00"
```

> 核对 Asset 必填字段（按 `app/models/maintenance_asset.py`，可能需 `location_id`/`category_id` 可空）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_asset_cost.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现**

`app/services/analytics/asset_reliability_analytics.py`：
- import 加：
```python
from decimal import ROUND_HALF_UP, Decimal
from app.services.analytics import _cost_attribution
```
- 在循环前取归属：
```python
    attrib = _cost_attribution.cost_by_asset(db, start, end_excl)
    _CENT = Decimal("0.01")

    def _asset_total(a_id: str) -> Decimal:
        v = attrib.get(a_id)
        if v is None:
            return Decimal("0.00")
        return (
            v["parts"].quantize(_CENT, rounding=ROUND_HALF_UP)
            + v["labor"].quantize(_CENT, rounding=ROUND_HALF_UP)
            + v["additional"].quantize(_CENT, rounding=ROUND_HALF_UP)
        )
```
- 在每个 `asset_rows.append({...})` 里加：
```python
                "total_maintenance_cost": _asset_total(a.id),
                "acquisition_cost": (
                    a.acquisition_cost.quantize(_CENT) if a.acquisition_cost is not None else None
                ),
                "cost_to_value_ratio": (
                    round(float(_asset_total(a.id) / a.acquisition_cost), 4)
                    if a.acquisition_cost is not None and a.acquisition_cost > 0
                    else None
                ),
```
> `acquisition_cost` 为 `Numeric` → Python Decimal。`_asset_total(a.id)` 调用两次可提到局部变量 `tmc = _asset_total(a.id)` 复用（实现者优化）。
- 车队级在 `return` 前：
```python
    fleet_total_maintenance_cost = sum(
        (cast(Decimal, r["total_maintenance_cost"]) for r in asset_rows), Decimal("0")
    )
```
`return` dict 加 `"fleet_total_maintenance_cost": fleet_total_maintenance_cost,`。

- [ ] **Step 4: schema**

`AssetReliabilityRow` 加：
```python
    total_maintenance_cost: Decimal
    acquisition_cost: Decimal | None
    cost_to_value_ratio: float | None
```
`AssetReliabilityAnalytics` 加：
```python
    fleet_total_maintenance_cost: Decimal
```

- [ ] **Step 5: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_asset_cost.py tests/test_analytics_api.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 6: commit**

```bash
git add -A && git commit -m "feat(analytics): asset maintenance cost + cost-to-value ratio

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: ⑤ /requests 请求分析端点

**Files:**
- Create: `app/services/analytics/request_analytics.py`
- Modify: `app/services/analytics/__init__.py`
- Modify: `app/schemas/analytics.py`
- Modify: `app/routers/analytics.py`
- Test: `tests/test_analytics_requests.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_requests.py`：
```python
"""/analytics/requests：总览 + 周期 + 收到vs解决 + 转化。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.company import Company
from app.models.request import Request
from app.models.request_status import RequestStatus


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_request_analytics_shape(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    now = datetime.utcnow()
    db.add(Request(custom_id="RQ1", title="r1", status=RequestStatus.APPROVED,
                   created_at=now - timedelta(hours=2), resolved_at=now,
                   work_order_id="WO-x", company_id=co))
    db.add(Request(custom_id="RQ2", title="r2", status=RequestStatus.PENDING,
                   created_at=now, company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/requests", headers=_h(t)).json()
    assert body["total"] == 2
    assert body["by_status"]["APPROVED"] == 1 and body["by_status"]["PENDING"] == 1
    assert body["received"] == 2
    assert body["resolved"] == 1
    assert body["converted"] == 1
    assert body["avg_resolution_cycle_hours"] == 2.0


def test_requires_auth(client):
    assert client.get("/api/v1/analytics/requests").status_code == 401
```

> 核对 Request 构造必填（custom_id/title/status/priority 默认）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_requests.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 服务**

`app/services/analytics/request_analytics.py`：
```python
"""请求分析（只读）：总览/优先级/周期/收到vs解决/转化。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.request import Request
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority
from app.services.analytics._common import hours_between, resolve_window


def request_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    stmt = select(Request).where(
        Request.created_at >= start, Request.created_at < end_excl
    )
    if asset_id is not None:
        stmt = stmt.where(Request.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(Request.location_id == location_id)
    reqs = list(db.execute(stmt).scalars().all())

    by_status = {s.value: 0 for s in RequestStatus}
    by_priority = {p.value: 0 for p in WorkOrderPriority}
    converted = 0
    for r in reqs:
        by_status[r.status.value] += 1
        by_priority[r.priority.value] += 1
        if r.work_order_id is not None:
            converted += 1

    # resolved 计窗内 resolved_at（与 created 窗一致口径）
    resolved_stmt = select(Request).where(
        Request.resolved_at.is_not(None),
        Request.resolved_at >= start,
        Request.resolved_at < end_excl,
    )
    resolved_rows = list(db.execute(resolved_stmt).scalars().all())
    cycles = [
        hours_between(r.created_at, r.resolved_at)
        for r in resolved_rows
        if r.resolved_at is not None
    ]
    avg_cycle = round(sum(cycles) / len(cycles), 2) if cycles else None

    return {
        "date_from": df,
        "date_to": dt,
        "total": len(reqs),
        "by_status": by_status,
        "by_priority": by_priority,
        "received": len(reqs),
        "resolved": len(resolved_rows),
        "converted": converted,
        "avg_resolution_cycle_hours": avg_cycle,
    }
```
`app/services/analytics/__init__.py`：导出 `request_analytics`。

- [ ] **Step 4: schema**

```python
class RequestAnalytics(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    received: int
    resolved: int
    converted: int
    avg_resolution_cycle_hours: float | None
```

- [ ] **Step 5: 路由**

`app/routers/analytics.py`：import `RequestAnalytics` 与 `request_analytics`，加端点：
```python
@router.get("/requests", response_model=RequestAnalytics)
def request_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
) -> dict[str, Any]:
    return request_analytics.request_dashboard(
        db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
    )
```
> 放在 `/{dashboard}/export` 通配路由**之前**（避免 `requests` 被通配吞掉——实际 export 是 `/{dashboard}/export` 不冲突，但保持具体路由在前为稳妥）。

- [ ] **Step 6: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_requests.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(analytics): /requests request analytics endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: ⑥ /personnel 人员分析端点

**Files:**
- Create: `app/services/analytics/personnel_analytics.py`
- Modify: `app/services/analytics/__init__.py`
- Modify: `app/schemas/analytics.py`
- Modify: `app/routers/analytics.py`
- Test: `tests/test_analytics_personnel.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_personnel.py`：
```python
"""/analytics/personnel：created/completed/assigned/labor_hours/labor_cost。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_labor import WorkOrderLabor
from app.models.work_order_status import WorkOrderStatus


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_personnel_metrics(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    uid = db.execute(select(User).where(User.email == "a@acme.com")).scalar_one().id
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co,
                   created_by_user_id=uid)
    db.add(wo)
    db.flush()
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=co))
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status=WorkOrderStatus.COMPLETE.value, actor_user_id=uid,
                             company_id=co))
    db.add(WorkOrderLabor(work_order_id=wo.id, duration_seconds=3600, hourly_rate=Decimal("60"),
                          user_id=uid, company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/personnel", headers=_h(t)).json()
    row = next(r for r in body["users"] if r["user_id"] == uid)
    assert row["created_count"] == 1
    assert row["completed_count"] == 1
    assert row["assigned_count"] == 1
    assert row["labor_hours"] == 1.0
    assert row["labor_cost"] == "60.00"
```

> 核对 WorkOrderActivity 必填（`activity_type` 必填、其余可空），及 User 显示字段名（`name`）。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_personnel.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 服务**

`app/services/analytics/personnel_analytics.py`：
```python
"""人员分析（只读）：创建/完成/被指派 数 + 工时 + 工时成本。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_labor import WorkOrderLabor
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_labor_service as labor
from app.services.analytics._common import resolve_window

_CENT = Decimal("0.01")


def personnel_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    start, end_excl, df, dt = resolve_window(date_from, date_to)

    created: dict[str, int] = defaultdict(int)
    completed: dict[str, int] = defaultdict(int)
    assigned: dict[str, int] = defaultdict(int)
    hours: dict[str, float] = defaultdict(float)
    cost: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    # created：WO.created_by_user_id，created_at 落窗
    for uid in db.execute(
        select(WorkOrder.created_by_user_id).where(
            WorkOrder.created_by_user_id.is_not(None),
            WorkOrder.created_at >= start,
            WorkOrder.created_at < end_excl,
        )
    ).scalars():
        created[uid] += 1

    # completed：活动 to_status=COMPLETE 的 actor，created_at 落窗
    for uid in db.execute(
        select(WorkOrderActivity.actor_user_id).where(
            WorkOrderActivity.actor_user_id.is_not(None),
            WorkOrderActivity.to_status == WorkOrderStatus.COMPLETE.value,
            WorkOrderActivity.created_at >= start,
            WorkOrderActivity.created_at < end_excl,
        )
    ).scalars():
        completed[uid] += 1

    # assigned：assignee 关联且 WO created_at 落窗
    for uid in db.execute(
        select(WorkOrderAssignee.user_id)
        .join(WorkOrder, WorkOrderAssignee.work_order_id == WorkOrder.id)
        .where(WorkOrder.created_at >= start, WorkOrder.created_at < end_excl)
    ).scalars():
        assigned[uid] += 1

    # labor：user 维度工时与成本，labor.created_at 落窗
    for row in db.execute(
        select(WorkOrderLabor).where(
            WorkOrderLabor.user_id.is_not(None),
            WorkOrderLabor.created_at >= start,
            WorkOrderLabor.created_at < end_excl,
        )
    ).scalars():
        uid = row.user_id
        if uid is None:  # 守卫（查询已过滤非空；不用 assert 以免 -O 剥离）
            continue
        hours[uid] += row.duration_seconds / 3600.0
        cost[uid] += labor.compute_cost(row)

    uids = set(created) | set(completed) | set(assigned) | set(hours) | set(cost)
    names = {
        u.id: u.name
        for u in db.execute(select(User).where(User.id.in_(uids))).scalars()
    } if uids else {}

    users = [
        {
            "user_id": uid,
            "name": names.get(uid),
            "created_count": created.get(uid, 0),
            "completed_count": completed.get(uid, 0),
            "assigned_count": assigned.get(uid, 0),
            "labor_hours": round(hours.get(uid, 0.0), 2),
            "labor_cost": cost.get(uid, Decimal("0")).quantize(_CENT, rounding=ROUND_HALF_UP),
        }
        for uid in sorted(uids)
    ]
    return {"date_from": df, "date_to": dt, "users": users}
```
`__init__.py` 导出 `personnel_analytics`。

> 注：User 查询经 ORM 自动租户 scope，仅返回当前 company 用户名；跨租户 uid 不会出现（且数据已 company 隔离）。

- [ ] **Step 4: schema**

```python
class PersonnelRow(BaseModel):
    user_id: str
    name: str | None
    created_count: int
    completed_count: int
    assigned_count: int
    labor_hours: float
    labor_cost: Decimal


class PersonnelAnalytics(BaseModel):
    date_from: date
    date_to: date
    users: list[PersonnelRow]
```

- [ ] **Step 5: 路由**

```python
@router.get("/personnel", response_model=PersonnelAnalytics)
def personnel_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
) -> dict[str, Any]:
    return personnel_analytics.personnel_dashboard(db, date_from=date_from, date_to=date_to)
```

- [ ] **Step 6: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_personnel.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(analytics): /personnel personnel analytics endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: ⑦ /trends 时间序列端点

**Files:**
- Create: `app/services/analytics/trend_analytics.py`
- Modify: `app/services/analytics/__init__.py`
- Modify: `app/schemas/analytics.py`
- Modify: `app/routers/analytics.py`
- Test: `tests/test_analytics_trends.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_trends.py`：
```python
"""/analytics/trends：日/周分桶，连续空桶，非法 granularity 400。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123",
              "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_daily_buckets_continuous(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime(2026, 5, 30, 9),
                     company_id=co))
    db.commit()
    body = client.get(
        "/api/v1/analytics/trends?date_from=2026-05-29&date_to=2026-05-31&granularity=day",
        headers=_h(t),
    ).json()
    assert body["granularity"] == "day"
    assert len(body["buckets"]) == 3  # 29/30/31 连续
    by_start = {b["bucket_start"]: b for b in body["buckets"]}
    assert by_start["2026-05-30"]["work_orders_created"] == 1
    assert by_start["2026-05-29"]["work_orders_created"] == 0


def test_weekly_granularity(client, db):
    t = _admin(client)
    body = client.get(
        "/api/v1/analytics/trends?date_from=2026-05-01&date_to=2026-05-21&granularity=week",
        headers=_h(t),
    ).json()
    assert body["granularity"] == "week"
    assert len(body["buckets"]) == 3  # 3 个 7 天桶


def test_invalid_granularity_400(client):
    t = _admin(client)
    r = client.get("/api/v1/analytics/trends?granularity=month", headers=_h(t))
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_GRANULARITY"
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_trends.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 服务（含分桶纯函数）**

`app/services/analytics/trend_analytics.py`：
```python
"""趋势分析（只读）：按日/周分桶的吞吐时间序列。

桶为纯函数生成，覆盖整个窗口（含空桶）。完整状态历史重建超出范围。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.request import Request
from app.models.work_order import WorkOrder
from app.services.analytics._common import resolve_window

_GRANULARITIES = ("day", "week")


def _bucket_starts(df: date, dt: date, granularity: str) -> list[date]:
    """生成 [df, dt] 覆盖的桶起点列表。day=逐日；week=自 df 起每 7 天。"""
    step = timedelta(days=1 if granularity == "day" else 7)
    out: list[date] = []
    cur = df
    while cur <= dt:
        out.append(cur)
        cur = cur + step
    return out


def _bucket_index(starts: list[date], d: date) -> int | None:
    """d 落在哪个桶（最后一个 start <= d）。越界返回 None。"""
    idx = None
    for i, s in enumerate(starts):
        if s <= d:
            idx = i
        else:
            break
    return idx


def trend_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: str = "day",
) -> dict[str, Any]:
    if granularity not in _GRANULARITIES:
        raise bad_request("INVALID_GRANULARITY", "granularity 仅支持 day 或 week")
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    starts = _bucket_starts(df, dt, granularity)
    buckets = [
        {
            "bucket_start": s,
            "work_orders_created": 0,
            "work_orders_completed": 0,
            "requests_received": 0,
            "requests_resolved": 0,
        }
        for s in starts
    ]

    def _bump(ts: datetime | None, key: str) -> None:
        if ts is None:
            return
        i = _bucket_index(starts, ts.date())
        if i is not None:
            buckets[i][key] += 1  # type: ignore[operator]

    for wo in db.execute(
        select(WorkOrder).where(
            WorkOrder.created_at >= start, WorkOrder.created_at < end_excl
        )
    ).scalars():
        _bump(wo.created_at, "work_orders_created")
    for wo in db.execute(
        select(WorkOrder).where(
            WorkOrder.completed_at.is_not(None),
            WorkOrder.completed_at >= start,
            WorkOrder.completed_at < end_excl,
        )
    ).scalars():
        _bump(wo.completed_at, "work_orders_completed")
    for r in db.execute(
        select(Request).where(Request.created_at >= start, Request.created_at < end_excl)
    ).scalars():
        _bump(r.created_at, "requests_received")
    for r in db.execute(
        select(Request).where(
            Request.resolved_at.is_not(None),
            Request.resolved_at >= start,
            Request.resolved_at < end_excl,
        )
    ).scalars():
        _bump(r.resolved_at, "requests_resolved")

    return {"date_from": df, "date_to": dt, "granularity": granularity, "buckets": buckets}
```
`__init__.py` 导出 `trend_analytics`。

- [ ] **Step 4: schema**

```python
class TrendBucket(BaseModel):
    bucket_start: date
    work_orders_created: int
    work_orders_completed: int
    requests_received: int
    requests_resolved: int


class TrendAnalytics(BaseModel):
    date_from: date
    date_to: date
    granularity: str
    buckets: list[TrendBucket]
```

- [ ] **Step 5: 路由**

```python
@router.get("/trends", response_model=TrendAnalytics)
def trend_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: str = "day",
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
) -> dict[str, Any]:
    return trend_analytics.trend_dashboard(
        db, date_from=date_from, date_to=date_to, granularity=granularity
    )
```

- [ ] **Step 6: 跑绿 + 门禁 + 全量分析回归**

Run: `.venv/bin/python -m pytest tests/test_analytics_trends.py tests/test_analytics_api.py tests/test_analytics_export.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(analytics): /trends time-series endpoint (day/week)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9B: CSV 导出补三新面板（spec §4.2）

**Files:**
- Modify: `app/routers/analytics.py`
- Test: `tests/test_analytics_export.py`

- [ ] **Step 1: 写失败测试**

`tests/test_analytics_export.py` 追加：
```python
def test_export_new_dashboards(client):
    t = _admin(client)  # 复用文件内既有 _admin/_h（若无则照 test_analytics_api.py 补）
    for path in ("requests", "personnel", "trends"):
        r = client.get(f"/api/v1/analytics/{path}/export", headers=_h(t))
        assert r.status_code == 200, (path, r.text)
        assert r.headers["content-type"].startswith("text/csv")


def test_export_unknown_404(client):
    t = _admin(client)
    assert client.get("/api/v1/analytics/nope/export", headers=_h(t)).status_code == 404
```
> 若该测试文件未定义 `_admin`/`_h`，从 `test_analytics_api.py` 复制这两个 helper 到文件顶部。

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/test_analytics_export.py::test_export_new_dashboards -q`
Expected: FAIL（404，switch 无分支）。

- [ ] **Step 3: 实现**

`app/routers/analytics.py`：加三个扁平化 helper：
```python
def _requests_csv(data: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    rows: list[list[Any]] = [[k, v] for k, v in data["by_status"].items()]
    return ["status", "count"], rows


def _personnel_csv(data: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    rows = [
        [r["user_id"], r["name"], r["created_count"], r["completed_count"],
         r["assigned_count"], r["labor_hours"], r["labor_cost"]]
        for r in data["users"]
    ]
    return (
        ["user_id", "name", "created", "completed", "assigned", "labor_hours", "labor_cost"],
        rows,
    )


def _trends_csv(data: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    rows = [
        [b["bucket_start"], b["work_orders_created"], b["work_orders_completed"],
         b["requests_received"], b["requests_resolved"]]
        for b in data["buckets"]
    ]
    return (
        ["bucket_start", "wo_created", "wo_completed", "req_received", "req_resolved"],
        rows,
    )
```
`export_dashboard_csv`：函数签名加 `granularity: str = "day",`；在 `else:` 抛 404 前加分支：
```python
    elif dashboard == "requests":
        data = request_analytics.request_dashboard(
            db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
        )
        header, rows = _requests_csv(data)
    elif dashboard == "personnel":
        data = personnel_analytics.personnel_dashboard(db, date_from=date_from, date_to=date_to)
        header, rows = _personnel_csv(data)
    elif dashboard == "trends":
        data = trend_analytics.trend_dashboard(
            db, date_from=date_from, date_to=date_to, granularity=granularity
        )
        header, rows = _trends_csv(data)
```

- [ ] **Step 4: 跑绿 + 门禁**

Run: `.venv/bin/python -m pytest tests/test_analytics_export.py -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: PASS。

- [ ] **Step 5: commit**

```bash
git add -A && git commit -m "feat(analytics): CSV export for requests/personnel/trends

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 统一迁移 + 单测 + 零漂移

**Files:**
- Create: `alembic/versions/20260602_0004_analytics_backfill.py`
- Test: `tests/unit/test_migration_analytics_backfill.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_migration_analytics_backfill.py`：
```python
"""迁移 analytics_backfill：链路 + up/down 可重放（SQLite）。"""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _mod():
    return importlib.import_module("alembic.versions.20260602_0004_analytics_backfill")


def test_migration_revision_chain():
    m = _mod()
    assert m.revision == "analytics_backfill"
    assert m.down_revision == "workorder_labor_cost"


def test_upgrade_then_downgrade_sqlite():
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE tb_company (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE tb_work_order (id VARCHAR(36) PRIMARY KEY, title VARCHAR(300))"
        )
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _mod().upgrade()
            insp = inspect(conn)
            assert "tb_work_order_category" in insp.get_table_names()
            wo_cols = {c["name"] for c in insp.get_columns("tb_work_order")}
            assert {"category_id", "created_by_user_id"} <= wo_cols
            _mod().downgrade()
            insp2 = inspect(conn)
            assert "tb_work_order_category" not in insp2.get_table_names()
            wo_cols2 = {c["name"] for c in insp2.get_columns("tb_work_order")}
            assert "category_id" not in wo_cols2 and "created_by_user_id" not in wo_cols2
```

- [ ] **Step 2: 跑红**

Run: `.venv/bin/python -m pytest tests/unit/test_migration_analytics_backfill.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 迁移**

`alembic/versions/20260602_0004_analytics_backfill.py`：
```python
"""analytics backfill: tb_work_order_category + tb_work_order.(category_id, created_by_user_id)

Revision ID: analytics_backfill
Revises: workorder_labor_cost
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test)。新建工单分类表并给工单加两列。
全新表/列、无数据平移。MySQL 全链 alembic 重放受既有 initial_schema 问题阻塞
（与本迁移无关）；DDL 以最小 fixture 单测验证，全链待生产手验。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "analytics_backfill"
down_revision: str | Sequence[str] | None = "workorder_labor_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_work_order_category",
        sa.Column("name", sa.String(length=300), nullable=False),
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
            name=op.f("fk_tb_work_order_category_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_category")),
        sa.UniqueConstraint(
            "company_id", "name", name="uq_work_order_category_company_name"
        ),
    )
    op.create_index(
        op.f("ix_tb_work_order_category_company_id"),
        "tb_work_order_category",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_category_created_at"),
        "tb_work_order_category",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_category_is_active"),
        "tb_work_order_category",
        ["is_active"],
        unique=False,
    )

    op.add_column(
        "tb_work_order",
        sa.Column("category_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_tb_work_order_category_id"), "tb_work_order", ["category_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_tb_work_order_category_id"),
        "tb_work_order",
        "tb_work_order_category",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "tb_work_order",
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_tb_work_order_created_by_user_id"),
        "tb_work_order",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tb_work_order_created_by_user_id"), table_name="tb_work_order")
    op.drop_column("tb_work_order", "created_by_user_id")
    op.drop_constraint(
        op.f("fk_tb_work_order_category_id"), "tb_work_order", type_="foreignkey"
    )
    op.drop_index(op.f("ix_tb_work_order_category_id"), table_name="tb_work_order")
    op.drop_column("tb_work_order", "category_id")

    op.drop_index(
        op.f("ix_tb_work_order_category_is_active"), table_name="tb_work_order_category"
    )
    op.drop_index(
        op.f("ix_tb_work_order_category_created_at"), table_name="tb_work_order_category"
    )
    op.drop_index(
        op.f("ix_tb_work_order_category_company_id"), table_name="tb_work_order_category"
    )
    op.drop_table("tb_work_order_category")
```

> **SQLite 注意**：`create_foreign_key` 与 `drop_constraint(type_="foreignkey")` 在纯 SQLite ALTER 下不被支持，会使单测失败。若单测报错，改用 batch 模式或在单测里只断言列/表存在性而非 FK；MySQL 生产端 FK 必须保留。**实现者优先方案**：迁移中对 `tb_work_order` 的两列改用 `op.batch_alter_table("tb_work_order") as batch:` 包裹 add_column / create_index / FK（batch 模式对 SQLite 安全、对 MySQL 退化为直接 ALTER）。按需重写 upgrade/downgrade 为 batch 形式后再跑单测。

- [ ] **Step 4: 跑绿（如遇 SQLite FK 限制，改 batch 后再跑）**

Run: `.venv/bin/python -m pytest tests/unit/test_migration_analytics_backfill.py -q`
Expected: PASS。

- [ ] **Step 5: 模型 vs 迁移列对账 + 零漂移**

逐列核对 `tb_work_order_category` 与 `WorkOrderCategory`（mixin 列、索引、唯一约束、FK ondelete 全一致）。然后：
```bash
.venv/bin/alembic upgrade head && .venv/bin/alembic check
```
Expected: `tb_work_order_category` 与两新列**零漂移**（若 `alembic check` 报漂移，仅应是既有 `tb_procedure_*` 等历史问题，与本迁移无关——grep 确认新对象不在漂移行）。

> 若本地 alembic 全链受既有 initial_schema 阻塞而无法 `upgrade head`，记录于迁移 docstring（已含声明），以单测 DDL 验证为准（沿用 2A T6 做法）。

- [ ] **Step 6: 全量回归 + 门禁**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check app/ && .venv/bin/mypy app/`
Expected: 全 PASS / All checks passed。

- [ ] **Step 7: commit**

```bash
git add -A && git commit -m "feat(analytics): unified migration for category table + work order columns

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 跨任务回归与收尾

完成 T1–T10 后由控制者派发最终 code review（subagent-driven-development 的末步），再用 `superpowers:finishing-a-development-branch`。

**自查清单（实现期间随时核对）：**
- Decimal 全部经 Pydantic 序列化为字符串；金额量化沿用 2A `_q`（2dp ROUND_HALF_UP）。
- 时长/百分比为 float、`round(..., 2)`。
- 所有新查询对象（WorkOrderCategory/Labor/AdditionalCost/Request/WorkOrder/PartConsumption/User）均 TenantScoped → 自动租户隔离；新端点至少各有 1 条跨租户/隔离断言（cost/wo-distribution 已含；requests/personnel/trends 可在对应测试补一条 B 公司查询为空的断言）。
- 无 `assert` 用于生产控制流（仅测试与 mypy 缩窄用）。
```
