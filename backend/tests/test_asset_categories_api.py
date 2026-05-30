def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_and_list_category(client):
    t = _admin(client)
    r = client.post("/api/v1/asset-categories", headers=_h(t), json={"name": "泵类"})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "泵类"
    names = {c["name"] for c in client.get("/api/v1/asset-categories", headers=_h(t)).json()}
    assert names == {"泵类"}


def test_update_and_delete_category(client):
    t = _admin(client)
    cid = client.post("/api/v1/asset-categories", headers=_h(t), json={"name": "泵类"}).json()["id"]
    r = client.patch(f"/api/v1/asset-categories/{cid}", headers=_h(t), json={"name": "水泵"})
    assert r.status_code == 200
    assert r.json()["name"] == "水泵"
    assert client.delete(f"/api/v1/asset-categories/{cid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/asset-categories", headers=_h(t)).json() == []


def test_requires_auth(client):
    assert client.get("/api/v1/asset-categories").status_code == 401


def test_cross_tenant_category_isolated(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    cid = client.post("/api/v1/asset-categories", headers=_h(tb), json={"name": "B类"}).json()["id"]
    assert client.get("/api/v1/asset-categories", headers=_h(ta)).json() == []
    assert client.patch(f"/api/v1/asset-categories/{cid}", headers=_h(ta),
                        json={"name": "x"}).status_code == 404
