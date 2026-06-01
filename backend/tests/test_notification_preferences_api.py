"""偏好 API（/api/v1/notification-preferences）：仅本人、跨租户隔离。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_get_default_when_unset(client):
    t = _admin(client)
    r = client.get("/api/v1/notification-preferences", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json() == {"email_enabled": True, "disabled_types": []}


def test_put_then_get(client):
    t = _admin(client)
    put = client.put("/api/v1/notification-preferences",
                     json={"email_enabled": False, "disabled_types": ["WO_ASSIGNED"]},
                     headers=_h(t))
    assert put.status_code == 200, put.text
    got = client.get("/api/v1/notification-preferences", headers=_h(t)).json()
    assert got["email_enabled"] is False
    assert got["disabled_types"] == ["WO_ASSIGNED"]


def test_requires_auth(client):
    assert client.get("/api/v1/notification-preferences").status_code == 401
