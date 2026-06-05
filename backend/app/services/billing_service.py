"""计费服务（Phase 6）：发起 checkout/portal + webhook 同步订阅状态（真相源）。

webhook 处理 customer.subscription.created/updated/deleted；按 stripe_customer_id
反查公司，把 status/plan 同步到 Company。tb_billing_event 去重保证幂等。
"""

from __future__ import annotations

import logging
from typing import Any

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
# 设计原则：fail-closed —— 不在映射中的状态一律降级为 "canceled"（无访问权限）。
#
# 未列出的典型状态及原因：
#   incomplete      — 首次付款挂起（瞬态），Stripe 付款成功后会推送 .updated→active；
#                     在此之前不开通访问，等事件自然到达即可。
#   paused          — Stripe 暂停收费（Beta 功能），暂不开通访问，视同 canceled。
#
# 未知/新增状态 → canceled（fail-closed：未知 = 无访问权限）。
_STATUS_MAP = {
    "active": "active",
    "trialing": "active",  # 试用期：享有 pro 访问权限
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
        # 立即持久化 customer id：若 create_checkout_session 抛错，id 已存，下次 ensure_customer 复用（不泄漏 Stripe customer）。
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
        raise bad_request("NO_SUBSCRIPTION", "尚未绑定 Stripe 账户，请先发起订阅")
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
        _sync_subscription(db, event["data"]["object"], deleted=event_type.endswith("deleted"))
    db.add(BillingEvent(event_id=event_id, event_type=event_type, processed_at=utcnow()))
    db.commit()


def _sync_subscription(db: Session, sub: dict[str, Any], *, deleted: bool) -> None:
    customer_id = sub["customer"]
    company = db.execute(
        select(Company).where(Company.stripe_customer_id == customer_id)
    ).scalar_one_or_none()
    if company is None:
        logger.warning("webhook 订阅事件未匹配到公司 customer=%s", customer_id)
        return
    raw_status = sub.get("status", "")
    mapped = _STATUS_MAP.get(raw_status)
    if mapped is None and not deleted:
        logger.warning(
            "webhook 未知 subscription.status=%s sub=%s — 降级为 canceled",
            raw_status,
            sub.get("id"),
        )
    status = "canceled" if (deleted or mapped is None) else mapped
    if status == "canceled":
        company.plan = Plan.free.value
        company.subscription_status = "canceled"
        company.stripe_subscription_id = None
    else:
        company.plan = Plan.pro.value  # 单一 price = pro
        company.subscription_status = status
        company.stripe_subscription_id = sub["id"]
