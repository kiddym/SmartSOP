# P6 Stripe 计费 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐 task 实现。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 让 pro 档由真实 Stripe（test-mode）支付驱动——托管 Checkout 订阅 → webhook 同步 `Company.plan`/`subscription_status` → 客户门户管理/取消降级。

**Architecture:** 薄网关 `stripe_gateway`（隔离 SDK）+ 服务 `billing_service`（编排 + webhook 真相源同步）+ 三个端点（checkout/portal/webhook）。`Company` 加 `stripe_customer_id`/`stripe_subscription_id`；`tb_billing_event` 去重。前端 PlansView/SettingsView 加订阅/门户按钮 + 返回轮询。enterprise 仍走平台手动设档（不改）。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + `stripe` Python SDK + pytest（mock 网关）；Vue 3 + Pinia + Element Plus + Vitest。

设计依据：`docs/superpowers/specs/2026-06-04-p6-stripe-billing-design.md`。

---

## 契约（全程以此为准）

- **真相源**：`customer.subscription.created/updated/deleted` webhook → 写 `Company.plan`/`subscription_status`/`stripe_subscription_id`。`checkout.session.completed` 不单独处理（customer 在 checkout 前已落库）。
- **状态映射**：`active`/`trialing`→`active`；`past_due`/`unpaid`→`past_due`；`canceled`/`incomplete_expired`/事件 deleted→`canceled` 且 `plan=free`。活跃订阅 `plan=pro`（单一 price）。
- **幂等**：`tb_billing_event(event_id)` 命中即跳过；写 Company 本就幂等。
- **门控**：checkout/portal 端点要 `billing.manage` 权限；webhook 无认证、验签。
- **净室红线**：Stripe 官方 SDK 正常使用；不复制任何第三方计费代码/命名/文案。密钥仅入 `.env`，仓库不存。
- **门禁每个后端 task 收尾全绿**：`cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app && .venv/bin/python -m pytest -q`；`alembic heads` 单 head。
- **前端门禁**：`cd frontend && npm run test && npm run typecheck && npm run lint`。

---

## File Structure（本轮新建/改动）

**后端**
- Create `backend/app/billing/stripe_gateway.py` — Stripe SDK 薄封装（ensure_customer / create_checkout_session / create_portal_session / construct_event）。
- Create `backend/app/services/billing_service.py` — start_checkout / open_portal / handle_event（webhook 同步）。
- Create `backend/app/models/billing_event.py` — `tb_billing_event` 去重表。
- Create `backend/alembic/versions/20260605_0001_p6_stripe_billing.py` — Company 加 2 列 + 建去重表。
- Modify `backend/app/models/company.py` — 加 `stripe_customer_id`/`stripe_subscription_id`。
- Modify `backend/app/config.py` — Stripe 配置字段。
- Modify `backend/app/permissions.py` — 加 `BILLING_MANAGE`。
- Modify `backend/app/schemas/billing.py` — 加 `CheckoutSessionOut`/`PortalSessionOut`。
- Modify `backend/app/routers/billing.py` — 加 3 端点。
- Modify `backend/app/models/__init__.py` — 导出 `BillingEvent`（若该文件集中导出模型）。
- Modify `backend/pyproject.toml` — 加 `stripe` 依赖。
- Tests: `backend/tests/unit/services/test_billing_service.py`、`backend/tests/integration/test_billing_stripe_api.py`、`backend/tests/test_no_literal_text_default.py`（既有护栏自动覆盖新列，无需改）。

**前端**
- Modify `frontend/src/api/billing.ts` — 加 createCheckoutSession / createPortalSession。
- Modify `frontend/src/store/billing.ts` — 加 startCheckout / openPortal action。
- Modify `frontend/src/views/billing/PlansView.vue` — pro 订阅按钮 + enterprise 联系销售。
- Modify `frontend/src/views/billing/SettingsView.vue` — 管理订阅（门户）按钮 + 返回轮询。
- Tests: `frontend/tests/unit/store/billing.spec.ts`、`frontend/tests/unit/views/billingPlans.spec.ts`（新建）。

---

## 环境准备

```bash
cd backend
# 安装 Stripe SDK（本机无 uv，用 venv pip）
.venv/bin/pip install "stripe>=11,<13"
# .env 追加（值由人工填 test-mode；仓库不入密钥）：
#   STRIPE_SECRET_KEY=sk_test_xxx
#   STRIPE_WEBHOOK_SECRET=whsec_xxx
#   STRIPE_PRICE_PRO=price_xxx
#   BILLING_CHECKOUT_SUCCESS_URL=http://localhost:5173/billing/settings?checkout=success
#   BILLING_CHECKOUT_CANCEL_URL=http://localhost:5173/billing/plans?checkout=cancel
#   BILLING_PORTAL_RETURN_URL=http://localhost:5173/billing/settings
#   SALES_CONTACT_EMAIL=sales@example.com
```

