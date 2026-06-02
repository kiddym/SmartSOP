"""工单 category_id / created_by_user_id 接线 + 跨租户分类校验。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _me_id(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()["id"]


def _category(client, token, name="保养"):
    return client.post(
        "/api/v1/work-order-categories", headers=_h(token), json={"name": name}
    ).json()["id"]


def test_create_stamps_created_by_and_category(client):
    t = _admin(client)
    me = _me_id(client, t)
    cid = _category(client, t)
    r = client.post(
        "/api/v1/work-orders", headers=_h(t), json={"title": "维修", "category_id": cid}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category_id"] == cid
    assert body["created_by_user_id"] == me


def test_patch_category(client):
    t = _admin(client)
    cid = _category(client, t)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "x"}).json()["id"]
    r = client.patch(
        f"/api/v1/work-orders/{wid}", headers=_h(t), json={"category_id": cid}
    )
    assert r.json()["category_id"] == cid


def test_cross_tenant_category_rejected(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    cid_a = _category(client, ta, "A分类")
    r = client.post(
        "/api/v1/work-orders", headers=_h(tb), json={"title": "x", "category_id": cid_a}
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "WORK_ORDER_CATEGORY_NOT_FOUND"
