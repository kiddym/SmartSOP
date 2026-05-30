def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_assigns_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区A"}).json()
    b = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区B"}).json()
    assert a["custom_id"] == "L000001"
    assert b["custom_id"] == "L000002"


def test_tree_children_and_cycle_guard(client):
    t = _admin(client)
    root = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区"}).json()
    child = client.post("/api/v1/locations", headers=_h(t),
                        json={"name": "车间", "parent_id": root["id"]}).json()
    kids = client.get(f"/api/v1/locations/{root['id']}/children", headers=_h(t)).json()
    assert {k["id"] for k in kids} == {child["id"]}
    r = client.patch(f"/api/v1/locations/{root['id']}", headers=_h(t),
                     json={"parent_id": child["id"]})
    assert r.status_code == 400, r.text
    assert client.patch(f"/api/v1/locations/{root['id']}", headers=_h(t),
                        json={"parent_id": root["id"]}).status_code == 400


def test_delete_with_children_rejected(client):
    t = _admin(client)
    root = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区"}).json()
    client.post("/api/v1/locations", headers=_h(t), json={"name": "车间", "parent_id": root["id"]})
    assert client.delete(f"/api/v1/locations/{root['id']}", headers=_h(t)).status_code == 400


def test_mini_and_relations(client):
    t = _admin(client)
    u = client.post("/api/v1/users", headers=_h(t),
                    json={"email": "w@acme.com", "password": "secret123", "name": "W"}).json()["id"]
    tid = client.post("/api/v1/teams", headers=_h(t), json={"name": "班组"}).json()["id"]
    loc = client.post("/api/v1/locations", headers=_h(t), json={
        "name": "厂区", "assigned_user_ids": [u], "team_ids": [tid]}).json()
    assert set(loc["assigned_user_ids"]) == {u}
    assert set(loc["team_ids"]) == {tid}
    mini = client.get("/api/v1/locations/mini", headers=_h(t)).json()
    assert mini[0]["custom_id"] == "L000001" and "name" in mini[0]


def test_requires_auth(client):
    assert client.get("/api/v1/locations").status_code == 401


def test_cross_tenant_location_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    lid = client.post("/api/v1/locations", headers=_h(tb), json={"name": "B区"}).json()["id"]
    assert client.get("/api/v1/locations", headers=_h(ta)).json() == []
    assert client.get(f"/api/v1/locations/{lid}", headers=_h(ta)).status_code == 404
