def _admin(client):
    return client.post("/api/v1/auth/register", json={
        "company_name": "Acme", "email": "admin@acme.com",
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_seeded_roles(client):
    t = _admin(client)
    codes = {x["code"] for x in client.get("/api/v1/roles", headers=_h(t)).json()}
    assert codes == {"super_admin", "admin", "technician", "viewer", "requester"}


def test_create_custom_role(client):
    t = _admin(client)
    r = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]})
    assert r.status_code == 201, r.text
    assert r.json()["permissions"] == ["user.view"]


def test_reject_unknown_permission(client):
    t = _admin(client)
    r = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "x", "name": "X", "permissions": ["does.not.exist"]})
    assert r.status_code == 422


def test_update_role(client):
    t = _admin(client)
    rid = client.post("/api/v1/roles", headers=_h(t), json={
        "code": "planner", "name": "计划员", "permissions": ["user.view"]}).json()["id"]
    r = client.patch(f"/api/v1/roles/{rid}", headers=_h(t),
                     json={"permissions": ["user.view", "user.create"]})
    assert r.status_code == 200
    assert set(r.json()["permissions"]) == {"user.view", "user.create"}


def test_cannot_delete_builtin(client):
    t = _admin(client)
    rid = [x for x in client.get("/api/v1/roles", headers=_h(t)).json()
           if x["code"] == "admin"][0]["id"]
    assert client.delete(f"/api/v1/roles/{rid}", headers=_h(t)).status_code == 400
