"""备件富字段（area/additional_infos）+ 备件侧对称维护供应商/客户 M:N 关联
（全量替换 + 跨租户校验 + 清空语义）。关联表复用 tb_vendor_part/tb_customer_part。"""

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


def _part(client, t, **extra):
    body = {"name": "备件A", **extra}
    return client.post("/api/v1/parts", headers=_h(t), json=body)


def test_create_with_scalars(client):
    t = _admin(client)
    r = _part(client, t, area="A区-3排", additional_infos="易碎，轻拿轻放")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["area"] == "A区-3排"
    assert body["additional_infos"] == "易碎，轻拿轻放"
    got = client.get(f"/api/v1/parts/{body['id']}", headers=_h(t)).json()
    assert got["area"] == "A区-3排"
    assert got["additional_infos"] == "易碎，轻拿轻放"


def test_scalar_defaults_none_and_empty_relations(client):
    t = _admin(client)
    body = _part(client, t).json()
    assert body["area"] is None
    assert body["additional_infos"] is None
    assert body["vendor_ids"] == []
    assert body["customer_ids"] == []


def test_update_scalars(client):
    t = _admin(client)
    pid = _part(client, t).json()["id"]
    r = client.patch(
        f"/api/v1/parts/{pid}",
        headers=_h(t),
        json={"area": "B区", "additional_infos": "更新说明"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["area"] == "B区"
    assert r.json()["additional_infos"] == "更新说明"


def test_create_with_partner_relations(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    r = _part(client, t, vendor_ids=[v], customer_ids=[c])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vendor_ids"] == [v]
    assert body["customer_ids"] == [c]
    got = client.get(f"/api/v1/parts/{body['id']}", headers=_h(t)).json()
    assert got["vendor_ids"] == [v]
    assert got["customer_ids"] == [c]


def test_relation_visible_from_vendor_side(client):
    """备件侧设关联后，供应商侧反查 part_ids 对称可见。"""
    t = _admin(client)
    v = _vendor(client, t)
    pid = _part(client, t, vendor_ids=[v]).json()["id"]
    vendor = client.get(f"/api/v1/vendors/{v}", headers=_h(t)).json()
    assert vendor["part_ids"] == [pid]


def test_relation_visible_from_customer_side(client):
    """备件侧设关联后，客户侧反查 part_ids 对称可见。"""
    t = _admin(client)
    c = _customer(client, t)
    pid = _part(client, t, customer_ids=[c]).json()["id"]
    customer = client.get(f"/api/v1/customers/{c}", headers=_h(t)).json()
    assert customer["part_ids"] == [pid]


def test_update_replaces_relations(client):
    t = _admin(client)
    v1, v2 = _vendor(client, t, "V1"), _vendor(client, t, "V2")
    pid = _part(client, t, vendor_ids=[v1]).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"vendor_ids": [v2]})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v2]


def test_update_clear_relations_with_empty_list(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    pid = _part(client, t, vendor_ids=[v], customer_ids=[c]).json()["id"]
    r = client.patch(
        f"/api/v1/parts/{pid}",
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
    pid = _part(client, t, vendor_ids=[v]).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(t), json={"unit": "个"})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v]


def test_cross_tenant_vendor_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    r = _part(client, tb, vendor_ids=[v_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"


def test_cross_tenant_customer_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    c_a = _customer(client, ta)
    r = _part(client, tb, customer_ids=[c_a])
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_cross_tenant_rejected_on_update(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    pid = _part(client, tb).json()["id"]
    r = client.patch(f"/api/v1/parts/{pid}", headers=_h(tb), json={"vendor_ids": [v_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"
