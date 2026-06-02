from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


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


def test_time_category_crud(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/time-categories",
        json={"name": "常规工时", "hourly_rate": "80.00"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert float(r.json()["hourly_rate"]) == 80.0
    assert client.get("/api/v1/time-categories", headers=_h(t)).status_code == 200
    upd = client.patch(
        f"/api/v1/time-categories/{cid}", json={"hourly_rate": "120"}, headers=_h(t)
    )
    assert float(upd.json()["hourly_rate"]) == 120.0
    assert client.delete(f"/api/v1/time-categories/{cid}", headers=_h(t)).status_code == 204
    # 软删后不在列表
    assert client.get("/api/v1/time-categories", headers=_h(t)).json() == []


def test_time_category_default_rate_zero(client):
    t = _admin(client)
    r = client.post("/api/v1/time-categories", json={"name": "无费率"}, headers=_h(t))
    assert r.status_code == 201, r.text
    assert float(r.json()["hourly_rate"]) == 0.0


def test_time_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post(
        "/api/v1/time-categories", json={"name": "X"}, headers=_h(a)
    ).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/time-categories/{cid}", headers=_h(b)).status_code == 404


def test_time_category_technician_cannot_manage(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    # technician 有 view 无 manage
    assert client.get("/api/v1/time-categories", headers=_h(tech)).status_code == 200
    r = client.post("/api/v1/time-categories", json={"name": "x"}, headers=_h(tech))
    assert r.status_code == 403
