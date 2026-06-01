def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _new_user(client, t, email):
    return client.post(
        "/api/v1/users",
        headers=_h(t),
        json={"email": email, "password": "secret123", "name": email},
    ).json()["id"]


def test_create_and_list_team(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/teams", headers=_h(t), json={"name": "电气班", "description": "电工组"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "电气班"
    assert r.json()["member_ids"] == []
    names = {x["name"] for x in client.get("/api/v1/teams", headers=_h(t)).json()}
    assert names == {"电气班"}


def test_set_members(client):
    t = _admin(client)
    u1 = _new_user(client, t, "u1@acme.com")
    u2 = _new_user(client, t, "u2@acme.com")
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "电气班"}).json()["id"]
    r = client.put(f"/api/v1/teams/{tid}/members", headers=_h(t), json={"user_ids": [u1, u2]})
    assert r.status_code == 200, r.text
    assert set(r.json()["member_ids"]) == {u1, u2}
    r = client.put(f"/api/v1/teams/{tid}/members", headers=_h(t), json={"user_ids": [u1]})
    assert set(r.json()["member_ids"]) == {u1}


def test_update_and_delete_team(client):
    t = _admin(client)
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "电气班"}).json()["id"]
    assert (
        client.patch(f"/api/v1/teams/{tid}", headers=_h(t), json={"name": "电气一班"}).json()[
            "name"
        ]
        == "电气一班"
    )
    assert client.delete(f"/api/v1/teams/{tid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/teams", headers=_h(t)).json() == []


def test_requires_auth(client):
    assert client.get("/api/v1/teams").status_code == 401


def test_cross_tenant_team_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    tid = client.post("/api/v1/teams", headers=_h(tb), json={"name": "B班"}).json()["id"]
    assert client.get("/api/v1/teams", headers=_h(ta)).json() == []
    assert (
        client.patch(f"/api/v1/teams/{tid}", headers=_h(ta), json={"name": "x"}).status_code == 404
    )
