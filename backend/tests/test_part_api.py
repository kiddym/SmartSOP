"""备件 API（Phase 3A）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post("/api/v1/users", headers=_h(admin_token), json={
        "email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid})
    return client.post("/api/v1/auth/login", json={
        "company_slug": "acme", "email": "tech@acme.com",
        "password": "secret123"}).json()["access_token"]


def _part(client, token, **kw):
    body = {"name": "轴承", "quantity": "10", "min_quantity": "3"}
    body.update(kw)
    return client.post("/api/v1/parts", json=body, headers=_h(token))


def test_part_crud(client):
    t = _admin(client)
    r = _part(client, t)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["custom_id"] == "PRT000001"
    assert r.json()["is_low_stock"] is False              # 10 >= 3
    got = client.get(f"/api/v1/parts/{pid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["name"] == "轴承"
    upd = client.patch(f"/api/v1/parts/{pid}", json={"quantity": "1"}, headers=_h(t))
    assert upd.json()["is_low_stock"] is True             # 1 < 3
    assert client.delete(f"/api/v1/parts/{pid}", headers=_h(t)).status_code == 204


def test_part_low_stock_filter(client):
    t = _admin(client)
    _part(client, t, name="低", quantity="1", min_quantity="5")
    _part(client, t, name="足", quantity="9", min_quantity="5")
    low = client.get("/api/v1/parts?low_stock=true", headers=_h(t)).json()
    assert len(low) == 1 and low[0]["name"] == "低"


def test_part_mini(client):
    t = _admin(client)
    _part(client, t, name="轴承")
    mini = client.get("/api/v1/parts/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert mini.json()[0]["custom_id"] == "PRT000001"
    assert set(mini.json()[0].keys()) == {"id", "name", "custom_id"}


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    _part(client, admin)
    assert client.get("/api/v1/parts", headers=_h(tech)).status_code == 200
    assert _part(client, tech, name="x").status_code == 403


def test_part_tenant_isolation(client):
    a = _admin(client)
    pid = _part(client, a).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/parts/{pid}", headers=_h(b)).status_code == 404
