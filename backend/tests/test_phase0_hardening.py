"""Phase 0 hardening: middleware-based isolation (C1), disabled-user (I2),
reserved role codes (M4)."""


def _register(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# --- C1: isolation is fail-closed via middleware (handlers no longer re-assert) ---


def test_list_users_scoped_without_handler_reassert(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "u1@acme.com", "password": "secret123", "name": "U1"},
    )
    a = {u["email"] for u in client.get("/api/v1/users", headers=_h(ta)).json()}
    b = {u["email"] for u in client.get("/api/v1/users", headers=_h(tb)).json()}
    assert "u1@acme.com" in a
    assert "u1@acme.com" not in b  # B never sees A's user — middleware scopes the read


def test_list_roles_scoped_without_handler_reassert(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    a_ids = {r["id"] for r in client.get("/api/v1/roles", headers=_h(ta)).json()}
    b_ids = {r["id"] for r in client.get("/api/v1/roles", headers=_h(tb)).json()}
    assert a_ids and b_ids
    assert a_ids.isdisjoint(b_ids)  # each tenant's seeded roles are distinct rows


# --- M4: built-in role codes are reserved ---


def test_create_role_reserved_code_rejected(client):
    t = _register(client)
    for code in ("super_admin", "admin", "technician", "viewer"):
        r = client.post(
            "/api/v1/roles", headers=_h(t), json={"code": code, "name": "X", "permissions": []}
        )
        assert r.status_code == 400, (code, r.text)


def test_create_role_nonreserved_code_ok(client):
    t = _register(client)
    r = client.post(
        "/api/v1/roles",
        headers=_h(t),
        json={"code": "planner", "name": "计划员", "permissions": ["user.view"]},
    )
    assert r.status_code == 201, r.text


# --- I2: disabled users cannot authenticate with an existing token ---


def test_disabled_user_access_token_rejected(client):
    admin = _register(client)
    created = client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={"email": "bob@acme.com", "password": "secret123", "name": "Bob"},
    ).json()
    bob = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@acme.com", "password": "secret123", "company_slug": "acme"},
    ).json()
    bob_access = bob["access_token"]
    bob_refresh = bob["refresh_token"]
    # Bob works while active.
    assert client.get("/api/v1/auth/me", headers=_h(bob_access)).status_code == 200
    # Admin disables Bob.
    r = client.patch(
        f"/api/v1/users/{created['id']}", headers=_h(admin), json={"status": "disabled"}
    )
    assert r.status_code == 200, r.text
    # Bob's still-valid access token is now rejected on protected endpoints.
    assert client.get("/api/v1/auth/me", headers=_h(bob_access)).status_code == 401
    # And refresh is rejected.
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": bob_refresh}).status_code == 401
    )
