# P6 商业化门控骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 CMMS 加一道与 RBAC 正交的套餐门控：三档 Free/Pro/Enterprise 限制座席数与高级功能模块的访问，platform admin 可手动设档，公司可自查订阅；Stripe 真实支付留下一轮。

**Architecture:** 新增 `app/billing/catalog.py` 硬编码三档常量 + 纯函数 `effective_features`/`effective_seat_limit`（订阅失效降级到 Free 功能集）。新增 `require_feature(f)` FastAPI 依赖，挂在 5 个高级模块 router 上，与既有 `require_permission` 叠加；`super_admin` 通配权限但不绕 feature gate。座席校验接入 invite 路径。platform admin 经受保护端点手动设档。前端 Pinia billing store 拉取订阅，导航对未解锁模块显示锁标。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + pytest（后端）；Vue 3 + Pinia + Element Plus + vue-i18n + Vitest（前端）。

设计依据：`docs/superpowers/specs/2026-06-04-p6-commercialization-gating-design.md`。

---

## 契约（前后端共享，全程以此为准）

**Plan 枚举值**：`free` / `pro` / `enterprise`
**Feature 枚举值**：`preventive_maintenance` / `meters` / `purchasing` / `analytics` / `sop`
**SubscriptionStatus**：`active` / `trialing`（生效）、`past_due` / `canceled` / `suspended`（失效，降级到 free）
**座席上限**：free=3 / pro=15 / enterprise=null(无限)

**`GET /api/v1/billing/subscription`**（登录即可）响应：
```json
{
  "plan": "free",
  "subscription_status": "active",
  "seat_used": 1,
  "seat_limit": 3,
  "features": ["preventive_maintenance", "meters", "purchasing", "analytics", "sop"],
  "catalog": [
    {"plan": "free", "seat_limit": 3, "features": []},
    {"plan": "pro", "seat_limit": 15, "features": ["preventive_maintenance","meters","purchasing","analytics","sop"]},
    {"plan": "enterprise", "seat_limit": null, "features": ["preventive_maintenance","meters","purchasing","analytics","sop"]}
  ]
}
```
（`seat_limit: null` = 无限；`features` = 当前**生效**的已解锁功能集）

**`PATCH /api/v1/platform/companies/{company_id}/subscription`**（require is_platform_admin）body：
```json
{"plan": "pro", "subscription_status": "active"}
```
响应：`{"plan": "pro", "subscription_status": "active"}`（更新后快照）。

**HTTP 语义**：feature 未解锁 / 座席超限 → **402**；platform 权限不足 → **403**；company 不存在 → **404**。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `app/billing/__init__.py` | 创建 | 空包标记 |
| `app/billing/catalog.py` | 创建 | Plan/Feature 枚举、PLAN_CATALOG 常量、effective_features/effective_seat_limit/seat helper 纯函数 |
| `app/errors.py` | 修改 | 加 `payment_required`(402) |
| `app/deps.py` | 修改 | 加 `require_feature(f)`、`require_platform_admin` |
| `app/models/company.py` | 修改 | plan/subscription_status 加 Python default |
| `app/schemas/billing.py` | 创建 | SubscriptionRead / PlanCatalogEntry / SubscriptionUpdate |
| `app/routers/billing.py` | 创建 | GET /billing/subscription |
| `app/routers/platform.py` | 创建 | PATCH /platform/companies/{id}/subscription |
| `app/services/invitation_service.py` | 修改 | invite 前座席校验 |
| `app/routers/{preventive_maintenances,meters,purchase_orders,analytics,procedures,procedure_groups,nodes,parse,batch_imports,heading_rules,folders}.py` | 修改 | router 加 `dependencies=[Depends(require_feature(...))]` |
| `app/main.py` | 修改 | 注册 billing / platform router |
| `alembic/versions/20260604_0002_p6_commercialization_gating.py` | 创建 | backfill plan/status + server_default |
| 前端 `src/api/billing.ts` / `src/store/billing.ts` / `src/views/billing/*.vue` / 路由 / `AppSidebar.vue` / `zh-CN.ts` | 创建/修改 | 见前端 Task |

---

## Task 1: billing catalog（枚举 + 常量 + 纯函数）

**Files:**
- Create: `backend/app/billing/__init__.py`
- Create: `backend/app/billing/catalog.py`
- Test: `backend/tests/unit/test_billing_catalog.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_billing_catalog.py`

```python
"""三档 catalog 纯函数：生效解锁所购功能，失效降级到 free。"""

from app.billing.catalog import (
    PLAN_CATALOG,
    Feature,
    Plan,
    effective_features,
    effective_seat_limit,
)


def test_catalog_shape():
    assert PLAN_CATALOG[Plan.free].seat_limit == 3
    assert PLAN_CATALOG[Plan.free].features == frozenset()
    assert PLAN_CATALOG[Plan.pro].seat_limit == 15
    assert PLAN_CATALOG[Plan.enterprise].seat_limit is None
    pro_feats = PLAN_CATALOG[Plan.pro].features
    assert pro_feats == {
        Feature.preventive_maintenance,
        Feature.meters,
        Feature.purchasing,
        Feature.analytics,
        Feature.sop,
    }
    # enterprise 至少含 pro 全部
    assert pro_feats <= PLAN_CATALOG[Plan.enterprise].features


def test_effective_features_active_unlocks_plan():
    assert effective_features("pro", "active") == PLAN_CATALOG[Plan.pro].features
    assert effective_features("free", "active") == frozenset()
    assert effective_features("enterprise", "trialing") == PLAN_CATALOG[Plan.enterprise].features


def test_effective_features_inactive_downgrades_to_free():
    for status in ("past_due", "canceled", "suspended"):
        assert effective_features("pro", status) == frozenset()
        assert effective_features("enterprise", status) == frozenset()


def test_effective_seat_limit():
    assert effective_seat_limit("free", "active") == 3
    assert effective_seat_limit("pro", "active") == 15
    assert effective_seat_limit("enterprise", "active") is None
    # 失效降到 free=3
    assert effective_seat_limit("pro", "canceled") == 3
    assert effective_seat_limit("enterprise", "suspended") == 3


def test_unknown_or_null_plan_treated_as_free():
    assert effective_features(None, "active") == frozenset()
    assert effective_features("bogus", "active") == frozenset()
    assert effective_seat_limit(None, "active") == 3
```

