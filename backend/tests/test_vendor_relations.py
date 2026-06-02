"""Vendor↔asset + Vendor↔location 关联：内嵌 asset_ids/location_ids + 同步 + 跨租户校验。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _asset(client, t, name="泵A"):
    return client.post("/api/v1/assets", headers=_h(t), json={"name": name}).json()["id"]


def _loc(client, t, name="车间A"):
    return client.post("/api/v1/locations", headers=_h(t), json={"name": name}).json()["id"]


def _vendor(client, t, name="供应商X", **extra):
    return client.post("/api/v1/vendors", headers=_h(t), json={"name": name, **extra})


def test_create_with_asset_and_location(client):
    t = _admin(client)
    a = _asset(client, t)
    loc = _loc(client, t)
    r = _vendor(client, t, asset_ids=[a], location_ids=[loc])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["asset_ids"] == [a]
    assert body["location_ids"] == [loc]


def test_update_replaces_and_clears(client):
    t = _admin(client)
    a1, a2 = _asset(client, t, "泵1"), _asset(client, t, "泵2")
    l1, l2 = _loc(client, t, "A"), _loc(client, t, "B")
    vid = _vendor(client, t, asset_ids=[a1], location_ids=[l1]).json()["id"]
    r = client.patch(
        f"/api/v1/vendors/{vid}",
        headers=_h(t),
        json={"asset_ids": [a2], "location_ids": [l2]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["asset_ids"] == [a2]
    assert r.json()["location_ids"] == [l2]
    r2 = client.patch(
        f"/api/v1/vendors/{vid}",
        headers=_h(t),
        json={"asset_ids": [], "location_ids": []},
    )
    assert r2.json()["asset_ids"] == []
    assert r2.json()["location_ids"] == []


def test_cross_tenant_asset_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    asset_a = _asset(client, ta, "A泵")
    r = _vendor(client, tb, asset_ids=[asset_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "ASSET_NOT_FOUND"


def test_cross_tenant_location_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    loc_a = _loc(client, ta, "A库")
    r = _vendor(client, tb, location_ids=[loc_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "LOCATION_NOT_FOUND"
