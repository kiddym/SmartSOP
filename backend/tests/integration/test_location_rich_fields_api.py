"""位置富字段（image_url）+ 位置侧对称维护供应商/客户 M:N 关联
（全量替换 + 跨租户校验 + 清空语义）。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _vendor(client, t, name="供应商X"):
    return client.post("/api/v1/vendors", headers=_h(t), json={"name": name}).json()["id"]


def _customer(client, t, name="客户X"):
    return client.post("/api/v1/customers", headers=_h(t), json={"name": name}).json()["id"]


def test_create_with_image_url(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/locations",
        headers=_h(t),
        json={"name": "厂区1", "image_url": "/api/v1/locations/x/y"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["image_url"] == "/api/v1/locations/x/y"
    got = client.get(f"/api/v1/locations/{body['id']}", headers=_h(t)).json()
    assert got["image_url"] == "/api/v1/locations/x/y"


def test_scalar_defaults_none_and_empty_relations(client):
    t = _admin(client)
    body = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区2"}).json()
    assert body["image_url"] is None
    assert body["vendor_ids"] == []
    assert body["customer_ids"] == []


def test_update_image_url(client):
    t = _admin(client)
    lid = client.post("/api/v1/locations", headers=_h(t), json={"name": "厂区3"}).json()["id"]
    r = client.patch(f"/api/v1/locations/{lid}", headers=_h(t), json={"image_url": "/img"})
    assert r.status_code == 200, r.text
    assert r.json()["image_url"] == "/img"


def test_create_with_partner_relations(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    r = client.post(
        "/api/v1/locations",
        headers=_h(t),
        json={"name": "厂区4", "vendor_ids": [v], "customer_ids": [c]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vendor_ids"] == [v]
    assert body["customer_ids"] == [c]
    got = client.get(f"/api/v1/locations/{body['id']}", headers=_h(t)).json()
    assert got["vendor_ids"] == [v]
    assert got["customer_ids"] == [c]


def test_relation_visible_from_vendor_side(client):
    """位置侧设关联后，供应商侧反查 location_ids 对称可见。"""
    t = _admin(client)
    v = _vendor(client, t)
    lid = client.post(
        "/api/v1/locations", headers=_h(t), json={"name": "厂区5", "vendor_ids": [v]}
    ).json()["id"]
    vendor = client.get(f"/api/v1/vendors/{v}", headers=_h(t)).json()
    assert vendor["location_ids"] == [lid]


def test_update_replaces_relations(client):
    t = _admin(client)
    v1, v2 = _vendor(client, t, "V1"), _vendor(client, t, "V2")
    lid = client.post(
        "/api/v1/locations", headers=_h(t), json={"name": "厂区6", "vendor_ids": [v1]}
    ).json()["id"]
    r = client.patch(f"/api/v1/locations/{lid}", headers=_h(t), json={"vendor_ids": [v2]})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v2]


def test_update_clear_relations_with_empty_list(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    lid = client.post(
        "/api/v1/locations",
        headers=_h(t),
        json={"name": "厂区7", "vendor_ids": [v], "customer_ids": [c]},
    ).json()["id"]
    r = client.patch(
        f"/api/v1/locations/{lid}",
        headers=_h(t),
        json={"vendor_ids": [], "customer_ids": []},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vendor_ids"] == []
    assert body["customer_ids"] == []


def test_update_none_leaves_relations_unchanged(client):
    t = _admin(client)
    v = _vendor(client, t)
    lid = client.post(
        "/api/v1/locations", headers=_h(t), json={"name": "厂区8", "vendor_ids": [v]}
    ).json()["id"]
    r = client.patch(f"/api/v1/locations/{lid}", headers=_h(t), json={"address": "X"})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v]


def test_cross_tenant_vendor_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    r = client.post("/api/v1/locations", headers=_h(tb), json={"name": "厂区", "vendor_ids": [v_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"


def test_cross_tenant_customer_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    c_a = _customer(client, ta)
    r = client.post(
        "/api/v1/locations", headers=_h(tb), json={"name": "厂区", "customer_ids": [c_a]}
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_cross_tenant_rejected_on_update(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    lid = client.post("/api/v1/locations", headers=_h(tb), json={"name": "厂区"}).json()["id"]
    r = client.patch(f"/api/v1/locations/{lid}", headers=_h(tb), json={"vendor_ids": [v_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"
