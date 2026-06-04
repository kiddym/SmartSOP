"""工单关联 API 测试（Task 4）。"""


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _wo(client, h, title):
    return client.post("/api/v1/work-orders", headers=h, json={"title": title}).json()["id"]


def test_create_and_list_symmetric(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "RELATED"},
    )
    assert r.status_code == 201, r.text
    la = client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json()
    assert len(la) == 1
    assert la[0]["relation_type"] == "RELATED"
    assert la[0]["direction"] == "symmetric"
    assert la[0]["related_work_order_id"] == b
    lb = client.get(f"/api/v1/work-orders/{b}/relations", headers=h).json()
    assert len(lb) == 1
    assert lb[0]["related_work_order_id"] == a
    assert lb[0]["direction"] == "symmetric"


def test_directed_blocks_direction(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "BLOCKS"},
    )
    la = client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json()
    assert la[0]["direction"] == "outgoing"
    lb = client.get(f"/api/v1/work-orders/{b}/relations", headers=h).json()
    assert lb[0]["direction"] == "incoming"


def test_self_relation_rejected(client):
    t = _admin(client)
    h = _h(t)
    a = _wo(client, h, "A")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": a, "relation_type": "RELATED"},
    )
    assert r.status_code == 400


def test_duplicate_rejected(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    body = {"target_work_order_id": b, "relation_type": "RELATED"}
    client.post(f"/api/v1/work-orders/{a}/relations", headers=h, json=body)
    r = client.post(f"/api/v1/work-orders/{a}/relations", headers=h, json=body)
    assert r.status_code == 409


def test_cross_tenant_target_404(client):
    ta = _admin(client, "Acme", "a@a.com")
    tb = _admin(client, "Beta", "b@b.com")
    a = _wo(client, _h(ta), "A")
    b_other = _wo(client, _h(tb), "B")
    r = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=_h(ta),
        json={"target_work_order_id": b_other, "relation_type": "RELATED"},
    )
    assert r.status_code == 404


def test_delete_relation(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    rid = client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "RELATED"},
    ).json()["id"]
    d = client.delete(f"/api/v1/work-orders/{a}/relations/{rid}", headers=h)
    assert d.status_code == 204
    assert client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json() == []


def test_symmetric_reverse_duplicate_rejected(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "RELATED"},
    )
    # reverse direction, same symmetric type → duplicate
    r = client.post(
        f"/api/v1/work-orders/{b}/relations",
        headers=h,
        json={"target_work_order_id": a, "relation_type": "RELATED"},
    )
    assert r.status_code == 409, r.text


def test_directed_reverse_is_allowed(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "BLOCKS"},
    )
    # reverse direction of a DIRECTED type is a distinct relation → allowed (201)
    r = client.post(
        f"/api/v1/work-orders/{b}/relations",
        headers=h,
        json={"target_work_order_id": a, "relation_type": "BLOCKS"},
    )
    assert r.status_code == 201, r.text


def test_split_is_directed(client):
    t = _admin(client)
    h = _h(t)
    a, b = _wo(client, h, "A"), _wo(client, h, "B")
    client.post(
        f"/api/v1/work-orders/{a}/relations",
        headers=h,
        json={"target_work_order_id": b, "relation_type": "SPLIT"},
    )
    assert (
        client.get(f"/api/v1/work-orders/{a}/relations", headers=h).json()[0]["direction"]
        == "outgoing"
    )
    assert (
        client.get(f"/api/v1/work-orders/{b}/relations", headers=h).json()[0]["direction"]
        == "incoming"
    )
