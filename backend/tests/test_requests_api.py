"""维修请求 API 集成测试（Phase 2A）。

全程经 API 建立认证主体（register/roles/users/login），使用 conftest 的
`client` fixture（get_db 已覆盖到与 `db` 同一测试引擎）。不要手工 db.add(User)，
否则租户上下文与盖章时机会导致鉴权读不到用户。
"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _requester_token(client, admin_token):
    """复用内置 requester 角色（注册时已 seed，仅 request.view/create），
    建用户并登录取其 token。"""
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "requester")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "req@acme.com", "password": "secret123", "name": "Req", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "req@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_create_and_get_request(client):
    t = _admin(client)
    resp = client.post("/api/v1/requests", json={"title": "漏水"}, headers=_h(t))
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]
    assert resp.json()["custom_id"] == "RQ000001"
    got = client.get(f"/api/v1/requests/{rid}", headers=_h(t))
    assert got.status_code == 200
    assert got.json()["status"] == "PENDING"


def test_approve_generates_work_order(client):
    t = _admin(client)
    rid = client.post("/api/v1/requests", json={"title": "t"}, headers=_h(t)).json()["id"]
    resp = client.post(f"/api/v1/requests/{rid}/approve", json={"note": "ok"}, headers=_h(t))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["work_order_id"] is not None


def test_pending_list_excludes_resolved(client):
    t = _admin(client)
    a = client.post("/api/v1/requests", json={"title": "a"}, headers=_h(t)).json()["id"]
    b = client.post("/api/v1/requests", json={"title": "b"}, headers=_h(t)).json()["id"]
    client.post(f"/api/v1/requests/{b}/cancel", json={"reason": "x"}, headers=_h(t))
    pending = client.get("/api/v1/requests/pending", headers=_h(t))
    ids = {r["id"] for r in pending.json()}
    assert a in ids and b not in ids


def test_requester_cannot_approve(client):
    admin = _admin(client)
    rid = client.post("/api/v1/requests", json={"title": "t"}, headers=_h(admin)).json()["id"]
    req_token = _requester_token(client, admin)
    resp = client.post(f"/api/v1/requests/{rid}/approve", json={}, headers=_h(req_token))
    assert resp.status_code == 403


def test_comment_and_activities(client):
    t = _admin(client)
    rid = client.post("/api/v1/requests", json={"title": "t"}, headers=_h(t)).json()["id"]
    client.post(f"/api/v1/requests/{rid}/activities", json={"comment": "hi"}, headers=_h(t))
    acts = client.get(f"/api/v1/requests/{rid}/activities", headers=_h(t))
    assert any(a["activity_type"] == "COMMENT" for a in acts.json())
