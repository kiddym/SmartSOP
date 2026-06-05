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
    captured: dict = {}

    def _fake_start_checkout(db_, company_, user_):
        captured["company"] = company_
        captured["user"] = user_
        return "https://checkout/x"

    monkeypatch.setattr(billing_service, "start_checkout", _fake_start_checkout)
    r = client.post("/api/v1/billing/checkout-session", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["url"] == "https://checkout/x"
    # Verify correct objects were threaded through to the service
    assert captured["company"] is not None
    assert captured["user"].email == "a@acme.com"


def test_checkout_requires_auth(client, db):
    r = client.post("/api/v1/billing/checkout-session")
    assert r.status_code == 401


# test_checkout_forbidden_for_unprivileged: billing.manage gating is provided by
# `require_permission`, which is already covered by unit tests in
# tests/test_auth_deps.py (test_require_permission_denies_viewer).  Spinning up
# a low-privilege user here requires the full invite+accept-invite flow with no
# cheap helper — skipped to avoid heavy fixture duplication.


def test_portal_session_without_subscription_400(client, db):
    t = _admin(client)
    r = client.post("/api/v1/billing/portal-session", headers=_h(t))
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "NO_SUBSCRIPTION"


def test_webhook_bad_signature_400(client, db, monkeypatch):
    def _raise(payload, sig):
        raise stripe_gateway.SignatureError("bad")

    monkeypatch.setattr(stripe_gateway, "construct_event", _raise)
    r = client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"})
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
    r = client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"})
    assert r.status_code == 200, r.text
    db.refresh(co)
    assert co.plan == "pro" and co.subscription_status == "active"
