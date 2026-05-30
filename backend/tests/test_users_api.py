def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_creates_user(client):
    t = _admin(client)
    r = client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "bob@acme.com"


def test_list_users_scoped(client):
    t = _admin(client)
    client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    emails = {u["email"] for u in client.get("/api/v1/users", headers=_h(t)).json()}
    assert emails == {"admin@acme.com", "bob@acme.com"}


def test_create_requires_auth(client):
    r = client.post("/api/v1/users", json={
        "email": "x@acme.com", "password": "secret123", "name": "X"})
    assert r.status_code == 401


def test_new_user_can_login(client):
    t = _admin(client)
    client.post("/api/v1/users", headers=_h(t), json={
        "email": "bob@acme.com", "password": "secret123", "name": "Bob"})
    r = client.post("/api/v1/auth/login", json={
        "email": "bob@acme.com", "password": "secret123", "company_slug": "acme"})
    assert r.status_code == 200, r.text
