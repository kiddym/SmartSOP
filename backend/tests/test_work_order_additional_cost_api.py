from __future__ import annotations


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t):
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def test_additional_cost_crud(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # 复用现有成本分类
    cat = client.post("/api/v1/cost-categories", json={"name": "差旅"}, headers=_h(t)).json()["id"]
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "打车", "amount": "33.50", "cost_category_id": cat},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert float(r.json()["amount"]) == 33.5
    assert r.json()["cost_category_id"] == cat
    lst = client.get(f"/api/v1/work-orders/{wo}/additional-costs", headers=_h(t)).json()
    assert len(lst) == 1
    upd = client.patch(
        f"/api/v1/work-orders/{wo}/additional-costs/{aid}",
        json={"amount": "40"},
        headers=_h(t),
    )
    assert float(upd.json()["amount"]) == 40.0
    assert (
        client.delete(
            f"/api/v1/work-orders/{wo}/additional-costs/{aid}", headers=_h(t)
        ).status_code
        == 204
    )


def test_additional_cost_no_category(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "杂费", "amount": "10"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    assert r.json()["cost_category_id"] is None


def test_additional_cost_negative_amount_422(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "x", "amount": "-1"},
        headers=_h(t),
    )
    assert r.status_code == 422


def test_additional_cost_tenant_isolation(client):
    a = _admin(client)
    wo = _wo_id(client, a)
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "x", "amount": "1"},
        headers=_h(a),
    )
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert (
        client.get(f"/api/v1/work-orders/{wo}/additional-costs", headers=_h(b)).status_code == 404
    )