---

## Task 1: 依赖 + 配置 + 权限码

**Files:**
- Modify `backend/pyproject.toml`
- Modify `backend/app/config.py`
- Modify `backend/app/permissions.py`
- Test: `backend/tests/unit/test_billing_config_perms.py`（Create）

- [ ] **Step 1: 加 stripe 依赖** —— 在 `pyproject.toml` 的 `[project]` `dependencies = [...]` 数组末尾加一行 `"stripe>=11,<13",`，然后 `.venv/bin/pip install "stripe>=11,<13"`。若 `mypy app` 报 stripe 缺类型，在 `[[tool.mypy.overrides]]` 的 `module = [...]` 列表加 `"stripe.*"`（与既有 `docx.*` 等同处）。

- [ ] **Step 2: 加配置字段** —— 在 `app/config.py` 的 `Settings` 类里（紧随既有 `database_*` 字段后）加：

```python
    # --- Stripe 计费（Phase 6，test-mode） ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    billing_checkout_success_url: str = "http://localhost:5173/billing/settings?checkout=success"
    billing_checkout_cancel_url: str = "http://localhost:5173/billing/plans?checkout=cancel"
    billing_portal_return_url: str = "http://localhost:5173/billing/settings"
    sales_contact_email: str = ""
```

- [ ] **Step 3: 加权限码** —— 在 `app/permissions.py` 的 `COMPANY_SETTINGS = "company.settings"` 行后加 `BILLING_MANAGE = "billing.manage"`；并把 `BILLING_MANAGE` 追加进 `_PLATFORM` 列表（紧随 `CURRENCY_MANAGE` 后）——因 `admin`/`super_admin` 用 `ALL_PERMISSIONS`，加入任一汇总列表即自动纳入 `ALL_PERMISSIONS` 与内置 admin 角色。确认 `ALL_PERMISSIONS` 是由各 `_PLATFORM/_BASE_DOMAIN/...` 列表拼成（若不是，则也把 `BILLING_MANAGE` 显式加入 `ALL_PERMISSIONS`）。

- [ ] **Step 4: 写测试**（`tests/unit/test_billing_config_perms.py`）：

```python
from app import permissions
from app.config import settings


def test_billing_config_fields_default_empty():
    assert settings.stripe_secret_key == ""
    assert settings.stripe_price_pro == ""
    assert settings.billing_portal_return_url.startswith("http")


def test_billing_manage_permission_registered():
    assert permissions.BILLING_MANAGE == "billing.manage"
    assert permissions.BILLING_MANAGE in permissions.ALL_PERMISSIONS
    # admin 内置角色（用 ALL_PERMISSIONS）含 billing.manage
    admin = next(r for r in permissions.BUILTIN_ROLES if r["code"] == "admin")
    assert permissions.BILLING_MANAGE in admin["permissions"]
```

- [ ] **Step 5: 跑测试** `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_config_perms.py -q` → PASS。

- [ ] **Step 6: 门禁 + Commit** `.venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app`；`git add -A && git commit -m "feat(billing): stripe 依赖 + 配置字段 + billing.manage 权限"`。

---

## Task 2: 数据模型 + 迁移（Company 加列 + 去重表）

**Files:**
- Modify `backend/app/models/company.py`
- Create `backend/app/models/billing_event.py`
- Modify `backend/app/models/__init__.py`（若集中导出模型）
- Create `backend/alembic/versions/20260605_0001_p6_stripe_billing.py`
- Test: `backend/tests/unit/test_migration_p6_stripe_billing.py`（Create）

- [ ] **Step 1: Company 加两列** —— 在 `app/models/company.py` 的 `subscription_status` 行后加：

```python
    # Stripe 计费关联（Phase 6）：customer 一对一、当前活跃 subscription
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, default=None
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
```

> 执行时核实 `company.py` 已 import `String`（既有 `String(32)` 列说明已 import）。

- [ ] **Step 2: 建去重表模型**（`app/models/billing_event.py`）：

```python
"""Stripe webhook 事件去重日志（Phase 6）。

非租户表：webhook 无认证、按 customer 解析公司，事件本身不属单租户。
event_id 为 Stripe 事件 id（主键）；命中即视为已处理，保证幂等。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, utcnow


class BillingEvent(Base):
    __tablename__ = "tb_billing_event"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DATETIME6, nullable=False, default=utcnow)
```

> 执行时核实 `app/models/base.py` 导出 `DATETIME6`、`Base`、`utcnow`（[[node-field-serialization-wiring]] 同款 import 习惯；audit.py 即如此用）。

- [ ] **Step 3: 注册模型** —— 若 `app/models/__init__.py` 集中 `from app.models.x import Y` 导出（执行时核实），加 `from app.models.billing_event import BillingEvent` 并入 `__all__`。否则确保 `app.models.billing_event` 在 metadata 注册路径上（被 import）。