- [ ] **Step 2: 跑红** `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_catalog.py -v` → FAIL（ModuleNotFoundError: app.billing）。

- [ ] **Step 3: 建包** —— 创建空文件 `backend/app/billing/__init__.py`（内容为单行 docstring）：

```python
"""商业化门控（Phase 6）：套餐 catalog 与功能/座席门控。"""
```

- [ ] **Step 4: 写 catalog** `backend/app/billing/catalog.py`

```python
"""套餐 catalog：硬编码三档常量 + 有效功能/座席纯函数（Phase 6 门控骨架）。

订阅"生效"(active/trialing)→解锁所购档位功能；失效→降级到 free 功能集。
纯函数接受 plan/status 字符串（不依赖 ORM 对象），便于单测与复用。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Plan(enum.StrEnum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Feature(enum.StrEnum):
    preventive_maintenance = "preventive_maintenance"
    meters = "meters"
    purchasing = "purchasing"
    analytics = "analytics"
    sop = "sop"


# 订阅生效状态：解锁所购档位功能；其余状态降级到 free。
ACTIVE_STATUSES = frozenset({"active", "trialing"})
ALL_STATUSES = frozenset({"active", "trialing", "past_due", "canceled", "suspended"})

_PRO_FEATURES = frozenset(
    {
        Feature.preventive_maintenance,
        Feature.meters,
        Feature.purchasing,
        Feature.analytics,
        Feature.sop,
    }
)


@dataclass(frozen=True)
class PlanSpec:
    seat_limit: int | None  # None = 无限
    features: frozenset[Feature]


PLAN_CATALOG: dict[Plan, PlanSpec] = {
    Plan.free: PlanSpec(seat_limit=3, features=frozenset()),
    Plan.pro: PlanSpec(seat_limit=15, features=_PRO_FEATURES),
    Plan.enterprise: PlanSpec(seat_limit=None, features=_PRO_FEATURES),
}


def _resolve_plan(plan: str | None) -> Plan:
    """未知/空 plan 视为 free（容错，不抛）。"""
    try:
        return Plan(plan) if plan else Plan.free
    except ValueError:
        return Plan.free


def effective_features(plan: str | None, status: str | None) -> frozenset[Feature]:
    if status not in ACTIVE_STATUSES:
        return PLAN_CATALOG[Plan.free].features
    return PLAN_CATALOG[_resolve_plan(plan)].features


def effective_seat_limit(plan: str | None, status: str | None) -> int | None:
    if status not in ACTIVE_STATUSES:
        return PLAN_CATALOG[Plan.free].seat_limit
    return PLAN_CATALOG[_resolve_plan(plan)].seat_limit
```

- [ ] **Step 5: 跑绿** `.venv/bin/python -m pytest tests/unit/test_billing_catalog.py -v` → PASS。门禁 `.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app`。

- [ ] **Step 6: Commit**

```bash
git add backend/app/billing backend/tests/unit/test_billing_catalog.py
git commit -m "feat(p6): billing catalog 三档常量 + effective_features/seat 纯函数"
```

---

## Task 2: Company 默认值 + Alembic 迁移

**Files:**
- Modify: `backend/app/models/company.py:31-32`
- Create: `backend/alembic/versions/20260604_0002_p6_commercialization_gating.py`
- Test: `backend/tests/unit/test_migration_p6_billing.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_migration_p6_billing.py`

```python
"""P6 迁移：backfill 存量公司 plan/status + server_default。"""

import importlib

MOD = "alembic.versions.20260604_0002_p6_commercialization_gating"


def test_migration_module_importable_with_revisions():
    m = importlib.import_module(MOD)
    assert m.revision == "p6_commercialization_gating"
    assert m.down_revision == "workorder_2b_backfill"
    assert hasattr(m, "upgrade") and hasattr(m, "downgrade")
```

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/unit/test_migration_p6_billing.py -v` → FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 模型加 Python default** —— `backend/app/models/company.py`，把第 31-32 行替换为（让 ORM 新建公司自动有值）：

```python
    # Billing (Phase 6): default free/active; platform admin 手动改档。
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    subscription_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
```

- [ ] **Step 4: 写迁移** `backend/alembic/versions/20260604_0002_p6_commercialization_gating.py`

```python
"""P6 commercialization gating: backfill plan/subscription_status + server_default.

Revision ID: p6_commercialization_gating
Revises: workorder_2b_backfill
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "p6_commercialization_gating"
down_revision = "workorder_2b_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) backfill 存量 NULL → free/active
    op.execute("UPDATE tb_company SET plan = 'free' WHERE plan IS NULL")
    op.execute(
        "UPDATE tb_company SET subscription_status = 'active' "
        "WHERE subscription_status IS NULL"
    )
    # 2) 设 server_default + NOT NULL
    with op.batch_alter_table("tb_company") as batch:
        batch.alter_column(
            "plan",
            existing_type=sa.String(length=32),
            server_default="free",
            nullable=False,
        )
        batch.alter_column(
            "subscription_status",
            existing_type=sa.String(length=32),
            server_default="active",
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_company") as batch:
        batch.alter_column(
            "subscription_status",
            existing_type=sa.String(length=32),
            server_default=None,
            nullable=True,
        )
        batch.alter_column(
            "plan",
            existing_type=sa.String(length=32),
            server_default=None,
            nullable=True,
        )
```

- [ ] **Step 5: 跑绿** `.venv/bin/python -m pytest tests/unit/test_migration_p6_billing.py -v` → PASS。

- [ ] **Step 6: 校验单 head** `.venv/bin/alembic heads` → 应仅 `p6_commercialization_gating (head)`。

- [ ] **Step 7: 全量回归**（模型改 nullable 可能影响既有测试建 Company 的路径）`.venv/bin/python -m pytest tests/test_auth_api.py -q` → PASS。门禁同 Task 1。

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/company.py backend/alembic/versions/20260604_0002_p6_commercialization_gating.py backend/tests/unit/test_migration_p6_billing.py
git commit -m "feat(p6): Company plan/status 默认 free/active + 迁移 backfill"
```

---

## Task 3: payment_required 错误 + require_feature 依赖 + 首个 router 挂闸（meters）

**Files:**
- Modify: `backend/app/errors.py`（末尾加 helper）
- Modify: `backend/app/deps.py`（加 require_feature）
- Modify: `backend/app/routers/meters.py:29`（router 加 dependencies）
- Test: `backend/tests/test_feature_gating.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_feature_gating.py`

```python
"""feature gate 与 RBAC 正交叠加：free 锁高级模块，pro 解锁，super_admin 不绕。"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _set_plan(db, *, plan, status="active"):
    company = db.execute(select(Company)).scalars().first()
    company.plan = plan
    company.subscription_status = status
    db.commit()


