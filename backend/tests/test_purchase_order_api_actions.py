"""采购单 API 状态动作 + RBAC（Phase 3C）。"""

from __future__ import annotations

from decimal import Decimal

import pytest

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


def _vendor_id(client, t):
    return client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(t)).json()["id"]


def _part_id(client, t, name="轴承"):
    return client.post(
        "/api/v1/parts", json={"name": name, "quantity": "10"}, headers=_h(t)
    ).json()["id"]


def _draft_with_line(client, t):
    v, p = _vendor_id(client, t), _part_id(client, t)
    return client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": v, "lines": [{"part_id": p, "quantity": "3", "unit_cost": "2"}]},
        headers=_h(t),
    ).json(), p


def test_submit_then_approve_writes_back_stock(client):
    t = _admin(client)
    po, p = _draft_with_line(client, t)
    pid = po["id"]
    assert (
        client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t)).json()["status"]
        == "SUBMITTED"
    )
    appr = client.post(f"/api/v1/purchase-orders/{pid}/approve", json={"note": "ok"}, headers=_h(t))
    assert appr.status_code == 200 and appr.json()["status"] == "APPROVED"
    assert Decimal(
        str(client.get(f"/api/v1/parts/{p}", headers=_h(t)).json()["quantity"])
    ) == Decimal("13")
    acts = client.get(f"/api/v1/purchase-orders/{pid}/activities", headers=_h(t)).json()
    assert any(a["activity_type"] == "RECEIVED" for a in acts)


def test_submit_empty_400(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    pid = client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(t)).json()["id"]
    assert client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t)).status_code == 400


def test_reject_and_cancel(client):
    t = _admin(client)
    po, _ = _draft_with_line(client, t)
    pid = po["id"]
    client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(t))
    assert (
        client.post(
            f"/api/v1/purchase-orders/{pid}/reject", json={"note": "x"}, headers=_h(t)
        ).json()["status"]
        == "REJECTED"
    )
    po2, _ = _draft_with_line(client, t)
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po2['id']}/cancel", json={"note": "x"}, headers=_h(t)
        ).json()["status"]
        == "CANCELED"
    )


def test_technician_view_only(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    v = _vendor_id(client, admin)
    client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(admin)).json()["id"]
    assert client.get("/api/v1/purchase-orders", headers=_h(tech)).status_code == 200
    assert (
        client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(tech)).status_code
        == 403
    )


def test_technician_cannot_approve(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    v = _vendor_id(client, admin)
    p = _part_id(client, admin)
    pid = client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": v, "lines": [{"part_id": p, "quantity": "1"}]},
        headers=_h(admin),
    ).json()["id"]
    client.post(f"/api/v1/purchase-orders/{pid}/submit", headers=_h(admin))
    assert (
        client.post(
            f"/api/v1/purchase-orders/{pid}/approve", json={"note": ""}, headers=_h(tech)
        ).status_code
        == 403
    )