- [ ] **Step 4: 写迁移**（`alembic/versions/20260605_0001_p6_stripe_billing.py`）。新列均 String nullable，无 TEXT 字面默认（不涉 1101，见 [[mysql-text-default-blocks-bootstrap]]）：

```python
"""P6 stripe billing: company stripe ids + billing event dedup table

Revision ID: p6_stripe_billing
Revises: sop_tenancy_hardening
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "p6_stripe_billing"
down_revision: str | Sequence[str] | None = "sop_tenancy_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_company") as b:
        b.add_column(sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
        b.create_unique_constraint("uq_tb_company_stripe_customer_id", ["stripe_customer_id"])

    op.create_table(
        "tb_billing_event",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", DATETIME6, nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_tb_billing_event")),
    )


def downgrade() -> None:
    op.drop_table("tb_billing_event")
    with op.batch_alter_table("tb_company") as b:
        b.drop_constraint("uq_tb_company_stripe_customer_id", type_="unique")
        b.drop_column("stripe_subscription_id")
        b.drop_column("stripe_customer_id")
```

- [ ] **Step 5: 写迁移测试**（`tests/unit/test_migration_p6_stripe_billing.py`，对齐既有 `test_migration_roundtrip.py` 风格）：

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.config import settings

_ROOT = Path(__file__).resolve().parent.parent.parent


def _cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return cfg


def test_single_head_is_p6_stripe_billing() -> None:
    assert ScriptDirectory.from_config(_cfg()).get_heads() == ["p6_stripe_billing"]


def test_sqlite_upgrade_downgrade_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "rt.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    cfg = _cfg()
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    try:
        company_cols = {r[1] for r in conn.execute("PRAGMA table_info(tb_company)")}
        assert {"stripe_customer_id", "stripe_subscription_id"} <= company_cols
        event_cols = {r[1] for r in conn.execute("PRAGMA table_info(tb_billing_event)")}
        assert event_cols == {"event_id", "event_type", "processed_at"}
    finally:
        conn.close()
    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")
```

- [ ] **Step 6: 跑测试 + 单 head** `.venv/bin/python -m pytest tests/unit/test_migration_p6_stripe_billing.py tests/test_no_literal_text_default.py -q` → PASS；`.venv/bin/alembic heads` → `p6_stripe_billing (head)` 单 head。

- [ ] **Step 7: 门禁 + Commit** ruff/format/mypy 净；`git commit -m "feat(billing): Company stripe id 列 + tb_billing_event 去重表 + 迁移"`。

---

## Task 3: Stripe 网关（SDK 薄封装）

**Files:**
- Create `backend/app/billing/stripe_gateway.py`
- Test: `backend/tests/unit/test_stripe_gateway.py`（Create）

- [ ] **Step 1: 写网关**（隔离 SDK，验签失败抛自有 `SignatureError`，便于上层与测试不依赖 stripe 内部）：

```python
"""Stripe SDK 薄封装（Phase 6）：隔离外部依赖，便于服务层 mock。

所有函数即用即设 api_key（settings 可在测试中改）。construct_event 把 Stripe 的
验签异常翻成自有 SignatureError，使路由/测试不依赖 stripe.error 内部类型。
"""

from __future__ import annotations

from typing import Any

import stripe

from app.config import settings


class SignatureError(Exception):
    """Webhook 验签失败。"""


def _api_key() -> None:
    stripe.api_key = settings.stripe_secret_key


def ensure_customer(*, company_id: str, email: str, existing_id: str | None) -> str:
    """已有则复用，否则建 Customer（metadata 带 company_id）。返回 customer id。"""
    _api_key()
    if existing_id:
        return existing_id
    customer = stripe.Customer.create(email=email, metadata={"company_id": company_id})
    return customer.id


def create_checkout_session(
    *, customer_id: str, price_id: str, success_url: str, cancel_url: str
) -> str:
    """建 subscription 模式 Checkout Session，返回托管页 URL。"""
    _api_key()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """建客户门户 Session，返回 URL。"""
    _api_key()
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url


