"""用户禁用/启用端点：禁用后登录被拒、启用后恢复、防自锁、跨租户 404。"""


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _make_user(client, t, email="bob@acme.com"):
    return client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": email, "password": "secret123", "name": "Bob"},
    ).json()["id"]


def test_disable_blocks_login_enable_restores(client):
    t = _admin(client)
    uid = _make_user(client, t)
    creds = {"email": "bob@acme.com", "password": "secret123", "company_slug": "acme"}

    # baseline: can log in
    assert client.post("/api/v1/auth/login", json=creds).status_code == 200

    # disable -> status flips, login rejected
    r = client.patch(f"/api/v1/users/{uid}/disable", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disabled"
    assert client.post("/api/v1/auth/login", json=creds).status_code == 401

    # enable -> login restored
    r = client.patch(f"/api/v1/users/{uid}/enable", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert client.post("/api/v1/auth/login", json=creds).status_code == 200


def test_cannot_disable_self(client):
    t = _admin(client)
    me = client.get("/api/v1/auth/me", headers=_h(t)).json()["id"]
    r = client.patch(f"/api/v1/users/{me}/disable", headers=_h(t))
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "USER_CANNOT_DISABLE_SELF"


def test_disable_cross_tenant_404(client):
    t1 = _admin(client, "Acme", "admin@acme.com")
    bob = _make_user(client, t1)
    t2 = _admin(client, "Globex", "admin@globex.com")
    assert client.patch(f"/api/v1/users/{bob}/disable", headers=_h(t2)).status_code == 404
    assert client.patch(f"/api/v1/users/{bob}/enable", headers=_h(t2)).status_code == 404
