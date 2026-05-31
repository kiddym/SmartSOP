"""供应商 API（Phase 3B）。"""
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


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"},
                       headers=_h(t)).json()["id"]


def test_vendor_crud_and_parts(client):
    t = _admin(client)
    p1 = _part_id(client, t, "A")
    r = client.post("/api/v1/vendors",
                    json={"name": "供应商A", "vendor_type": "轴承", "part_ids": [p1]},
                    headers=_h(t))
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert r.json()["vendor_type"] == "轴承" and r.json()["part_ids"] == [p1]
    got = client.get(f"/api/v1/vendors/{vid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["name"] == "供应商A"
    upd = client.patch(f"/api/v1/vendors/{vid}", json={"name": "改名", "part_ids": []},
                       headers=_h(t))
    assert upd.json()["name"] == "改名" and upd.json()["part_ids"] == []
    assert client.delete(f"/api/v1/vendors/{vid}", headers=_h(t)).status_code == 204


def test_vendor_filter_by_part(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    client.post("/api/v1/vendors", json={"name": "V1", "part_ids": [p1]}, headers=_h(t))
    client.post("/api/v1/vendors", json={"name": "V2", "part_ids": [p2]}, headers=_h(t))
    got = client.get(f"/api/v1/vendors?part_id={p1}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["name"] == "V1"


def test_vendor_mini(client):
    t = _admin(client)
    client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(t))
    mini = client.get("/api/v1/vendors/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "name"}
    assert mini.json()[0]["name"] == "供应商A"


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    client.post("/api/v1/vendors", json={"name": "供应商A"}, headers=_h(admin))
    assert client.get("/api/v1/vendors", headers=_h(tech)).status_code == 200
    assert client.post("/api/v1/vendors", json={"name": "x"},
                       headers=_h(tech)).status_code == 403


def test_vendor_tenant_isolation(client):
    a = _admin(client)
    vid = client.post("/api/v1/vendors", json={"name": "供应商A"},
                      headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/vendors/{vid}", headers=_h(b)).status_code == 404