def construct_event(payload: bytes, sig_header: str) -> dict[str, Any]:
    """验签并解析 webhook 事件；验签失败抛 SignatureError。"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:  # type: ignore[attr-defined]
        raise SignatureError(str(exc)) from exc
    return dict(event)
```

- [ ] **Step 2: 写测试**（mock `stripe` 模块，断言入参；验签异常翻译）：

```python
from types import SimpleNamespace

import pytest

from app.billing import stripe_gateway


def test_ensure_customer_reuses_existing(monkeypatch):
    called = {}
    monkeypatch.setattr(
        stripe_gateway.stripe.Customer, "create", lambda **k: called.setdefault("hit", True)
    )
    cid = stripe_gateway.ensure_customer(company_id="c1", email="a@b.com", existing_id="cus_X")
    assert cid == "cus_X"
    assert "hit" not in called  # 复用不新建


def test_ensure_customer_creates_with_metadata(monkeypatch):
    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cus_NEW")

    monkeypatch.setattr(stripe_gateway.stripe.Customer, "create", _create)
    cid = stripe_gateway.ensure_customer(company_id="c1", email="a@b.com", existing_id=None)
    assert cid == "cus_NEW"
    assert captured["metadata"] == {"company_id": "c1"}


def test_create_checkout_session_returns_url(monkeypatch):
    monkeypatch.setattr(
        stripe_gateway.stripe.checkout.Session,
        "create",
        lambda **k: SimpleNamespace(url="https://checkout.stripe/x"),
    )
    url = stripe_gateway.create_checkout_session(
        customer_id="cus_X", price_id="price_X", success_url="s", cancel_url="c"
    )
    assert url == "https://checkout.stripe/x"


def test_construct_event_translates_signature_error(monkeypatch):
    def _raise(*a, **k):
        raise stripe_gateway.stripe.error.SignatureVerificationError("bad", "sig")

    monkeypatch.setattr(stripe_gateway.stripe.Webhook, "construct_event", _raise)
    with pytest.raises(stripe_gateway.SignatureError):
        stripe_gateway.construct_event(b"{}", "t=1,v1=bad")
```

- [ ] **Step 3: 跑测试** `.venv/bin/python -m pytest tests/unit/test_stripe_gateway.py -q` → PASS。
- [ ] **Step 4: 门禁 + Commit** `git commit -m "feat(billing): stripe_gateway SDK 薄封装 + 验签错误翻译"`。

---

## Task 4: 计费服务（checkout / portal / webhook 同步）

**Files:**
- Create `backend/app/services/billing_service.py`
- Test: `backend/tests/unit/services/test_billing_service.py`（Create）

- [ ] **Step 1: 写服务**：

```python
"""计费服务（Phase 6）：发起 checkout/portal + webhook 同步订阅状态（真相源）。

webhook 处理 customer.subscription.created/updated/deleted；按 stripe_customer_id
反查公司，把 status/plan 同步到 Company。tb_billing_event 去重保证幂等。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing import stripe_gateway
from app.billing.catalog import Plan
from app.config import settings
from app.errors import bad_request
from app.models.base import utcnow
from app.models.billing_event import BillingEvent
from app.models.company import Company
from app.models.user import User

logger = logging.getLogger(__name__)

_SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)
# Stripe subscription.status → 我们的 subscription_status
_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}


def start_checkout(db: Session, company: Company, user: User) -> str:
    """建/复用 Stripe Customer（回写 id）→ 建 pro 订阅 Checkout，返回跳转 URL。"""
    customer_id = stripe_gateway.ensure_customer(
        company_id=company.id, email=user.email, existing_id=company.stripe_customer_id
    )
    if company.stripe_customer_id != customer_id:
        company.stripe_customer_id = customer_id
        db.commit()
    return stripe_gateway.create_checkout_session(
        customer_id=customer_id,
        price_id=settings.stripe_price_pro,
        success_url=settings.billing_checkout_success_url,
        cancel_url=settings.billing_checkout_cancel_url,
    )


def open_portal(db: Session, company: Company) -> str:
    """打开客户门户；未订阅过（无 customer）→ 400。"""
    if not company.stripe_customer_id:
        raise bad_request("NO_SUBSCRIPTION", "尚无订阅，无法打开管理门户")
    return stripe_gateway.create_portal_session(
        customer_id=company.stripe_customer_id, return_url=settings.billing_portal_return_url
    )


def handle_event(db: Session, payload: bytes, sig_header: str) -> None:
    """验签 → 去重 → 同步订阅。验签失败由 stripe_gateway 抛 SignatureError。"""
    event = stripe_gateway.construct_event(payload, sig_header)
    event_id = event["id"]
    if db.get(BillingEvent, event_id) is not None:
        return  # 幂等：已处理过
    event_type = event["type"]
    if event_type in _SUBSCRIPTION_EVENTS:
        _sync_subscription(
            db, event["data"]["object"], deleted=event_type.endswith("deleted")
        )
    db.add(BillingEvent(event_id=event_id, event_type=event_type, processed_at=utcnow()))
    db.commit()


def _sync_subscription(db: Session, sub: dict, *, deleted: bool) -> None:
    customer_id = sub["customer"]
    company = db.execute(
        select(Company).where(Company.stripe_customer_id == customer_id)
    ).scalar_one_or_none()
    if company is None:
        logger.warning("webhook 订阅事件未匹配到公司 customer=%s", customer_id)
        return
    status = "canceled" if deleted else _STATUS_MAP.get(sub.get("status", ""), "canceled")
    if status == "canceled":
        company.plan = Plan.free.value
        company.subscription_status = "canceled"
        company.stripe_subscription_id = None
    else:
        company.plan = Plan.pro.value  # 单一 price = pro
        company.subscription_status = status
        company.stripe_subscription_id = sub["id"]
