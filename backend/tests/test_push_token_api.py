"""移动端推送 token API：注册/幂等/注销/跨用户跨租户隔离。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def test_requires_auth(client):
    assert (
        client.post(
            "/api/v1/notifications/push-token", json={"token": "x", "platform": "ios"}
        ).status_code
        == 401
    )


def test_register_token_created(client):
    t = _register(client)
    r = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-abc", "platform": "ios"},
        headers=_h(t),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["token"] == "tok-abc" and body["platform"] == "ios" and body["id"]


def test_register_idempotent_updates_platform(client):
    t = _register(client)
    r1 = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-abc", "platform": "ios"},
        headers=_h(t),
    )
    assert r1.status_code == 201
    first_id = r1.json()["id"]
    r2 = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-abc", "platform": "android"},
        headers=_h(t),
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id  # 同行
    assert r2.json()["platform"] == "android"


def test_delete_token(client):
    t = _register(client)
    client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-del", "platform": "web"},
        headers=_h(t),
    )
    r = client.request(
        "DELETE",
        "/api/v1/notifications/push-token",
        json={"token": "tok-del"},
        headers=_h(t),
    )
    assert r.status_code == 204
    # 再注册应又是 201（确认已删）
    r2 = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-del", "platform": "web"},
        headers=_h(t),
    )
    assert r2.status_code == 201


def test_invalid_platform_rejected(client):
    t = _register(client)
    r = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok", "platform": "blackberry"},
        headers=_h(t),
    )
    assert r.status_code == 422


def test_cannot_delete_other_users_token(client):
    t_a = _register(client, company="Acme", email="a@acme.com")
    t_b = _register(client, company="Beta", email="b@beta.com")
    # A 注册 token
    client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-shared", "platform": "ios"},
        headers=_h(t_a),
    )
    # B 试图删 A 的 token（同字符串）：不报错但不应删到 A 的
    r = client.request(
        "DELETE",
        "/api/v1/notifications/push-token",
        json={"token": "tok-shared"},
        headers=_h(t_b),
    )
    assert r.status_code == 204
    # A 重新注册同 token 应得 200（仍存在 = 未被 B 删除）
    r2 = client.post(
        "/api/v1/notifications/push-token",
        json={"token": "tok-shared", "platform": "ios"},
        headers=_h(t_a),
    )
    assert r2.status_code == 200
