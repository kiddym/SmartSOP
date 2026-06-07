"""资产富字段（area/additional_infos/image_url）+ 资产侧对称维护
供应商/客户/备件 M:N 关联（全量替换 + 跨租户校验 + 清空语义）。"""

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


def _part(client, t, name="备件X"):
    return client.post("/api/v1/parts", headers=_h(t), json={"name": name, "quantity": "1"}).json()[
        "id"
    ]


def test_create_with_scalar_fields(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/assets",
        headers=_h(t),
        json={
            "name": "泵1",
            "area": "库区A",
            "additional_infos": "更多信息文本",
            "image_url": "/api/v1/assets/x/y",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["area"] == "库区A"
    assert body["additional_infos"] == "更多信息文本"
    assert body["image_url"] == "/api/v1/assets/x/y"
    # 读回
    got = client.get(f"/api/v1/assets/{body['id']}", headers=_h(t)).json()
    assert got["area"] == "库区A"
    assert got["additional_infos"] == "更多信息文本"
    assert got["image_url"] == "/api/v1/assets/x/y"


def test_scalar_fields_default_none(client):
    t = _admin(client)
    body = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵2"}).json()
    assert body["area"] is None
    assert body["additional_infos"] is None
    assert body["image_url"] is None
    assert body["vendor_ids"] == []
    assert body["customer_ids"] == []
    assert body["part_ids"] == []


def test_update_scalar_fields(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵3"}).json()["id"]
    r = client.patch(
        f"/api/v1/assets/{aid}",
        headers=_h(t),
        json={"area": "库区B", "additional_infos": "新", "image_url": "/img"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["area"] == "库区B"
    assert body["additional_infos"] == "新"
    assert body["image_url"] == "/img"


def test_create_with_partner_relations(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    p = _part(client, t)
    r = client.post(
        "/api/v1/assets",
        headers=_h(t),
        json={
            "name": "泵4",
            "vendor_ids": [v],
            "customer_ids": [c],
            "part_ids": [p],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["vendor_ids"] == [v]
    assert body["customer_ids"] == [c]
    assert body["part_ids"] == [p]
    # 读回
    got = client.get(f"/api/v1/assets/{body['id']}", headers=_h(t)).json()
    assert got["vendor_ids"] == [v]
    assert got["customer_ids"] == [c]
    assert got["part_ids"] == [p]


def test_update_replaces_relations(client):
    t = _admin(client)
    v1, v2 = _vendor(client, t, "V1"), _vendor(client, t, "V2")
    aid = client.post(
        "/api/v1/assets", headers=_h(t), json={"name": "泵5", "vendor_ids": [v1]}
    ).json()["id"]
    r = client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"vendor_ids": [v2]})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v2]


def test_update_clear_relations_with_empty_list(client):
    t = _admin(client)
    v = _vendor(client, t)
    c = _customer(client, t)
    p = _part(client, t)
    aid = client.post(
        "/api/v1/assets",
        headers=_h(t),
        json={"name": "泵6", "vendor_ids": [v], "customer_ids": [c], "part_ids": [p]},
    ).json()["id"]
    r = client.patch(
        f"/api/v1/assets/{aid}",
        headers=_h(t),
        json={"vendor_ids": [], "customer_ids": [], "part_ids": []},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vendor_ids"] == []
    assert body["customer_ids"] == []
    assert body["part_ids"] == []


def test_update_none_leaves_relations_unchanged(client):
    t = _admin(client)
    v = _vendor(client, t)
    aid = client.post(
        "/api/v1/assets", headers=_h(t), json={"name": "泵7", "vendor_ids": [v]}
    ).json()["id"]
    # 不传 vendor_ids -> 不改
    r = client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"area": "X"})
    assert r.status_code == 200, r.text
    assert r.json()["vendor_ids"] == [v]


def test_cross_tenant_vendor_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    r = client.post("/api/v1/assets", headers=_h(tb), json={"name": "泵", "vendor_ids": [v_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"


def test_cross_tenant_customer_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    c_a = _customer(client, ta)
    r = client.post("/api/v1/assets", headers=_h(tb), json={"name": "泵", "customer_ids": [c_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_cross_tenant_part_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    p_a = _part(client, ta)
    r = client.post("/api/v1/assets", headers=_h(tb), json={"name": "泵", "part_ids": [p_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "PART_NOT_FOUND"


def test_cross_tenant_rejected_on_update(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    v_a = _vendor(client, ta)
    aid = client.post("/api/v1/assets", headers=_h(tb), json={"name": "泵"}).json()["id"]
    r = client.patch(f"/api/v1/assets/{aid}", headers=_h(tb), json={"vendor_ids": [v_a]})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "VENDOR_NOT_FOUND"
