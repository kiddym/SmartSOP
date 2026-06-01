"""备件消耗 API（Phase 3A，挂工单）。"""

from __future__ import annotations


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


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def _part_id(client, t, **kw):
    body = {"name": "轴承", "cost": "12.5", "quantity": "10"}
    body.update(kw)
    return client.post("/api/v1/parts", json=body, headers=_h(t)).json()["id"]


def test_consume_decrements_and_returns_ledger(client):
    t = _admin(client)
    wo, pid = _wo_id(client, t), _part_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "3"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    assert r.json()["unit_cost"] == "12.5000" or float(r.json()["unit_cost"]) == 12.5
    assert float(r.json()["total_cost"]) == 37.5  # 3 * 12.5
    # 库存扣减
    assert float(client.get(f"/api/v1/parts/{pid}", headers=_h(t)).json()["quantity"]) == 7.0
    lst = client.get(f"/api/v1/work-orders/{wo}/part-consumptions", headers=_h(t))
    assert len(lst.json()) == 1


def test_consume_insufficient_400(client):
    t = _admin(client)
    wo, pid = _wo_id(client, t), _part_id(client, t, quantity="2")
    r = client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "5"},
        headers=_h(t),
    )
    assert r.status_code == 400


def test_technician_can_consume(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    wo, pid = _wo_id(client, admin), _part_id(client, admin)
    r = client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "1"},
        headers=_h(tech),
    )
    assert r.status_code == 201, r.text


def test_consume_cross_tenant_404(client):
    a = _admin(client)
    wo, pid = _wo_id(client, a), _part_id(client, a)
    b = _admin(client, company="Beta", email="admin@beta.com")
    # 他租户工单不可见
    r = client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "1"},
        headers=_h(b),
    )
    assert r.status_code == 404
