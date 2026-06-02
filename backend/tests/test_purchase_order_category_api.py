"""采购单分类 API（/api/v1/purchase-order-categories）+ PO.category_id 接线。"""

from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "tech@acme.com", "password": "secret123"},
    ).json()["access_token"]


def _vendor_id(client, t, name="供应商A"):
    return client.post("/api/v1/vendors", json={"name": name}, headers=_h(t)).json()["id"]


def test_category_crud(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/purchase-order-categories",
        json={"name": "办公用品", "description": "d"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["name"] == "办公用品"
    # list 含
    lst = client.get("/api/v1/purchase-order-categories", headers=_h(t))
    assert lst.status_code == 200
    assert any(c["id"] == cid for c in lst.json())
    # get
    assert client.get(
        f"/api/v1/purchase-order-categories/{cid}", headers=_h(t)
    ).status_code == 200
    # patch 改名
    upd = client.patch(
        f"/api/v1/purchase-order-categories/{cid}", json={"name": "耗材"}, headers=_h(t)
    )
    assert upd.status_code == 200 and upd.json()["name"] == "耗材"
    # delete
    assert client.delete(
        f"/api/v1/purchase-order-categories/{cid}", headers=_h(t)
    ).status_code == 204
    # 软删后不可见
    assert client.get(
        f"/api/v1/purchase-order-categories/{cid}", headers=_h(t)
    ).status_code == 404
    assert all(c["id"] != cid for c in client.get(
        "/api/v1/purchase-order-categories", headers=_h(t)
    ).json())


def test_category_duplicate_name_409(client):
    t = _admin(client)
    first = client.post(
        "/api/v1/purchase-order-categories", json={"name": "重复"}, headers=_h(t)
    )
    assert first.status_code == 201
    dup = client.post(
        "/api/v1/purchase-order-categories", json={"name": "重复"}, headers=_h(t)
    )
    assert dup.status_code == 409, dup.text
    assert dup.json()["detail"]["code"] == "PURCHASE_ORDER_CATEGORY_DUPLICATE"


def test_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post(
        "/api/v1/purchase-order-categories", json={"name": "X"}, headers=_h(a)
    ).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    g = client.get(f"/api/v1/purchase-order-categories/{cid}", headers=_h(b))
    assert g.status_code == 404
    assert g.json()["detail"]["code"] == "PURCHASE_ORDER_CATEGORY_NOT_FOUND"
    p = client.patch(
        f"/api/v1/purchase-order-categories/{cid}", json={"name": "Y"}, headers=_h(b)
    )
    assert p.status_code == 404
    d = client.delete(f"/api/v1/purchase-order-categories/{cid}", headers=_h(b))
    assert d.status_code == 404


def test_category_technician_permissions(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    # technician 有 view 无 manage
    assert client.get(
        "/api/v1/purchase-order-categories", headers=_h(tech)
    ).status_code == 200
    cid = client.post(
        "/api/v1/purchase-order-categories", json={"name": "Z"}, headers=_h(admin)
    ).json()["id"]
    assert client.get(
        f"/api/v1/purchase-order-categories/{cid}", headers=_h(tech)
    ).status_code == 200
    assert client.post(
        "/api/v1/purchase-order-categories", json={"name": "no"}, headers=_h(tech)
    ).status_code == 403
    assert client.patch(
        f"/api/v1/purchase-order-categories/{cid}", json={"name": "no"}, headers=_h(tech)
    ).status_code == 403
    assert client.delete(
        f"/api/v1/purchase-order-categories/{cid}", headers=_h(tech)
    ).status_code == 403


def test_po_create_with_category(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    cid = client.post(
        "/api/v1/purchase-order-categories", json={"name": "采购类"}, headers=_h(t)
    ).json()["id"]
    r = client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": v, "category_id": cid, "notes": ""},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category_id"] == cid


def test_po_create_with_foreign_category_404(client):
    a = _admin(client)
    cid = client.post(
        "/api/v1/purchase-order-categories", json={"name": "A类"}, headers=_h(a)
    ).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    vb = _vendor_id(client, b)
    r = client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": vb, "category_id": cid},
        headers=_h(b),
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "PURCHASE_ORDER_CATEGORY_NOT_FOUND"


def test_po_update_category(client):
    t = _admin(client)
    v = _vendor_id(client, t)
    c1 = client.post(
        "/api/v1/purchase-order-categories", json={"name": "c1"}, headers=_h(t)
    ).json()["id"]
    c2 = client.post(
        "/api/v1/purchase-order-categories", json={"name": "c2"}, headers=_h(t)
    ).json()["id"]
    pid = client.post(
        "/api/v1/purchase-orders",
        json={"vendor_id": v, "category_id": c1},
        headers=_h(t),
    ).json()["id"]
    upd = client.patch(
        f"/api/v1/purchase-orders/{pid}", json={"category_id": c2}, headers=_h(t)
    )
    assert upd.status_code == 200 and upd.json()["category_id"] == c2
    # 清空
    clr = client.patch(
        f"/api/v1/purchase-orders/{pid}", json={"category_id": None}, headers=_h(t)
    )
    assert clr.status_code == 200 and clr.json()["category_id"] is None
