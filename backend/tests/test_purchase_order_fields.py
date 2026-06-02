"""采购单扩展元数据字段（收货地址/方式/付款条款/预计交货日期）。

仅非货币字段；货币口径仍为 po_spend=Σlines，不在此引入任何金额字段。
"""

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


def test_po_create_with_metadata_fields(client):
    t = _admin(client)
    vid = _vendor(client, t)
    r = client.post(
        "/api/v1/purchase-orders",
        headers=_h(t),
        json={
            "vendor_id": vid,
            "shipping_address": "上海市浦东新区某路 1 号",
            "shipping_method": "陆运",
            "terms_of_payment": "月结 30 天",
            "expected_delivery_date": "2026-09-01",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["shipping_address"] == "上海市浦东新区某路 1 号"
    assert body["shipping_method"] == "陆运"
    assert body["terms_of_payment"] == "月结 30 天"
    assert body["expected_delivery_date"] == "2026-09-01"


def test_po_create_defaults_when_omitted(client):
    t = _admin(client)
    vid = _vendor(client, t)
    r = client.post(
        "/api/v1/purchase-orders",
        headers=_h(t),
        json={"vendor_id": vid},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["shipping_address"] == ""
    assert body["shipping_method"] == ""
    assert body["terms_of_payment"] == ""
    assert body["expected_delivery_date"] is None


def test_po_update_metadata_fields_in_draft(client):
    t = _admin(client)
    vid = _vendor(client, t)
    po_id = client.post(
        "/api/v1/purchase-orders",
        headers=_h(t),
        json={"vendor_id": vid},
    ).json()["id"]
    r = client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        headers=_h(t),
        json={
            "shipping_address": "北京市朝阳区某街 9 号",
            "shipping_method": "空运",
            "terms_of_payment": "预付 50%",
            "expected_delivery_date": "2026-10-15",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["shipping_address"] == "北京市朝阳区某街 9 号"
    assert body["shipping_method"] == "空运"
    assert body["terms_of_payment"] == "预付 50%"
    assert body["expected_delivery_date"] == "2026-10-15"