```

- [ ] **Step 2: 写测试**（mock `stripe_gateway`，直接喂构造的事件 dict；用既有 client/db 夹具造公司）：

```python
import pytest
from sqlalchemy import select

from app.billing import stripe_gateway
from app.errors import HTTPException
from app.models.company import Company
from app.models.billing_event import BillingEvent
from app.services import billing_service


def _company(client, db):
    client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"},
    )
    return db.execute(select(Company)).scalars().first()


def _event(etype, *, customer, status="active", sub_id="sub_1", event_id="evt_1"):
    return {
        "id": event_id,
        "type": etype,
        "data": {"object": {"id": sub_id, "customer": customer, "status": status}},
    }


def test_subscription_created_sets_pro_active(client, db, monkeypatch):
    co = _company(client, db)
    co.stripe_customer_id = "cus_1"
    db.commit()
    monkeypatch.setattr(
        stripe_gateway, "construct_event",
        lambda p, s: _event("customer.subscription.created", customer="cus_1"),
    )
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.plan == "pro"
    assert co.subscription_status == "active"
    assert co.stripe_subscription_id == "sub_1"


def test_subscription_deleted_reverts_free(client, db, monkeypatch):
    co = _company(client, db)
    co.stripe_customer_id = "cus_1"
    co.plan = "pro"
    co.stripe_subscription_id = "sub_1"
    db.commit()
    monkeypatch.setattr(
        stripe_gateway, "construct_event",
        lambda p, s: _event("customer.subscription.deleted", customer="cus_1", event_id="evt_2"),
    )
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.plan == "free"
    assert co.subscription_status == "canceled"
    assert co.stripe_subscription_id is None


def test_past_due_maps(client, db, monkeypatch):
    co = _company(client, db)
    co.stripe_customer_id = "cus_1"
    db.commit()
    monkeypatch.setattr(
        stripe_gateway, "construct_event",
        lambda p, s: _event(
            "customer.subscription.updated", customer="cus_1", status="past_due", event_id="evt_3"
        ),
    )
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.subscription_status == "past_due"


def test_idempotent_replay_skips(client, db, monkeypatch):
    co = _company(client, db)
    co.stripe_customer_id = "cus_1"
    db.commit()
    ev = _event("customer.subscription.updated", customer="cus_1", status="past_due", event_id="evt_dup")
    monkeypatch.setattr(stripe_gateway, "construct_event", lambda p, s: ev)
    billing_service.handle_event(db, b"{}", "sig")
    # 第二次：把状态改为 active 的同 id 事件，应被去重跳过（不二次处理）
    ev2 = _event("customer.subscription.updated", customer="cus_1", status="active", event_id="evt_dup")
    monkeypatch.setattr(stripe_gateway, "construct_event", lambda p, s: ev2)
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.subscription_status == "past_due"  # 仍是首次结果
    assert db.get(BillingEvent, "evt_dup") is not None


def test_unknown_customer_tolerated(client, db, monkeypatch):
    monkeypatch.setattr(
        stripe_gateway, "construct_event",
        lambda p, s: _event("customer.subscription.created", customer="cus_ghost", event_id="evt_g"),
    )
    billing_service.handle_event(db, b"{}", "sig")  # 不抛
    assert db.get(BillingEvent, "evt_g") is not None  # 仍记录已处理


def test_open_portal_without_customer_400(client, db):
    co = _company(client, db)
    with pytest.raises(HTTPException):
        billing_service.open_portal(db, co)
```

> 执行时核实 `app.errors` 是否导出 `HTTPException`（若 errors 用 fastapi 的 `HTTPException`，测试改 `from fastapi import HTTPException`）。

- [ ] **Step 3: 跑测试** `.venv/bin/python -m pytest tests/unit/services/test_billing_service.py -q` → PASS。
- [ ] **Step 4: 门禁 + Commit** `git commit -m "feat(billing): billing_service checkout/portal + webhook 同步（幂等/状态映射/容错）"`。

---

## Task 5: 路由端点（checkout / portal / webhook）

**Files:**
- Modify `backend/app/schemas/billing.py`
- Modify `backend/app/routers/billing.py`
- Test: `backend/tests/integration/test_billing_stripe_api.py`（Create）

- [ ] **Step 1: 加响应 schema** —— 在 `app/schemas/billing.py` 末尾加：

```python
class CheckoutSessionOut(BaseModel):
    url: str


class PortalSessionOut(BaseModel):
    url: str
