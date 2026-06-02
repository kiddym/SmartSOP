"""Part↔location 关联：内嵌 location_ids + 同步 + 跨租户校验。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _loc(client, t, name="车间A"):
    return client.post("/api/v1/locations", headers=_h(t), json={"name": name}).json()["id"]


def _part(client, t, name="轴承", **extra):
    return client.post("/api/v1/parts", headers=_h(t), json={"name": name, **extra})


def test_create_with_locations(client):
    t = _admin(client)
    loc = _loc(client, t)
    r = _part(client, t, location_ids=[loc])
    assert r.status_code == 201, r.text
    assert r.json()["location_ids"] == [loc]


def test_update_replaces_locations(client):
    t = _admin(client)
    l1, l2 = _loc(client, t, "A"), _loc(client, t, "B")
    pid = _part(client, t, location_ids=[l1]).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"location_ids": [l2]})
    assert r.json()["location_ids"] == [l2]
    r2 = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"location_ids": []})
    assert r2.json()["location_ids"] == []


def test_cross_tenant_location_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    loc_a = _loc(client, ta, "A库")
    r = _part(client, tb, location_ids=[loc_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "LOCATION_NOT_FOUND"
