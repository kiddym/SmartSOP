"""采购单收货信息细化字段（收件人/收货公司/城市/州省/邮编/电话/传真/申购人）。

全可空标量；保留既有 shipping_address/shipping_method/terms_of_payment/
expected_delivery_date（不改语义）。不引入任何金额字段。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")

_SHIPPING = {
    "shipping_to_name": "张三",
    "shipping_company_name": "收货公司有限公司",
    "shipping_city": "上海",
    "shipping_state": "上海市",
    "shipping_zip_code": "200120",
    "shipping_phone": "021-12345678",
    "shipping_fax": "021-87654321",
    "requisitioned_by_name": "李四",
}


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _vendor(client, t, name="供应商X"):
    return client.post("/api/v1/vendors", headers=_h(t), json={"name": name}).json()["id"]


def test_po_create_with_shipping_detail_fields(client):
    t = _admin(client)
    vid = _vendor(client, t)
    r = client.post(
        "/api/v1/purchase-orders",
        headers=_h(t),
        json={"vendor_id": vid, **_SHIPPING},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    for k, v in _SHIPPING.items():
        assert body[k] == v
    # 既有字段不受影响
    assert body["shipping_address"] == ""


def test_po_create_shipping_detail_null_when_omitted(client):
    t = _admin(client)
    vid = _vendor(client, t)
    r = client.post("/api/v1/purchase-orders", headers=_h(t), json={"vendor_id": vid})
    assert r.status_code == 201, r.text
    body = r.json()
    for k in _SHIPPING:
        assert body[k] is None


def test_po_update_shipping_detail_fields_in_draft(client):
    t = _admin(client)
    vid = _vendor(client, t)
    po_id = client.post(
        "/api/v1/purchase-orders", headers=_h(t), json={"vendor_id": vid}
    ).json()["id"]
    r = client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        headers=_h(t),
        json=_SHIPPING,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k, v in _SHIPPING.items():
        assert body[k] == v
    # 读回确认持久化
    got = client.get(f"/api/v1/purchase-orders/{po_id}", headers=_h(t)).json()
    for k, v in _SHIPPING.items():
        assert got[k] == v
