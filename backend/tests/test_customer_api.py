"""客户 API（Phase 3B）。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


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


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"}, headers=_h(t)).json()[
        "id"
    ]


def test_customer_crud_and_currency(client):
    t = _admin(client)
    p1 = _part_id(client, t, "A")
    r = client.post(
        "/api/v1/customers",
        json={"name": "客户A", "billing_currency": "CNY", "part_ids": [p1]},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["billing_currency"] == "CNY" and r.json()["part_ids"] == [p1]
    upd = client.patch(f"/api/v1/customers/{cid}", json={"billing_currency": "USD"}, headers=_h(t))
    assert upd.json()["billing_currency"] == "USD"
    assert client.delete(f"/api/v1/customers/{cid}", headers=_h(t)).status_code == 204


def test_customer_billing_fields_create_update_readback(client):
    t = _admin(client)
    r = client.post(
        "/api/v1/customers",
        json={
            "name": "账单客户",
            "billing_currency": "CNY",
            "billing_name": "结算抬头",
            "billing_address": "上海市浦东新区某路 1 号",
            "billing_address2": "B 座 18 楼",
        },
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["billing_name"] == "结算抬头"
    assert r.json()["billing_address"] == "上海市浦东新区某路 1 号"
    assert r.json()["billing_address2"] == "B 座 18 楼"
    upd = client.patch(
        f"/api/v1/customers/{cid}",
        json={"billing_name": "新抬头", "billing_address2": "C 座 9 楼"},
        headers=_h(t),
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["billing_name"] == "新抬头"
    assert upd.json()["billing_address"] == "上海市浦东新区某路 1 号"
    assert upd.json()["billing_address2"] == "C 座 9 楼"
    got = client.get(f"/api/v1/customers/{cid}", headers=_h(t)).json()
    assert got["billing_name"] == "新抬头"


def test_customer_billing_fields_null_when_omitted(client):
    t = _admin(client)
    r = client.post("/api/v1/customers", json={"name": "无账单客户"}, headers=_h(t))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["billing_name"] is None
    assert body["billing_address"] is None
    assert body["billing_address2"] is None


def test_customer_filter_by_part(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    client.post("/api/v1/customers", json={"name": "C1", "part_ids": [p1]}, headers=_h(t))
    client.post("/api/v1/customers", json={"name": "C2", "part_ids": [p2]}, headers=_h(t))
    got = client.get(f"/api/v1/customers?part_id={p2}", headers=_h(t)).json()
    assert len(got) == 1 and got[0]["name"] == "C2"


def test_customer_mini(client):
    t = _admin(client)
    client.post("/api/v1/customers", json={"name": "客户A"}, headers=_h(t))
    mini = client.get("/api/v1/customers/mini", headers=_h(t))
    assert mini.status_code == 200, mini.text
    assert set(mini.json()[0].keys()) == {"id", "name"}
    assert mini.json()[0]["name"] == "客户A"


def test_technician_can_view_not_create(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    client.post("/api/v1/customers", json={"name": "客户A"}, headers=_h(admin))
    assert client.get("/api/v1/customers", headers=_h(tech)).status_code == 200
    assert client.post("/api/v1/customers", json={"name": "x"}, headers=_h(tech)).status_code == 403


def test_customer_tenant_isolation(client):
    a = _admin(client)
    cid = client.post("/api/v1/customers", json={"name": "客户A"}, headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/customers/{cid}", headers=_h(b)).status_code == 404