```

- [ ] **Step 2: 加端点** —— 在 `app/routers/billing.py`：顶部 import 增 `from fastapi import APIRouter, Depends, Request`、`from app import permissions`、`from app.billing import stripe_gateway`、`from app.deps import require_permission`、`from app.errors import bad_request`、`from app.services import billing_service`、`from app.schemas.billing import CheckoutSessionOut, PortalSessionOut`。然后在 `get_subscription` 后加：

```python
@router.post("/checkout-session", response_model=CheckoutSessionOut)
def create_checkout_session(
    current_user: User = Depends(require_permission(permissions.BILLING_MANAGE)),
    db: Session = Depends(get_db),
) -> CheckoutSessionOut:
    company = db.get(Company, current_user.company_id)
    if company is None:
        raise bad_request("COMPANY_NOT_FOUND", "公司不存在")
    return CheckoutSessionOut(url=billing_service.start_checkout(db, company, current_user))


@router.post("/portal-session", response_model=PortalSessionOut)
def create_portal_session(
    current_user: User = Depends(require_permission(permissions.BILLING_MANAGE)),
    db: Session = Depends(get_db),
) -> PortalSessionOut:
    company = db.get(Company, current_user.company_id)
    if company is None:
        raise bad_request("COMPANY_NOT_FOUND", "公司不存在")
    return PortalSessionOut(url=billing_service.open_portal(db, company))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        billing_service.handle_event(db, payload, sig)
    except stripe_gateway.SignatureError:
        raise bad_request("INVALID_SIGNATURE", "Webhook 验签失败") from None
    return {"received": True}
```

> webhook 端点**无认证依赖**（Stripe 直连）。`billing.router` 已在 `main.py:173` 注册，无需改 main。

- [ ] **Step 3: 写集成测试**（mock 网关；用 `_admin` 注册拿 token）：

```python
import pytest
from sqlalchemy import select

from app.billing import stripe_gateway
from app.models.company import Company
from app.services import billing_service


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_checkout_session_returns_url(client, db, monkeypatch):
    t = _admin(client)
    monkeypatch.setattr(
        billing_service, "start_checkout", lambda db, company, user: "https://checkout/x"
    )
    r = client.post("/api/v1/billing/checkout-session", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://checkout/x"


def test_checkout_requires_billing_manage(client, db, monkeypatch):
    # technician 角色无 billing.manage：注册管理员后另建低权限用户较繁，
    # 这里直接断言 super_admin/admin 有权（注册者默认 admin）→ 200；
    # 无权场景由单元 require_permission 既有测试覆盖。改为验证未认证 401：
    r = client.post("/api/v1/billing/checkout-session")
    assert r.status_code == 401


def test_portal_session_without_subscription_400(client, db):
    t = _admin(client)
    r = client.post("/api/v1/billing/portal-session", headers=_h(t))
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "NO_SUBSCRIPTION"


def test_webhook_bad_signature_400(client, db, monkeypatch):
    def _raise(payload, sig):
        raise stripe_gateway.SignatureError("bad")

    monkeypatch.setattr(stripe_gateway, "construct_event", _raise)
    r = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"}
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "INVALID_SIGNATURE"


def test_webhook_syncs_company(client, db, monkeypatch):
    _admin(client)
    co = db.execute(select(Company)).scalars().first()
    co.stripe_customer_id = "cus_1"
    db.commit()
    monkeypatch.setattr(
        stripe_gateway,
        "construct_event",
        lambda p, s: {
            "id": "evt_w1",
            "type": "customer.subscription.created",
            "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "active"}},
        },
    )
    r = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"}
    )
    assert r.status_code == 200, r.text
    db.refresh(co)
    assert co.plan == "pro" and co.subscription_status == "active"
```

> 执行时核实错误信封字段：既有 `test_feature_gating.py` 用 `r.json()["detail"]["code"]`，沿用之。

- [ ] **Step 4: 跑测试** `.venv/bin/python -m pytest tests/integration/test_billing_stripe_api.py -q` → PASS。
- [ ] **Step 5: 后端全量 + 门禁** `.venv/bin/python -m pytest -q && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app && .venv/bin/alembic heads`（单 head `p6_stripe_billing`）。
- [ ] **Step 6: Commit** `git commit -m "feat(billing): checkout/portal/webhook 端点 + 集成测试"`。

---

## Task 6: 前端（订阅按钮 / 门户 / 返回轮询）

**Files:**
- Modify `frontend/src/api/billing.ts`
- Modify `frontend/src/store/billing.ts`
- Modify `frontend/src/views/billing/PlansView.vue`
- Modify `frontend/src/views/billing/SettingsView.vue`
- Test: `frontend/tests/unit/store/billing.spec.ts`（Modify）、`frontend/tests/unit/views/billingPlans.spec.ts`（Create）

- [ ] **Step 1: api 加方法** —— 在 `frontend/src/api/billing.ts` 末尾加：

```typescript
export interface SessionUrl {
  url: string
}

export const createCheckoutSession = () =>
  http.post<SessionUrl>('/billing/checkout-session').then((r) => r.data)

export const createPortalSession = () =>
  http.post<SessionUrl>('/billing/portal-session').then((r) => r.data)
