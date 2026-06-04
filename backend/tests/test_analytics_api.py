"""分析 API（Phase 4）：鉴权/RBAC/形状/跨租户。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "tech@acme.com", "password": "secret123"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_all_four_dashboards_200(client):
    t = _admin(client)
    for path in ("work-orders", "costs", "asset-reliability", "inventory"):
        r = client.get(f"/api/v1/analytics/{path}", headers=_h(t))
        assert r.status_code == 200, (path, r.text)


def test_requires_auth(client):
    assert client.get("/api/v1/analytics/work-orders").status_code == 401


def test_technician_forbidden(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    assert client.get("/api/v1/analytics/work-orders", headers=_h(tech)).status_code == 403


def test_work_order_dashboard_counts(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/work-orders", headers=_h(t)).json()
    assert body["total"] == 1 and "by_status" in body


def test_tenant_isolation(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    co_a = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co_a))
    db.commit()
    assert client.get("/api/v1/analytics/work-orders", headers=_h(ta)).json()["total"] == 1
    assert client.get("/api/v1/analytics/work-orders", headers=_h(tb)).json()["total"] == 0
