"""/analytics/trends：日/周分桶，连续空桶，非法 granularity 400，跨租户隔离。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_daily_buckets_continuous(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(
        WorkOrder(custom_id="WO1", title="t", created_at=datetime(2026, 5, 30, 9), company_id=co)
    )
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


def test_tenant_isolation(client, db):
    """B 公司工单不计入 A 公司的桶。"""
    t_a = _admin(client)
    _admin(client, company="Beta", email="b@beta.com")
    co_b = _company_id(db, "beta")
    db.add(
        WorkOrder(custom_id="WO1", title="t", created_at=datetime(2026, 5, 30, 9), company_id=co_b)
    )
    db.commit()
    body = client.get(
        "/api/v1/analytics/trends?date_from=2026-05-29&date_to=2026-05-31&granularity=day",
        headers=_h(t_a),
    ).json()
    assert all(b["work_orders_created"] == 0 for b in body["buckets"])