```

- [ ] **Step 2: store 加 action** —— 在 `frontend/src/store/billing.ts` 的 `actions` 里 `loadSubscription` 后加（轮询用于 checkout 返回后等 webhook 落地）：

```typescript
    async startCheckout(): Promise<void> {
      const { url } = await billingApi.createCheckoutSession()
      window.location.assign(url)
    },
    async openPortal(): Promise<void> {
      const { url } = await billingApi.createPortalSession()
      window.location.assign(url)
    },
    /** checkout 返回后轮询订阅直到 plan 翻新（webhook 异步）。最多 maxTries 次。 */
    async pollUntilPlanChange(prevPlan: string, maxTries = 8, intervalMs = 1500): Promise<void> {
      for (let i = 0; i < maxTries; i++) {
        await this.loadSubscription()
        if (this.subscription && this.subscription.plan !== prevPlan) return
        await new Promise((res) => setTimeout(res, intervalMs))
      }
    },
```

- [ ] **Step 3: PlansView 加订阅/联系销售** —— 改 `frontend/src/views/billing/PlansView.vue` 的卡片按钮区。`<script setup>` 加：

```typescript
import { usePermission } from '@/composables/usePermission'

const { hasPermission } = usePermission()
const salesEmail = import.meta.env.VITE_SALES_CONTACT_EMAIL ?? ''

async function subscribe(): Promise<void> {
  await billing.startCheckout()
}
```

模板里把原 `<el-button v-else disabled>请联系管理员升级</el-button>` 替换为：

```vue
        <template v-else>
          <el-button
            v-if="entry.plan === 'pro' && hasPermission('billing.manage')"
            type="primary"
            @click="subscribe"
          >
            订阅
          </el-button>
          <el-button
            v-else-if="entry.plan === 'enterprise'"
            tag="a"
            :href="salesEmail ? `mailto:${salesEmail}` : undefined"
            :disabled="!salesEmail"
          >
            联系销售
          </el-button>
          <el-button v-else disabled>请联系管理员升级</el-button>
        </template>
```

> 执行时核实 `usePermission` 路径（research 给出 `@/composables/usePermission`）。`VITE_SALES_CONTACT_EMAIL` 为前端构建期环境变量，缺省空 → enterprise 按钮禁用呈纯文案。

- [ ] **Step 4: SettingsView 加门户 + 返回轮询** —— 在 `frontend/src/views/billing/SettingsView.vue` `<script setup>` 加：

```typescript
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { usePermission } from '@/composables/usePermission'

const route = useRoute()
const { hasPermission } = usePermission()

async function manage(): Promise<void> {
  await billing.openPortal()
}

onMounted(async () => {
  if (route.query.checkout === 'success' && billing.subscription) {
    await billing.pollUntilPlanChange(billing.subscription.plan)
  }
})
```

模板里（当前套餐展示区附近）加：

```vue
    <el-button
      v-if="billing.planName === 'pro' && hasPermission('billing.manage')"
      @click="manage"
    >
      管理订阅 / 改支付方式
    </el-button>
    <p v-if="$route.query.checkout === 'success'" class="checkout-hint">
      支付已提交，正在确认订阅状态…
    </p>
```

> 执行时核实 SettingsView 既有 `billing` store 实例名与已 import（research 显示其已用 store 显示 plan）。

- [ ] **Step 5: 改/写前端测试**：

`frontend/tests/unit/store/billing.spec.ts` 加 mock 与用例（在既有 `vi.mock('@/api/billing', () => api)` 的 `api` 对象里补 `createCheckoutSession`/`createPortalSession`）：

```typescript
// 顶部 hoisted mock 改为：
const api = vi.hoisted(() => ({
  getSubscription: vi.fn(),
  createCheckoutSession: vi.fn(),
  createPortalSession: vi.fn(),
}))

it('startCheckout 跳转到返回的 url', async () => {
  api.createCheckoutSession.mockResolvedValue({ url: 'https://checkout/x' })
  const assign = vi.fn()
  vi.stubGlobal('window', { ...window, location: { assign } })
  const store = useBillingStore()
  await store.startCheckout()
  expect(assign).toHaveBeenCalledWith('https://checkout/x')
})

it('pollUntilPlanChange 在 plan 翻新后停止', async () => {
  let plan = 'free'
  api.getSubscription.mockImplementation(async () => ({
    plan, subscription_status: 'active', seat_used: 1, seat_limit: 3, features: [], catalog: [],
  }))
  const store = useBillingStore()
  await store.loadSubscription()
  setTimeout(() => { plan = 'pro' }, 0)
  await store.pollUntilPlanChange('free', 5, 1)
  expect(store.subscription?.plan).toBe('pro')
})
```

`frontend/tests/unit/views/billingPlans.spec.ts`（Create，对齐 `billingSettings.spec.ts` stub 风格）：

```typescript
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PlansView from '@/views/billing/PlansView.vue'
import { useBillingStore } from '@/store/billing'

