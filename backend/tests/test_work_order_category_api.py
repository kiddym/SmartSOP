"""工单分类 CRUD：鉴权/RBAC/软删/重名/跨租户。镜像 time-categories。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _create(client, token, name="保养"):
    return client.post(
        "/api/v1/work-order-categories", headers=_h(token), json={"name": name}
    )


def test_requires_auth(client):
    assert client.get("/api/v1/work-order-categories").status_code == 401


def test_crud_roundtrip(client):
    t = _admin(client)
    r = _create(client, t, "保养")
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["name"] == "保养"
    assert client.get("/api/v1/work-order-categories", headers=_h(t)).json()[0]["id"] == cid
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 200
    assert (
        client.patch(
            f"/api/v1/work-order-categories/{cid}", headers=_h(t), json={"name": "校准"}
        ).json()["name"]
        == "校准"
    )
    assert (
        client.delete(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 204
    )
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(t)).status_code == 404


def test_duplicate_name_conflict(client):
    t = _admin(client)
    _create(client, t, "保养")
    assert _create(client, t, "保养").status_code == 409


def test_cross_tenant_isolation(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    cid = _create(client, ta, "A的分类").json()["id"]
    assert client.get(f"/api/v1/work-order-categories/{cid}", headers=_h(tb)).status_code == 404
    assert client.get("/api/v1/work-order-categories", headers=_h(tb)).json() == []
