"""POST /auth/logout 清除 access_token cookie（安全跟进：登出残留会话）。"""
from __future__ import annotations


def _register(client, email="a@acme.com"):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_logout_clears_access_cookie(client):
    _register(client)
    # login sets the cookie
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.cookies
    # logout must clear it
    r2 = client.post("/api/v1/auth/logout")
    assert r2.status_code == 200
    # Starlette TestClient: a cleared cookie shows up as a Set-Cookie with an expiry in the past / max-age=0.
    set_cookie = r2.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert ("Max-Age=0" in set_cookie) or ("max-age=0" in set_cookie) or ("expires=" in set_cookie.lower())


def test_logout_works_without_auth(client):
    # logout must succeed even with no token (you can log out with an expired/absent session)
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 200