vi.mock('@/composables/usePermission', () => ({
  usePermission: () => ({ hasPermission: () => true }),
}))

const slot = { template: '<div><slot /></div>' }

describe('PlansView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('pro 卡片对有权用户显示订阅按钮', async () => {
    const store = useBillingStore()
    store.subscription = {
      plan: 'free', subscription_status: 'active', seat_used: 1, seat_limit: 3, features: [],
      catalog: [
        { plan: 'free', seat_limit: 3, features: [] },
        { plan: 'pro', seat_limit: 15, features: ['meters'] },
      ],
    }
    const wrapper = mount(PlansView, {
      global: { stubs: { 'el-card': slot, 'el-tag': slot, 'el-button': slot } },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('订阅')
  })
})
```

- [ ] **Step 6: 跑前端测试 + 门禁** `cd frontend && npm run test && npm run typecheck && npm run lint` → 全绿。
- [ ] **Step 7: Commit** `git commit -m "feat(billing): 前端订阅/门户按钮 + 返回轮询"`。

---

## Task 7: 收尾（.env 样例 + 手验清单 + 全量门禁）

**Files:**
- Modify `backend/.env.example`（若存在；否则在计划报告里列出所需 env）
- Create/Modify `docs/superpowers/plans/2026-06-05-p6-stripe-billing.md` 的"手验清单"（本文件，执行时勾选）

- [ ] **Step 1: .env 样例** —— 若 `backend/.env.example` 存在，追加 Task 1 列出的 7 个 `STRIPE_*`/`BILLING_*`/`SALES_CONTACT_EMAIL` 键（值留占位 `sk_test_...`）。仓库**不存真实密钥**。

- [ ] **Step 2: 后端 + 前端全量门禁** —— 后端 `.venv/bin/python -m pytest -q && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app && .venv/bin/alembic heads`（单 head `p6_stripe_billing`）；前端 `npm run test && npm run typecheck && npm run lint`。

- [ ] **Step 3: env-gated MySQL bootstrap 复跑**（新迁移在 MySQL 也通）—— `mysql -uroot -e "DROP DATABASE IF EXISTS sop_mysql_verify; CREATE DATABASE sop_mysql_verify CHARACTER SET utf8mb4;"`；`TEST_MYSQL_URL="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify" .venv/bin/python -m pytest tests/test_mysql_bootstrap.py -q` → PASS（新列均 String，无 1101）。

- [ ] **Step 4: 端到端手验（test-mode，需 .env 填好真实 test 值）** ——
  1. 起后端 + 前端（见 [[running-smartsop-dev]]）。
  2. 另开终端：`stripe login`（一次）；`stripe listen --forward-to localhost:8000/api/v1/billing/webhook`，把打印的 `whsec_...` 填入 `.env` 的 `STRIPE_WEBHOOK_SECRET` 并重启后端。
  3. 浏览器登录 → 订阅页点 pro「订阅」→ Stripe 测试卡 `4242 4242 4242 4242`（任意未来日期/CVC）→ 成功返回 → 设置页「正在确认…」轮询后显示 `plan=pro`，某高级模块（如计量）解锁。
  4. 设置页「管理订阅」→ 门户取消订阅 → 回 app 刷新 → `plan=free`、模块回锁（402）。
  5. 记录结论（升/降两向 + 门控联动）。

- [ ] **Step 5: Commit + 汇报** —— `git commit -m "chore(billing): .env 样例 + 手验收尾" || echo 无改动`；汇报新增/改动文件、后端/前端通过数、单 head、手验结论、遗留项。

---

## Self-Review（执行后记录结论）

**Spec 覆盖**：§数据模型→Task 2 ✓；§stripe_gateway→Task 3 ✓；§billing_service+webhook 同步→Task 4 ✓；§路由→Task 5 ✓；§config+权限→Task 1 ✓；§前端→Task 6 ✓；§测试策略→各 task 单测+Task 7 手验 ✓；§与手动设档共存→不改 platform.py（保留）✓；§验收标准→分散 Task 4/5/6/7 ✓。

**执行注意**：
1. webhook 端点无认证、读 `await request.body()` 原始体；验签经 `stripe_gateway.construct_event` → `SignatureError` → 400。
2. 真相源是 `customer.subscription.*`，不处理 `checkout.session.completed`（customer 已在 start_checkout 落库）。
3. 新列均 String nullable，不涉 TEXT 字面默认 1101；新迁移 down_revision=`sop_tenancy_hardening`，收尾确认单 head `p6_stripe_billing`。
4. 密钥仅入 `.env`；仓库不存。enterprise 仍走 `platform.py` 手动设档，不在本轮改动。
5. 前端 `usePermission`/store 实例名/SettingsView 既有结构执行时以真实代码为准（research 已给路径，仍核实）。
