def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Acme",
            "email": "admin@acme.com",
            "password": "secret123",
            "name": "Admin",
        },
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_creates_user(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "bob@acme.com"


def test_list_users_scoped(client):
    t = _admin(client)
    client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    )
    emails = {u["email"] for u in client.get("/api/v1/users", headers=_h(t)).json()}
    assert emails == {"admin@acme.com", "bob@acme.com"}


def test_create_requires_auth(client):
    r = client.post(
        "/api/v1/users", json={"email": "x@acme.com", "password": "secret123", "name": "X"}
    )
    assert r.status_code == 401


def test_new_user_can_login(client):
    t = _admin(client)
    client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@acme.com", "password": "secret123", "company_slug": "acme"},
    )
    assert r.status_code == 200, r.text


def test_list_users_tenant_isolated(client):
    """A tenant's user list must never include another tenant's users."""
    t1 = _admin(client)
    client.post(
        "/api/v1/users",
        headers=_h(t1),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    )
    t2 = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Globex",
            "email": "admin@globex.com",
            "password": "secret123",
            "name": "Admin2",
        },
    ).json()["access_token"]
    client.post(
        "/api/v1/users",
        headers=_h(t2),
        json={"email": "carol@globex.com", "password": "secret123", "name": "Carol"},
    )

    acme = {u["email"] for u in client.get("/api/v1/users", headers=_h(t1)).json()}
    globex = {u["email"] for u in client.get("/api/v1/users", headers=_h(t2)).json()}
    assert acme == {"admin@acme.com", "bob@acme.com"}
    assert globex == {"admin@globex.com", "carol@globex.com"}


def test_create_user_with_profile_fields(client):
    """Admin may set phone/job_title/rate/avatar_url at creation."""
    t = _admin(client)
    r = client.post(
        "/api/v1/users",
        headers=_h(t),
        json={
            "email": "bob@acme.com",
            "password": "secret123",
            "name": "Bob",
            "phone": "+1-555-0100",
            "job_title": "Technician",
            "rate": "42.5000",
            "avatar_url": "https://cdn.example.com/bob.png",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["phone"] == "+1-555-0100"
    assert body["job_title"] == "Technician"
    assert str(body["rate"]) in ("42.5", "42.5000", "42.50")
    assert body["avatar_url"] == "https://cdn.example.com/bob.png"


def test_update_user_profile_fields(client):
    """Profile fields are editable via PATCH and persisted."""
    t = _admin(client)
    uid = client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    ).json()["id"]
    r = client.patch(
        f"/api/v1/users/{uid}",
        headers=_h(t),
        json={"phone": "12345", "job_title": "Lead", "rate": "60"},
    )
    assert r.status_code == 200, r.text
    fetched = client.get(f"/api/v1/users/{uid}", headers=_h(t)).json()
    assert fetched["phone"] == "12345"
    assert fetched["job_title"] == "Lead"
    assert str(fetched["rate"]) in ("60", "60.0", "60.0000", "60.00")


def test_profile_fields_default_null(client):
    """Users created without profile fields expose them as null."""
    t = _admin(client)
    uid = client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    ).json()["id"]
    fetched = client.get(f"/api/v1/users/{uid}", headers=_h(t)).json()
    assert fetched["phone"] is None
    assert fetched["job_title"] is None
    assert fetched["rate"] is None
    assert fetched["avatar_url"] is None


def test_get_other_tenant_user_404(client):
    """Cross-tenant fetch by id (db.get bypasses read-scope) must 404."""
    t1 = _admin(client)
    bob_id = client.post(
        "/api/v1/users",
        headers=_h(t1),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    ).json()["id"]
    t2 = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Globex",
            "email": "admin@globex.com",
            "password": "secret123",
            "name": "Admin2",
        },
    ).json()["access_token"]
    r = client.get(f"/api/v1/users/{bob_id}", headers=_h(t2))
    assert r.status_code == 404, r.text
