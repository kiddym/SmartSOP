def _register(client, company="Acme", email="a@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Alice"})


def test_register_returns_tokens(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_then_me(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "secret123"})
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == "a@acme.com"
    assert body["role_code"] == "super_admin"
    assert "user.create" in body["permissions"]


def test_login_bad_password_401(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"email": "a@acme.com", "password": "wrong"})
    assert r.status_code == 401


def test_refresh(client):
    reg = _register(client).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": reg["refresh_token"]})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
