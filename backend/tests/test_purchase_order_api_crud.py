"""采购单 API CRUD（Phase 3C）。"""

from __future__ import annotations

from decimal import Decimal


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _vendor_id(client, t, name="供应商A"):
    return client.post("/api/v1/vendors", json={"name": name}, headers=_h(t)).json()["id"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"}, headers=_h(t)).json()[
        "id"
    ]


def test_po_crud_and_lines(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    p = _part_id(client, t)
    r = client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": v,
            "notes": "n",
            "lines": [{"part_id": p, "quantity": "3", "unit_cost": "2"}],
        },
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    pid = body["id"]
    assert body["custom_id"].startswith("PO") and body["status"] == "DRAFT"
    assert Decimal(str(body["lines"][0]["line_total"])) == Decimal("6")
    assert Decimal(str(body["total_cost"])) == Decimal("6")
    got = client.get(f"/api/v1/purchase-orders/{pid}", headers=_h(t))
    assert got.status_code == 200 and got.json()["vendor_id"] == v
    upd = client.patch(
        f"/api/v1/purchase-orders/{pid}", json={"notes": "n2", "lines": []}, headers=_h(t)
    )
    assert upd.json()["notes"] == "n2" and upd.json()["lines"] == []
    assert client.delete(f"/api/v1/purchase-orders/{pid}", headers=_h(t)).status_code == 204


def test_po_list_filter_by_vendor(client):
    t = _admin(client)
    v1, v2 = _vendor_id(client, t, "V1"), _vendor_id(client, t, "V2")
    client.post("/api/v1/purchase-orders", json={"vendor_id": v1}, headers=_h(t))
    client.post("/api/v1/purchase-orders", json={"vendor_id": v2}, headers=_h(t))
    got = client.get(f"/api/v1/purchase-orders?vendor_id={v1}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["vendor_id"] == v1


def test_po_mini(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(t))
    mini = client.get("/api/v1/purchase-orders/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "custom_id", "vendor_id", "status"}


def test_po_tenant_isolation(client):
    a = _admin(client)
    v = _vendor_id(client, a)
    pid = client.post("/api/v1/purchase-orders", json={"vendor_id": v}, headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/purchase-orders/{pid}", headers=_h(b)).status_code == 404
