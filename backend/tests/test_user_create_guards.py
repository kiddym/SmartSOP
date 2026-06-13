"""POST /users 的座席上限与角色租户校验（审计 #4）。free 套餐 seat_limit=3。"""
from __future__ import annotations


def _register(client, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_user_rejects_foreign_role(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    b_role = client.get("/api/v1/roles", headers=_h(tb)).json()[0]["id"]
    r = client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "u@acme.com", "password": "secret123", "name": "U", "role_id": b_role},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_ROLE"


def test_create_user_enforces_seat_limit(client):
    ta = _register(client, "Acme", "a@acme.com")  # 注册即占 1 席（super_admin）
    for i in range(2):
        r = client.post(
            "/api/v1/users",
            headers=_h(ta),
            json={"email": f"u{i}@acme.com", "password": "secret123", "name": f"U{i}"},
        )
        assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "overflow@acme.com", "password": "secret123", "name": "Over"},
    )
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "SEAT_LIMIT_REACHED"


def test_create_user_accepts_own_company_role(client):
    ta = _register(client, "Acme", "a@acme.com")
    own_role = client.get("/api/v1/roles", headers=_h(ta)).json()[0]["id"]
    r = client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "member@acme.com", "password": "secret123", "name": "Member", "role_id": own_role},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role_id"] == own_role
