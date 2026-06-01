"""备件分类 API（Phase 3A）。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def test_part_category_crud(client):
    t = _admin(client)
    r = client.post("/api/v1/part-categories", json={"name": "轴承类"}, headers=_h(t))
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert client.get("/api/v1/part-categories", headers=_h(t)).status_code == 200
    upd = client.patch(f"/api/v1/part-categories/{cid}", json={"name": "改名"}, headers=_h(t))
    assert upd.json()["name"] == "改名"
    assert client.delete(f"/api/v1/part-categories/{cid}", headers=_h(t)).status_code == 204


def test_part_category_tenant_isolation(client):
    a = _admin(client)
    cid = client.post("/api/v1/part-categories", json={"name": "X"}, headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/part-categories/{cid}", headers=_h(b)).status_code == 404
