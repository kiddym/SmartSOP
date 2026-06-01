def _register(client, company, email):
    r = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_users_list_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post(
        "/api/v1/users",
        headers=_h(ta),
        json={"email": "u1@acme.com", "password": "secret123", "name": "U1"},
    )
    client.post(
        "/api/v1/users",
        headers=_h(tb),
        json={"email": "u2@globex.com", "password": "secret123", "name": "U2"},
    )
    a = {u["email"] for u in client.get("/api/v1/users", headers=_h(ta)).json()}
    b = {u["email"] for u in client.get("/api/v1/users", headers=_h(tb)).json()}
    assert "u1@acme.com" in a and "u2@globex.com" not in a
    assert "u2@globex.com" in b and "u1@acme.com" not in b


def test_cross_tenant_user_fetch_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bob = client.post(
        "/api/v1/users",
        headers=_h(tb),
        json={"email": "bob@globex.com", "password": "secret123", "name": "Bob"},
    ).json()["id"]
    assert client.get(f"/api/v1/users/{bob}", headers=_h(ta)).status_code == 404


def test_cross_tenant_role_update_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    rid = next(
        x for x in client.get("/api/v1/roles", headers=_h(tb)).json() if x["code"] == "viewer"
    )["id"]
    assert (
        client.patch(f"/api/v1/roles/{rid}", headers=_h(ta), json={"name": "hacked"}).status_code
        == 404
    )


def test_company_me_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    assert client.get("/api/v1/companies/me", headers=_h(ta)).json()["slug"] == "acme"
    assert client.get("/api/v1/companies/me", headers=_h(tb)).json()["slug"] == "globex"
