"""Self-service profile endpoints (/api/v1/users/me)."""


def _register(client):
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


def test_get_my_profile_returns_full_user(client):
    t = _register(client)
    r = client.get("/api/v1/users/me", headers=_h(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "admin@acme.com"
    assert body["name"] == "Admin"
    # Full UserRead exposes profile fields (null when unset).
    for key in ("phone", "job_title", "rate", "avatar_url", "locale"):
        assert key in body


def test_get_my_profile_requires_auth(client):
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401


def test_patch_my_profile_persists(client):
    t = _register(client)
    r = client.patch(
        "/api/v1/users/me",
        headers=_h(t),
        json={"name": "New Name", "phone": "+1-555-9000", "job_title": "Operator"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "New Name"
    assert body["phone"] == "+1-555-9000"
    assert body["job_title"] == "Operator"
    # Persisted across a fresh read.
    fetched = client.get("/api/v1/users/me", headers=_h(t)).json()
    assert fetched["name"] == "New Name"
    assert fetched["phone"] == "+1-555-9000"
    assert fetched["job_title"] == "Operator"


def test_patch_my_profile_updates_locale_and_avatar(client):
    t = _register(client)
    r = client.patch(
        "/api/v1/users/me",
        headers=_h(t),
        json={"locale": "en-US", "avatar_url": "https://cdn.example.com/me.png"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["locale"] == "en-US"
    assert body["avatar_url"] == "https://cdn.example.com/me.png"


def test_patch_my_profile_ignores_privileged_fields(client):
    t = _register(client)
    before = client.get("/api/v1/users/me", headers=_h(t)).json()
    r = client.patch(
        "/api/v1/users/me",
        headers=_h(t),
        json={
            "name": "Still Admin",
            "role_id": "00000000-0000-0000-0000-000000000000",
            "status": "disabled",
            "rate": "999.0000",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Whitelisted field applied...
    assert body["name"] == "Still Admin"
    # ...privileged fields silently ignored (extra="ignore").
    assert body["role_id"] == before["role_id"]
    assert body["status"] == "active"
    assert body["rate"] is None


def test_patch_my_profile_requires_auth(client):
    r = client.patch("/api/v1/users/me", json={"name": "X"})
    assert r.status_code == 401
