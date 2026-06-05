import pytest
from sqlalchemy import select

from app.billing import stripe_gateway
from app.models.billing_event import BillingEvent
from app.models.company import Company
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
        stripe_gateway,
        "construct_event",
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
        stripe_gateway,
        "construct_event",
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
        stripe_gateway,
        "construct_event",
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
    ev = _event(
        "customer.subscription.updated", customer="cus_1", status="past_due", event_id="evt_dup"
    )
    monkeypatch.setattr(stripe_gateway, "construct_event", lambda p, s: ev)
    billing_service.handle_event(db, b"{}", "sig")
    ev2 = _event(
        "customer.subscription.updated", customer="cus_1", status="active", event_id="evt_dup"
    )
    monkeypatch.setattr(stripe_gateway, "construct_event", lambda p, s: ev2)
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.subscription_status == "past_due"  # 仍是首次结果
    assert db.get(BillingEvent, "evt_dup") is not None


def test_unknown_customer_tolerated(client, db, monkeypatch):
    monkeypatch.setattr(
        stripe_gateway,
        "construct_event",
        lambda p, s: _event(
            "customer.subscription.created", customer="cus_ghost", event_id="evt_g"
        ),
    )
    billing_service.handle_event(db, b"{}", "sig")  # 不抛
    assert db.get(BillingEvent, "evt_g") is not None


def test_trialing_maps_active(client, db, monkeypatch):
    co = _company(client, db)
    co.stripe_customer_id = "cus_1"
    db.commit()
    monkeypatch.setattr(
        stripe_gateway,
        "construct_event",
        lambda p, s: _event(
            "customer.subscription.updated",
            customer="cus_1",
            status="trialing",
            event_id="evt_trial",
        ),
    )
    billing_service.handle_event(db, b"{}", "sig")
    db.refresh(co)
    assert co.subscription_status == "active"
    assert co.plan == "pro"


def test_open_portal_without_customer_400(client, db):
    co = _company(client, db)
    with pytest.raises(Exception) as exc:
        billing_service.open_portal(db, co)
    # bad_request 返回 fastapi HTTPException
    assert getattr(exc.value, "status_code", None) == 400
