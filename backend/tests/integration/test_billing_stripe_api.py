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


def test_checkout_requires_auth(client, db):
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
