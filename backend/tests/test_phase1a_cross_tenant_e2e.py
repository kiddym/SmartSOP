def _register(client, company, email):
    r = client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_assets_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/assets", headers=_h(ta), json={"name": "A泵"})
    bid = client.post("/api/v1/assets", headers=_h(tb), json={"name": "B泵"}).json()["id"]
    a_names = {x["name"] for x in client.get("/api/v1/assets", headers=_h(ta)).json()}
    assert a_names == {"A泵"}
    assert client.get(f"/api/v1/assets/{bid}", headers=_h(ta)).status_code == 404
    assert client.patch(f"/api/v1/assets/{bid}", headers=_h(ta),
                        json={"name": "hacked"}).status_code == 404
    assert client.delete(f"/api/v1/assets/{bid}", headers=_h(ta)).status_code == 404


def test_locations_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/locations", headers=_h(tb), json={"name": "B区"}).json()["id"]
    assert client.get("/api/v1/locations", headers=_h(ta)).json() == []
    assert client.get(f"/api/v1/locations/{bid}", headers=_h(ta)).status_code == 404


def test_teams_and_categories_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    btid = client.post("/api/v1/teams", headers=_h(tb), json={"name": "B班"}).json()["id"]
    bcid = client.post("/api/v1/asset-categories", headers=_h(tb), json={"name": "B类"}).json()["id"]
    assert client.get("/api/v1/teams", headers=_h(ta)).json() == []
    assert client.get("/api/v1/asset-categories", headers=_h(ta)).json() == []
    assert client.patch(f"/api/v1/teams/{btid}", headers=_h(ta), json={"name": "x"}).status_code == 404
    assert client.patch(f"/api/v1/asset-categories/{bcid}", headers=_h(ta),
                        json={"name": "x"}).status_code == 404


def test_custom_id_per_tenant_independent(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    a1 = client.post("/api/v1/assets", headers=_h(ta), json={"name": "x"}).json()["custom_id"]
    b1 = client.post("/api/v1/assets", headers=_h(tb), json={"name": "y"}).json()["custom_id"]
    assert a1 == "A000001" and b1 == "A000001"


def test_cross_tenant_downtime_404(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/assets", headers=_h(tb), json={"name": "B泵"}).json()["id"]
    assert client.post(f"/api/v1/assets/{bid}/downtimes", headers=_h(ta),
                       json={"started_at": "2026-05-30T08:00:00"}).status_code == 404
