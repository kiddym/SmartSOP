"""多备件套件 API（Phase 3A）。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _part_id(client, t, name="轴承"):
    return client.post("/api/v1/parts", json={"name": name, "quantity": "1"}, headers=_h(t)).json()[
        "id"
    ]


def test_multipart_crud(client):
    t = _admin(client)
    p1, p2 = _part_id(client, t, "A"), _part_id(client, t, "B")
    r = client.post(
        "/api/v1/multi-parts", json={"name": "套件", "part_ids": [p1, p2]}, headers=_h(t)
    )
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["custom_id"] == "KIT000001"
    assert set(r.json()["part_ids"]) == {p1, p2}
    upd = client.patch(f"/api/v1/multi-parts/{mid}", json={"part_ids": [p1]}, headers=_h(t))
    assert upd.json()["part_ids"] == [p1]
    assert len(client.get("/api/v1/multi-parts", headers=_h(t)).json()) == 1
    assert client.delete(f"/api/v1/multi-parts/{mid}", headers=_h(t)).status_code == 204


def test_multipart_tenant_isolation(client):
    a = _admin(client)
    mid = client.post("/api/v1/multi-parts", json={"name": "X"}, headers=_h(a)).json()["id"]
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/multi-parts/{mid}", headers=_h(b)).status_code == 404
