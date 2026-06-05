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
    return session.url or ""  # SDK types url as str | None; non-None guaranteed for valid sessions


def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """建客户门户 Session，返回 URL。"""
    _api_key()
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url or ""  # SDK types url as str | None; non-None guaranteed for valid sessions


def construct_event(payload: bytes, sig_header: str) -> dict[str, Any]:
    """验签并解析 webhook 事件；验签失败抛 SignatureError。"""
    try:
        event = stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:  # type: ignore[attr-defined]
        raise SignatureError(str(exc)) from exc
    return dict(event)
