def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_list_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵1"}).json()
    assert a["custom_id"] == "A000001"
    assert a["status"] == "OPERATIONAL"
    names = {x["name"] for x in client.get("/api/v1/assets", headers=_h(t)).json()}
    assert names == {"泵1"}


def test_by_barcode_and_nfc(client):
    t = _admin(client)
    client.post(
        "/api/v1/assets", headers=_h(t), json={"name": "泵", "barcode": "BC1", "nfc_id": "N1"}
    )
    assert client.get("/api/v1/assets/by-barcode/BC1", headers=_h(t)).json()["name"] == "泵"
    assert client.get("/api/v1/assets/by-nfc/N1", headers=_h(t)).json()["name"] == "泵"
    assert client.get("/api/v1/assets/by-barcode/nope", headers=_h(t)).status_code == 404


def test_barcode_conflict_409(client):
    t = _admin(client)
    client.post("/api/v1/assets", headers=_h(t), json={"name": "泵1", "barcode": "DUP"})
    r = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵2", "barcode": "DUP"})
    assert r.status_code == 409, r.text


def test_filter_by_status_and_children(client):
    t = _admin(client)
    root = client.post("/api/v1/assets", headers=_h(t), json={"name": "根"}).json()
    client.post("/api/v1/assets", headers=_h(t), json={"name": "子", "parent_id": root["id"]})
    kids = client.get(f"/api/v1/assets/{root['id']}/children", headers=_h(t)).json()
    assert {k["name"] for k in kids} == {"子"}
    down = client.get("/api/v1/assets?status=DOWN", headers=_h(t)).json()
    assert down == []


def test_downtime_register_and_close(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    r = client.post(
        f"/api/v1/assets/{aid}/downtimes",
        headers=_h(t),
        json={"started_at": "2026-05-30T08:00:00", "reason": "故障"},
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert r.json()["ended_at"] is None
    r2 = client.patch(
        f"/api/v1/assets/{aid}/downtimes/{did}",
        headers=_h(t),
        json={"ended_at": "2026-05-30T10:00:00"},
    )
    assert r2.status_code == 200
    assert r2.json()["ended_at"].startswith("2026-05-30T10:00:00")
    lst = client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()
    assert len(lst) == 1


def test_technician_can_edit_not_delete(client):
    admin = _admin(client)
    client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T"},
    )
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    tech_role = next(r for r in roles if r["code"] == "technician")["id"]
    uid = next(
        u
        for u in client.get("/api/v1/users", headers=_h(admin)).json()
        if u["email"] == "tech@acme.com"
    )["id"]
    client.patch(f"/api/v1/users/{uid}", headers=_h(admin), json={"role_id": tech_role})
    tech = client.post(
        "/api/v1/auth/login",
        json={"email": "tech@acme.com", "password": "secret123", "company_slug": "acme"},
    ).json()["access_token"]
    aid = client.post("/api/v1/assets", headers=_h(admin), json={"name": "泵"}).json()["id"]
    assert (
        client.patch(f"/api/v1/assets/{aid}", headers=_h(tech), json={"status": "DOWN"}).status_code
        == 200
    )
    assert client.delete(f"/api/v1/assets/{aid}", headers=_h(tech)).status_code == 403


def test_requires_auth(client):
    assert client.get("/api/v1/assets").status_code == 401