def test_meters_locked_on_free_returns_402(client):
    t = _admin(client)  # 新公司默认 free
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "FEATURE_LOCKED"


def test_meters_unlocked_on_pro(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 200, r.text


def test_super_admin_does_not_bypass_feature_gate(client, db):
    # 注册用户即 super_admin（通配权限），但 free 档仍被 feature gate 拦
    t = _admin(client)
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text


def test_pro_but_inactive_status_downgrades(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro", status="past_due")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text
```

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_feature_gating.py -v` → FAIL（meters 当前返回 200，无 feature gate）。

- [ ] **Step 3: errors 加 402 helper** —— `backend/app/errors.py` 末尾追加：

```python
def payment_required(code: str, message: str, field: str | None = None) -> HTTPException:
    return app_error(status.HTTP_402_PAYMENT_REQUIRED, code, message, field)
```

- [ ] **Step 4: deps 加 require_feature** —— `backend/app/deps.py`：import 区加（在现有 import 后）：

```python
from app.billing.catalog import Feature, effective_features
from app.errors import payment_required
from app.models.company import Company
```

在 `require_permission` 函数之后追加：

```python
def require_feature(feature: Feature) -> Callable[..., User]:
    """Return a dependency enforcing the company's plan includes the feature.

    与 require_permission 正交：super_admin 通配权限但不绕此闸门。
    订阅失效时 effective_features 已降级到 free，故自动锁高级模块。
    """

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        company = db.get(Company, current_user.company_id)
        plan = company.plan if company else None
        status_ = company.subscription_status if company else None
        if feature not in effective_features(plan, status_):
            raise payment_required("FEATURE_LOCKED", "当前套餐未包含此功能，请升级订阅")
        return current_user

    return checker
```

并把 `require_feature` 加入 `__all__`。

- [ ] **Step 5: meters router 挂闸** —— `backend/app/routers/meters.py`：import 区加 `from app.billing.catalog import Feature` 和（若未导入）`from app.deps import require_feature`（注意该文件如何 import deps：若用 `from app.deps import ...` 风格则追加 `require_feature`；若用 `from app import deps` 则用 `deps.require_feature`）。然后把第 29 行 router 定义改为：

```python
router = APIRouter(
    prefix="/api/v1/meters",
    tags=["meters"],
    dependencies=[Depends(require_feature(Feature.meters))],
)
```

（`Depends` 已在该文件 import；确认 `from fastapi import APIRouter, Depends, status` 在顶部。）

- [ ] **Step 6: 跑绿** `.venv/bin/python -m pytest tests/test_feature_gating.py -v` → PASS。回归 meters 既有测试 `.venv/bin/python -m pytest tests/test_meters_api.py -q`（注意：既有 meters 测试若用 free 公司直调将变 402——见下方注意）。门禁同上。

> **注意（重要）**：既有 `tests/test_meters_api.py` 等高级模块测试用 `_admin` 注册的 free 公司直接访问，挂闸后会变 402 而回归失败。**修复方式**：在这些既有测试的注册 helper 后把公司升到 pro。最稳妥做法——在 `tests/conftest.py` 加一个共享 helper `seed_pro_company(db)` 或让既有测试各自调 `_set_plan`。本 Task Step 7 处理。

- [ ] **Step 7: 修既有 meters 测试** —— `tests/test_meters_api.py`：在其注册 helper（如 `_admin`/`_token`）拿到 token 后，用 db fixture 把公司升 pro。最小改动：给每个 client 测试加 `db` 参数并在注册后调用一个本地 helper：

```python
from sqlalchemy import select
from app.models.company import Company

def _unlock_pro(db):
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"
    c.subscription_status = "active"
    db.commit()
```

在每个访问 `/api/v1/meters` 的测试里，注册后、首次调用前插入 `_unlock_pro(db)`（函数签名加 `db` fixture）。跑 `.venv/bin/python -m pytest tests/test_meters_api.py -q` → PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/errors.py backend/app/deps.py backend/app/routers/meters.py backend/tests/test_feature_gating.py backend/tests/test_meters_api.py
git commit -m "feat(p6): require_feature 依赖 + meters 挂闸 + 402 payment_required"
```

---

## Task 4: 其余高级模块 router 挂闸（PM / purchasing / analytics + SOP 7 router）

**Files (Modify, 各加 router dependencies + import):**
- `backend/app/routers/preventive_maintenances.py:24` → `Feature.preventive_maintenance`
- `backend/app/routers/purchase_orders.py:26` → `Feature.purchasing`
- `backend/app/routers/analytics.py:39` → `Feature.analytics`
- `backend/app/routers/procedures.py:48` → `Feature.sop`
- `backend/app/routers/procedure_groups.py:17` → `Feature.sop`
- `backend/app/routers/nodes.py:21` → `Feature.sop`
- `backend/app/routers/parse.py:17` → `Feature.sop`
- `backend/app/routers/batch_imports.py:33` → `Feature.sop`
- `backend/app/routers/heading_rules.py:21` → `Feature.sop`
- `backend/app/routers/folders.py:28` → `Feature.sop`
- Test: 扩展 `backend/tests/test_feature_gating.py`

- [ ] **Step 1: 扩展失败测试** —— 在 `tests/test_feature_gating.py` 追加（覆盖每个高级模块代表端点 + RBAC 正交）：

```python
import pytest

# (path, feature 所属模块) —— 代表性 GET 端点
_LOCKED_ENDPOINTS = [
    "/api/v1/preventive-maintenances",
    "/api/v1/purchase-orders",
    "/api/v1/analytics/work-orders",
    "/api/v1/procedures",
    "/api/v1/procedure-groups",
    "/api/v1/folders",
    "/api/v1/batch-imports",
]


@pytest.mark.parametrize("path", _LOCKED_ENDPOINTS)
def test_advanced_endpoints_locked_on_free(client, path):
    t = _admin(client)
    r = client.get(path, headers=_h(t))
    assert r.status_code == 402, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.parametrize("path", _LOCKED_ENDPOINTS)
def test_advanced_endpoints_unlocked_on_pro(client, db, path):
    t = _admin(client)
    _set_plan(db, plan="pro")
    r = client.get(path, headers=_h(t))
    assert r.status_code != 402, f"{path} -> {r.status_code} {r.text}"


def test_core_modules_not_feature_gated(client):
    # 核心模块在 free 档仍可访问（不被 feature gate 拦）
    t = _admin(client)
    for path in ("/api/v1/work-orders", "/api/v1/assets", "/api/v1/locations", "/api/v1/requests"):
        r = client.get(path, headers=_h(t))
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
```

> 确认各代表端点的真实路径：PM=`/api/v1/preventive-maintenances`(GET list)、purchasing=`/api/v1/purchase-orders`、analytics 取一个已存在的 GET（如 `/api/v1/analytics/work-orders`，执行时用 `grep -n '@router.get' app/routers/analytics.py` 核实首个 GET 路径并替换）、procedures=`/api/v1/procedures`、procedure-groups=`/api/v1/procedure-groups`、folders=`/api/v1/folders`、batch-imports=`/api/v1/batch-imports`。`nodes`/`parse`/`heading_rules` 端点需路径参数或 POST，挂闸由 router dependencies 保证、不单独在此 GET 测。

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_feature_gating.py -v` → 新增用例 FAIL（这些 router 尚未挂闸，返回非 402）。

- [ ] **Step 3: 逐个 router 挂闸** —— 对上述 10 个 router 文件，各做两步改动：

  (a) import 区加 `from app.billing.catalog import Feature`；确认 `require_feature` 可用（按该文件既有 deps import 风格补 `require_feature`）；确认 `Depends` 已从 fastapi import。

  (b) 把 router 定义加 `dependencies=[Depends(require_feature(Feature.<对应值>))]`。示例（preventive_maintenances.py:24）：

```python
router = APIRouter(
    prefix="/api/v1/preventive-maintenances",
    tags=["preventive-maintenances"],
    dependencies=[Depends(require_feature(Feature.preventive_maintenance))],
)
```

  `nodes.py`（无 prefix）：

```python
router = APIRouter(
    tags=["nodes"],
    dependencies=[Depends(require_feature(Feature.sop))],
)
```

  `parse.py` / `heading_rules.py`（prefix="/api/v1"）同样加 `dependencies=[Depends(require_feature(Feature.sop))]`。

- [ ] **Step 4: 跑绿** `.venv/bin/python -m pytest tests/test_feature_gating.py -v` → PASS。

- [ ] **Step 5: 修既有高级模块测试** —— 挂闸后，以下测试文件中用 free 公司直访这些 router 的用例会变 402。逐个文件加 `_unlock_pro(db)`（同 Task 3 Step 7 模式）：`tests/test_preventive_maintenances_api.py`、`tests/test_purchase_orders_api.py`、`tests/test_analytics*.py`、`tests/test_procedures*.py`、`tests/test_procedure_groups_api.py`、`tests/test_nodes_api.py`、`tests/test_parse*.py`、`tests/test_batch_imports*.py`、`tests/test_heading_rules_api.py`、`tests/test_folders_api.py`。

  执行策略：先 `.venv/bin/python -m pytest tests/ -q` 看哪些 FAIL（应均为 402），对每个失败文件的注册 helper 之后插入升 pro。许多文件共用 `_admin` 风格 helper——可在该文件加 `_unlock_pro(db)` 并在 client 测试签名补 `db`。

> **替代更省力方案（推荐执行者采用）**：在 `tests/conftest.py` 提供一个 autouse 选项不可行（会破坏本 Task 的 free 测试）。改为提供共享 helper：在 `conftest.py` 加顶层函数 `def unlock_all_features(db): ...`（把当前公司设 enterprise+active），高级模块测试 import 后在注册后调用。减少各文件重复定义。

- [ ] **Step 6: 全量回归** `.venv/bin/python -m pytest -q` → 全绿。门禁同上。

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers backend/tests
git commit -m "feat(p6): PM/purchasing/analytics/SOP 全部高级 router 挂 feature gate + 修既有测试"
```

---

## Task 5: require_platform_admin + platform 设档端点

**Files:**
- Modify: `backend/app/deps.py`（加 require_platform_admin）
- Create: `backend/app/schemas/billing.py`（SubscriptionUpdate 部分）
- Create: `backend/app/routers/platform.py`
- Modify: `backend/app/main.py`（注册 platform router）
- Test: `backend/tests/test_platform_subscription_api.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_platform_subscription_api.py`

```python
"""platform 设档端点：仅 is_platform_admin 可改任意公司订阅。"""

from sqlalchemy import select

from app.models.company import Company
from app.models.user import User


def _admin(client, company, email):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug_part):
    return db.execute(
        select(Company).where(Company.name == slug_part)
    ).scalar_one().id


def _make_platform_admin(db, email):
    u = db.execute(select(User).where(User.email == email)).scalar_one()
    u.is_platform_admin = True
    db.commit()


def test_non_platform_admin_forbidden(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 403, r.text


def test_platform_admin_can_set_plan(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"plan": "pro", "subscription_status": "active"}
    # 升档后该公司可访问高级模块
    assert client.get("/api/v1/meters", headers=_h(t)).status_code == 200


def test_unknown_company_404(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        "/api/v1/platform/companies/nonexistent-id/subscription",
        headers=_h(t),
        json={"plan": "pro", "subscription_status": "active"},
    )
    assert r.status_code == 404, r.text


def test_invalid_plan_rejected(client, db):
    t = _admin(client, "Acme", "a@acme.com")
    cid = _company_id(db, "Acme")
    _make_platform_admin(db, "a@acme.com")
    r = client.patch(
        f"/api/v1/platform/companies/{cid}/subscription",
        headers=_h(t),
        json={"plan": "platinum", "subscription_status": "active"},
    )
    assert r.status_code == 422, r.text
```

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_platform_subscription_api.py -v` → FAIL（404 路由不存在）。

- [ ] **Step 3: deps 加 require_platform_admin** —— `backend/app/deps.py` 在 `require_feature` 之后追加，并入 `__all__`：

```python
def require_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """仅平台运营身份（is_platform_admin）可通过。普通公司 super_admin 不可。"""
    if not current_user.is_platform_admin:
        raise forbidden("PLATFORM_ONLY", "仅平台管理员可操作")
    return current_user
```

- [ ] **Step 4: schema** `backend/app/schemas/billing.py`（先建含 SubscriptionUpdate；SubscriptionRead 在 Task 6 补到同文件）

```python
"""商业化订阅 schema（Phase 6）。"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.billing.catalog import ALL_STATUSES, Plan


class SubscriptionUpdate(BaseModel):
    plan: str
    subscription_status: str

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str) -> str:
        if v not in {p.value for p in Plan}:
            raise ValueError("无效的套餐档位")
        return v

    @field_validator("subscription_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ALL_STATUSES:
            raise ValueError("无效的订阅状态")
        return v
```

- [ ] **Step 5: platform router** `backend/app/routers/platform.py`

```python
"""平台运营端点（Phase 6）：手动设公司套餐/订阅状态。仅 is_platform_admin。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_platform_admin
from app.errors import not_found
from app.models.company import Company
from app.models.user import User
from app.schemas.billing import SubscriptionUpdate

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


@router.patch("/companies/{company_id}/subscription")
def set_company_subscription(
    company_id: str,
    payload: SubscriptionUpdate,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # Company 非 tenant-scoped，db.get 直取任意公司。
    company = db.get(Company, company_id)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    company.plan = payload.plan
    company.subscription_status = payload.subscription_status
    db.commit()
    return {"plan": company.plan, "subscription_status": company.subscription_status}
```

- [ ] **Step 6: 注册 router** —— `backend/app/main.py`：在 import 块（约 23-65 行的 `from app.routers import (...)` 或末尾单独 import 区）加入 `platform`，并在 include_router 区（约 171 行后）加：

```python
app.include_router(platform.router)
```

（按文件现有 import 风格：若集中 import，则在 routers 元组里加 `platform`；执行时 `grep -n "from app.routers import" app/main.py` 确认风格。）

- [ ] **Step 7: 跑绿** `.venv/bin/python -m pytest tests/test_platform_subscription_api.py -v` → PASS。门禁同上。

- [ ] **Step 8: Commit**

```bash
git add backend/app/deps.py backend/app/schemas/billing.py backend/app/routers/platform.py backend/app/main.py backend/tests/test_platform_subscription_api.py
git commit -m "feat(p6): platform admin 手动设档端点 + require_platform_admin"
```

---

## Task 6: billing 自查端点

**Files:**
- Modify: `backend/app/schemas/billing.py`（加 SubscriptionRead / PlanCatalogEntry）
- Create: `backend/app/routers/billing.py`
- Modify: `backend/app/main.py`（注册 billing router）
- Test: `backend/tests/test_billing_subscription_api.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_billing_subscription_api.py`

```python
"""公司自查订阅端点：登录即可，返回档位/座席/已解锁功能/三档 catalog。"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_subscription_default_free(client):
    t = _admin(client)
    r = client.get("/api/v1/billing/subscription", headers=_h(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "active"
    assert body["seat_used"] == 1  # 注册的 super_admin
    assert body["seat_limit"] == 3
    assert body["features"] == []
    # catalog 含三档
    plans = {e["plan"] for e in body["catalog"]}
    assert plans == {"free", "pro", "enterprise"}
    enterprise = next(e for e in body["catalog"] if e["plan"] == "enterprise")
    assert enterprise["seat_limit"] is None


def test_subscription_reflects_pro(client, db):
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"
    db.commit()
    body = client.get("/api/v1/billing/subscription", headers=_h(t)).json()
    assert body["plan"] == "pro"
    assert body["seat_limit"] == 15
    assert set(body["features"]) == {
        "preventive_maintenance", "meters", "purchasing", "analytics", "sop"
    }


def test_subscription_requires_auth(client):
    assert client.get("/api/v1/billing/subscription").status_code == 401
```

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_billing_subscription_api.py -v` → FAIL（404）。

- [ ] **Step 3: schema 补 Read** —— `backend/app/schemas/billing.py` 追加：

```python
class PlanCatalogEntry(BaseModel):
    plan: str
    seat_limit: int | None
    features: list[str]


class SubscriptionRead(BaseModel):
    plan: str
    subscription_status: str
    seat_used: int
    seat_limit: int | None
    features: list[str]
    catalog: list[PlanCatalogEntry]
```

- [ ] **Step 4: billing router** `backend/app/routers/billing.py`

```python
"""公司订阅自查端点（Phase 6）：登录即可查看本公司档位/座席/已解锁功能。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.billing.catalog import (
    PLAN_CATALOG,
    Plan,
    effective_features,
    effective_seat_limit,
)
from app.db import get_db
from app.deps import get_current_user
from app.models.company import Company
from app.models.user import User, UserStatus
from app.schemas.billing import PlanCatalogEntry, SubscriptionRead

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

_CATALOG_VIEW = [
    PlanCatalogEntry(
        plan=plan.value,
        seat_limit=spec.seat_limit,
        features=sorted(f.value for f in spec.features),
    )
    for plan, spec in PLAN_CATALOG.items()
]


@router.get("/subscription", response_model=SubscriptionRead)
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    company = db.get(Company, current_user.company_id)
    plan = company.plan if company else Plan.free.value
    status_ = company.subscription_status if company else "active"
    seat_used = db.execute(
        select(func.count())
        .select_from(User)
        .where(User.company_id == current_user.company_id, User.status == UserStatus.active)
    ).scalar_one()
    return SubscriptionRead(
        plan=plan,
        subscription_status=status_,
        seat_used=seat_used,
        seat_limit=effective_seat_limit(plan, status_),
        features=sorted(f.value for f in effective_features(plan, status_)),
        catalog=_CATALOG_VIEW,
    )
```

- [ ] **Step 5: 注册 router** —— `backend/app/main.py` 加 `billing` import + `app.include_router(billing.router)`。

- [ ] **Step 6: 跑绿** `.venv/bin/python -m pytest tests/test_billing_subscription_api.py -v` → PASS。门禁同上。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/billing.py backend/app/routers/billing.py backend/app/main.py backend/tests/test_billing_subscription_api.py
git commit -m "feat(p6): GET /billing/subscription 自查端点（档位/座席/功能/catalog）"
```

---

## Task 7: 座席上限校验（invite 路径）

**Files:**
- Modify: `backend/app/services/invitation_service.py`
- Test: `backend/tests/test_seat_limit.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_seat_limit.py`

```python
"""座席上限：满员拒新邀请(402)；降档超员保留存量、仅拦新增。"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _invite(client, t, email):
    return client.post("/api/v1/users/invite", headers=_h(t), json={"email": email})


def test_free_seat_limit_blocks_third_invite(client):
    # free 上限 3；注册占 1 席，可再邀 2 个，第 3 个被拒
    t = _admin(client)
    assert _invite(client, t, "u1@acme.com").status_code in (200, 201)
    assert _invite(client, t, "u2@acme.com").status_code in (200, 201)
    r = _invite(client, t, "u3@acme.com")
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "SEAT_LIMIT_REACHED"


def test_pro_allows_more_seats(client, db):
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"  # 上限 15
    db.commit()
    for i in range(5):
        assert _invite(client, t, f"u{i}@acme.com").status_code in (200, 201)


def test_downgrade_keeps_existing_blocks_new(client, db):
    # pro 下邀满 5 人，再降回 free（上限3），存量保留但新邀被拒
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"
    db.commit()
    for i in range(4):
        assert _invite(client, t, f"u{i}@acme.com").status_code in (200, 201)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "free"
    db.commit()
    r = _invite(client, t, "extra@acme.com")
    assert r.status_code == 402, r.text
```

> 执行时先 `grep -n '@router.post' app/routers/users.py` 核实 invite 端点路径与成功状态码（200 或 201），把断言里的 `(200, 201)` 收敛为实际值。

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_seat_limit.py -v` → FAIL（当前无座席校验，全部成功）。

- [ ] **Step 3: 加座席校验** —— `backend/app/services/invitation_service.py`：

  import 区加：

```python
from sqlalchemy import func

from app.billing.catalog import effective_seat_limit
from app.errors import payment_required
```

  在 `invite()` 函数体开头（`existing = ...` 重复邮箱检查**之后**，`if role_id is not None:` **之前**）插入：

```python
    company = db.get(Company, company_id)
    limit = effective_seat_limit(
        company.plan if company else None,
        company.subscription_status if company else None,
    )
    if limit is not None:
        active_count = db.execute(
            select(func.count())
            .select_from(User)
            .where(User.company_id == company_id, User.status == UserStatus.active)
        ).scalar_one()
        if active_count >= limit:
            raise payment_required("SEAT_LIMIT_REACHED", "席位已达上限，请升级订阅以增加席位")
```

（注：`company` 变量名在 `invite()` 后段已用于发邮件——复用此处取的 `company`，删除后段重复的 `company = db.get(Company, company_id)` 一行以免重复查询；若类型检查无碍可保留，但 DRY 优先复用。）

- [ ] **Step 4: 跑绿** `.venv/bin/python -m pytest tests/test_seat_limit.py -v` → PASS。回归邀请既有测试 `.venv/bin/python -m pytest tests/test_users_api.py tests/test_invitation*.py -q` → PASS（既有邀请测试若一次邀多人超 free=3，需在注册后升 pro；按需补 `_unlock_pro(db)`）。门禁同上。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/invitation_service.py backend/tests/test_seat_limit.py
git commit -m "feat(p6): invite 座席上限校验（满员/降档超员→402，保留存量）"
```

---

## Task 8: 后端全量门禁收尾

- [ ] **Step 1: 全量回归** `cd backend && .venv/bin/python -m pytest -q` → 全绿（新增计入；既有不回归）。若有高级模块测试遗漏升 pro 导致 402，逐个补 `_unlock_pro(db)`。

- [ ] **Step 2: 门禁** `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app` → 全净。

- [ ] **Step 3: 迁移单 head** `.venv/bin/alembic heads` → 单 head `p6_commercialization_gating`。

- [ ] **Step 4: Commit（如有格式化改动）**

```bash
git add -A backend
git commit -m "chore(p6): 后端全量门禁收尾" || echo "无改动"
```

---

## Task 9: 前端 billing API 客户端 + 类型 + store

**Files:**
- Create: `frontend/src/api/billing.ts`
- Create: `frontend/src/store/billing.ts`
- Test: `frontend/tests/unit/store/billing.spec.ts`

- [ ] **Step 1: 写失败测试** `frontend/tests/unit/store/billing.spec.ts`

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({ getSubscription: vi.fn() }))
vi.mock('@/api/billing', () => api)

import { useBillingStore } from '@/store/billing'

const MOCK_FREE = {
  plan: 'free',
  subscription_status: 'active',
  seat_used: 1,
  seat_limit: 3,
  features: [],
  catalog: [
    { plan: 'free', seat_limit: 3, features: [] },
    { plan: 'pro', seat_limit: 15, features: ['meters', 'analytics'] },
    { plan: 'enterprise', seat_limit: null, features: ['meters', 'analytics'] },
  ],
}

describe('useBillingStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getSubscription.mockReset().mockResolvedValue(MOCK_FREE)
  })

  it('loadSubscription 拉取并存订阅', async () => {
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.subscription).toEqual(MOCK_FREE)
  })

  it('hasFeature 按 features 集合判定', async () => {
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.hasFeature('meters')).toBe(false) // free 未解锁
  })

  it('hasFeature 在 pro 下解锁', async () => {
    api.getSubscription.mockResolvedValue({ ...MOCK_FREE, plan: 'pro', features: ['meters', 'analytics'] })
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.hasFeature('meters')).toBe(true)
    expect(store.hasFeature('sop')).toBe(false)
  })

  it('未加载时 hasFeature 返回 false（安全默认）', () => {
    const store = useBillingStore()
    expect(store.hasFeature('meters')).toBe(false)
  })
})
```

- [ ] **Step 2: 跑红** `cd frontend && npx vitest run tests/unit/store/billing.spec.ts` → FAIL（模块不存在）。

- [ ] **Step 3: API 客户端** `frontend/src/api/billing.ts`

```typescript
import { http } from './http'

export interface PlanCatalogEntry {
  plan: string
  seat_limit: number | null
  features: string[]
}

export interface Subscription {
  plan: string
  subscription_status: string
  seat_used: number
  seat_limit: number | null
  features: string[]
  catalog: PlanCatalogEntry[]
}

export const getSubscription = () =>
  http.get<Subscription>('/billing/subscription').then((r) => r.data)
```

- [ ] **Step 4: store** `frontend/src/store/billing.ts`

```typescript
import { defineStore } from 'pinia'

import * as billingApi from '@/api/billing'
import type { Subscription } from '@/api/billing'

interface State {
  subscription: Subscription | null
  loading: boolean
}

export const useBillingStore = defineStore('billing', {
  state: (): State => ({ subscription: null, loading: false }),
  getters: {
    // feature 未加载时返回 false（安全默认：未知即锁）
    hasFeature(): (feature: string) => boolean {
      return (feature: string) => this.subscription?.features.includes(feature) ?? false
    },
    planName(): string {
      return this.subscription?.plan ?? 'free'
    },
  },
  actions: {
    async loadSubscription(): Promise<void> {
      this.loading = true
      try {
        this.subscription = await billingApi.getSubscription()
      } finally {
        this.loading = false
      }
    },
  },
})
```

- [ ] **Step 5: 跑绿** `npx vitest run tests/unit/store/billing.spec.ts` → PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/billing.ts frontend/src/store/billing.ts frontend/tests/unit/store/billing.spec.ts
git commit -m "feat(p6): 前端 billing api 客户端 + Pinia store（hasFeature 门控）"
```

---

## Task 10: 前端 订阅设置页 + 套餐对比页 + 路由 + 启动加载 + i18n

**Files:**
- Create: `frontend/src/views/billing/SettingsView.vue`
- Create: `frontend/src/views/billing/PlansView.vue`
- Modify: `frontend/src/router/index.ts`（加两路由）
- Modify: `frontend/src/store/auth.ts` 或启动钩子（登录后加载订阅）
- Modify: `frontend/src/i18n/locales/zh-CN.ts`（加 billing 文案）
- Test: `frontend/tests/unit/views/billingSettings.spec.ts`

- [ ] **Step 1: 写失败测试** `frontend/tests/unit/views/billingSettings.spec.ts`

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'

const api = vi.hoisted(() => ({ getSubscription: vi.fn() }))
vi.mock('@/api/billing', () => api)

import SettingsView from '@/views/billing/SettingsView.vue'

const SUB = {
  plan: 'pro',
  subscription_status: 'active',
  seat_used: 4,
  seat_limit: 15,
  features: ['meters', 'analytics'],
  catalog: [],
}

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getSubscription.mockReset().mockResolvedValue(SUB)
  })

  it('展示当前档位与座席用量', async () => {
    const wrapper = mount(SettingsView, {
      global: { stubs: { 'el-progress': true, 'el-tag': true, 'el-card': true } },
    })
    await vi.waitFor(() => expect(api.getSubscription).toHaveBeenCalled())
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('pro')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('15')
  })
})
```

- [ ] **Step 2: 跑红** `npx vitest run tests/unit/views/billingSettings.spec.ts` → FAIL（组件不存在）。

- [ ] **Step 3: SettingsView** `frontend/src/views/billing/SettingsView.vue`（参照 `src/views/platform/CompanySettingsView.vue` 布局）

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useBillingStore } from '@/store/billing'

const billing = useBillingStore()

onMounted(() => billing.loadSubscription())

const sub = computed(() => billing.subscription)
const seatText = computed(() => {
  const s = sub.value
  if (!s) return ''
  return s.seat_limit === null ? `${s.seat_used} / 无限` : `${s.seat_used} / ${s.seat_limit}`
})
</script>

<template>
  <div class="billing-settings" v-if="sub">
    <h2>订阅设置</h2>
    <el-card>
      <p>当前套餐：<el-tag>{{ sub.plan }}</el-tag></p>
      <p>订阅状态：{{ sub.subscription_status }}</p>
      <p>席位用量：{{ seatText }}</p>
      <el-progress
        v-if="sub.seat_limit !== null"
        :percentage="Math.min(100, Math.round((sub.seat_used / sub.seat_limit) * 100))"
      />
      <p>已解锁功能：{{ sub.features.join('、') || '无' }}</p>
      <router-link to="/billing/plans">查看套餐对比</router-link>
    </el-card>
  </div>
</template>
```

- [ ] **Step 4: PlansView** `frontend/src/views/billing/PlansView.vue`

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useBillingStore } from '@/store/billing'

const billing = useBillingStore()

onMounted(() => {
  if (!billing.subscription) billing.loadSubscription()
})

const catalog = computed(() => billing.subscription?.catalog ?? [])
const currentPlan = computed(() => billing.planName)

function seatLabel(limit: number | null): string {
  return limit === null ? '无限席位' : `${limit} 个席位`
}
</script>

<template>
  <div class="plans-view">
    <h2>订阅套餐</h2>
    <div class="plan-grid">
      <el-card v-for="entry in catalog" :key="entry.plan" :class="{ current: entry.plan === currentPlan }">
        <h3>{{ entry.plan }}</h3>
        <p>{{ seatLabel(entry.seat_limit) }}</p>
        <ul>
          <li v-for="f in entry.features" :key="f">{{ f }}</li>
        </ul>
        <el-tag v-if="entry.plan === currentPlan" type="success">当前套餐</el-tag>
        <el-button v-else disabled>请联系管理员升级</el-button>
      </el-card>
    </div>
  </div>
</template>
```

- [ ] **Step 5: 路由** —— `frontend/src/router/index.ts` routes 数组加（参照既有 `requiresAuth` meta 风格）：

```typescript
{
  path: '/billing/settings',
  name: 'billing-settings',
  component: () => import('@/views/billing/SettingsView.vue'),
  meta: { title: '订阅设置', requiresAuth: true },
},
{
  path: '/billing/plans',
  name: 'billing-plans',
  component: () => import('@/views/billing/PlansView.vue'),
  meta: { title: '订阅套餐', requiresAuth: true },
},
```

- [ ] **Step 6: 登录后加载订阅** —— `frontend/src/store/auth.ts`：在 `loadMe()` 成功后（或 `bootstrap()` 末尾）触发 billing 加载。最小侵入：在 `loadMe` 末尾加：

```typescript
    // 加载公司订阅供 feature 门控（失败不阻塞登录）
    try {
      const { useBillingStore } = await import('./billing')
      await useBillingStore().loadSubscription()
    } catch {
      // 订阅加载失败不阻断主流程
    }
```

（用动态 import 避免 store 间循环依赖。）

- [ ] **Step 7: i18n 文案** —— `frontend/src/i18n/locales/zh-CN.ts` 顶层对象加：

```typescript
  billing: {
    settings: '订阅设置',
    plans: '订阅套餐',
    currentPlan: '当前套餐',
    seatUsage: '席位用量',
    unlockedFeatures: '已解锁功能',
    upgradeHint: '请联系管理员升级',
    locked: '需升级订阅解锁',
  },
```

- [ ] **Step 8: 跑绿** `npx vitest run tests/unit/views/billingSettings.spec.ts` → PASS。门禁 `npx vue-tsc --noEmit && npx eslint src && npx prettier --check src`（按项目实际脚本，先 `cat package.json | grep -A10 scripts` 核实命令名）。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/billing frontend/src/router/index.ts frontend/src/store/auth.ts frontend/src/i18n/locales/zh-CN.ts frontend/tests/unit/views/billingSettings.spec.ts
git commit -m "feat(p6): 订阅设置页 + 套餐对比页 + 路由 + 登录加载订阅 + 文案"
```

---

## Task 11: 前端导航锁标门控

**Files:**
- Modify: `frontend/src/components/AppSidebar.vue`
- Test: `frontend/tests/unit/components/appSidebarLock.spec.ts`

- [ ] **Step 1: 写失败测试** `frontend/tests/unit/components/appSidebarLock.spec.ts`

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBillingStore } from '@/store/billing'

// 验证「按 feature 判断菜单项是否锁定」的纯逻辑。
// AppSidebar 用 billing.hasFeature 决定 locked；此处测该判定接线。
describe('sidebar feature lock', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('free 档下高级模块判为 locked', () => {
    const billing = useBillingStore()
    billing.subscription = {
      plan: 'free', subscription_status: 'active', seat_used: 1, seat_limit: 3,
      features: [], catalog: [],
    }
    expect(billing.hasFeature('meters')).toBe(false)
    expect(billing.hasFeature('analytics')).toBe(false)
  })

  it('pro 档下高级模块解锁', () => {
    const billing = useBillingStore()
    billing.subscription = {
      plan: 'pro', subscription_status: 'active', seat_used: 1, seat_limit: 15,
      features: ['meters', 'analytics', 'preventive_maintenance', 'purchasing', 'sop'], catalog: [],
    }
    expect(billing.hasFeature('meters')).toBe(true)
    expect(billing.hasFeature('sop')).toBe(true)
  })
})
```

- [ ] **Step 2: 跑红/跑绿确认 store 逻辑** `npx vitest run tests/unit/components/appSidebarLock.spec.ts`（store getter 已存在，应 PASS；此测试锁定门控契约，防回归）。

- [ ] **Step 3: AppSidebar 接线锁标** —— `frontend/src/components/AppSidebar.vue`：

  (a) script 区引入 billing store：`import { useBillingStore } from '@/store/billing'` + `const billing = useBillingStore()`。

  (b) 给高级模块菜单项的 `NavItem` 增加 `feature?: string` 字段，对应映射：计量→`meters`、预防性维护→`preventive_maintenance`、采购（采购单/供应商等）→`purchasing`、分析→`analytics`、SOP（程序库/批量解析等）→`sop`。

  (c) 计算每项 `locked = it.feature ? !billing.hasFeature(it.feature) : false`。

  (d) 模板中（参照既有 `soon` 标签处理，AppSidebar.vue 内 `<el-menu-item>` 渲染处）：locked 项加锁标且点击跳套餐页而非进入模块。最小实现：

```vue
<el-menu-item
  v-for="it in g.items"
  :key="it.path"
  :index="it.path"
  :disabled="it.soon"
  @click="it.locked ? goPlans() : undefined"
>
  <span>{{ it.label }}</span>
  <el-icon v-if="it.locked" class="lock-icon"><Lock /></el-icon>
</el-menu-item>
```

  其中 `goPlans` = `() => router.push('/billing/plans')`，`Lock` 从 `@element-plus/icons-vue` import。locked 项不导航到原模块（避免进去后满屏 402）。

> 执行时先读 `AppSidebar.vue` 全文，确认 NavItem 类型定义、菜单项渲染结构与既有 `soon`/`requiredPermission` 处理，按其真实结构接线（上面是示意，须贴合实际模板）。

- [ ] **Step 4: 跑绿 + 门禁** `npx vitest run` → 全绿。`npx vue-tsc --noEmit && npx eslint src` → 净。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppSidebar.vue frontend/tests/unit/components/appSidebarLock.spec.ts
git commit -m "feat(p6): 侧边栏高级模块按 feature 显示锁标并引导套餐页"
```

---

## Task 12: 前端全量门禁收尾

- [ ] **Step 1: 全量前端测试** `cd frontend && npx vitest run` → 全绿。

- [ ] **Step 2: 类型/lint/格式** `npx vue-tsc --noEmit && npx eslint src && npx prettier --check src`（命令以 package.json scripts 为准）→ 全净。

- [ ] **Step 3: Commit（如有）**

```bash
git add -A frontend
git commit -m "chore(p6): 前端全量门禁收尾" || echo "无改动"
```

---

## Self-Review（已执行，记录结论）

**Spec 覆盖核对**：

- §2 feature gate 正交叠加 → Task 3（require_feature）+ Task 4（全 router 挂闸）；super_admin 不绕 → Task 3 test ✓
- §3 三档 catalog + 座席 + 5 feature → Task 1 ✓
- §4 订阅状态机 + 失效降级 → Task 1（effective_* 纯函数）+ Task 3 test（past_due→402）✓
- §5 数据模型/迁移 → Task 2 ✓
- §6 组件：catalog/require_feature/座席校验/billing 端点/platform 端点/router 挂闸 → Task 1/3/7/6/5/4 ✓
- §7 前端：billing store/订阅页/套餐页/导航锁标 → Task 9/10/11 ✓
- §8 测试策略各项 → 分散在各 Task test ✓
- §10 风险：JWT 实时查库（require_feature 每请求 db.get Company）✓、前端非安全边界（后端 402 兜底）✓、座席仅计 active → Task 6/7 用 UserStatus.active ✓

**类型一致性**：Feature 枚举值在后端 catalog、router 挂闸、前端 hasFeature、SidebarNav.feature 全用同一组字符串（preventive_maintenance/meters/purchasing/analytics/sop）；Subscription 字段名后端 SubscriptionRead 与前端 interface 一致（plan/subscription_status/seat_used/seat_limit/features/catalog）。

**已知执行注意**：挂闸会让既有高级模块测试（用 free 公司直访）变 402，需在对应测试注册后升 pro/enterprise——Task 3/4/7 已标注修复方式（共享 `_unlock_pro`/`unlock_all_features` helper）。执行者每挂一个 router 即跑该模块既有测试，立刻修复，避免堆积。
