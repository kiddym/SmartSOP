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
