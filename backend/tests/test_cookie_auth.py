"""GET 接受 access_token cookie；写操作仍只认 Authorization 头（审计 #6 + CSRF 安全）。"""
from __future__ import annotations


def _register(client, company="Acme", email="a@acme.com"):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def test_login_sets_access_cookie(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.cookies


def test_me_get_accepts_cookie_only(client):
    tok = _register(client)
    client.cookies.clear()
    client.cookies.set("access_token", tok)
    r = client.get("/api/v1/auth/me")  # 无 Authorization 头
    assert r.status_code == 200
    assert r.json()["email"] == "a@acme.com"


def test_mutation_rejects_cookie_only(client):
    tok = _register(client)
    client.cookies.clear()
    client.cookies.set("access_token", tok)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "secret123", "new_password": "newsecret123"},
    )
    assert r.status_code == 401  # 写操作不认 cookie，防 CSRF


def test_feature_gated_get_accepts_cookie_only(client):
    """audit #6 真实链路：经 require_feature 包装的 GET（procedures 路由）也接受 cookie 兜底。"""
    tok = _register(client)
    client.cookies.clear()
    client.cookies.set("access_token", tok)
    r = client.get("/api/v1/procedures", params={"page": 1, "page_size": 1})  # 无 Authorization 头
    assert r.status_code == 200
