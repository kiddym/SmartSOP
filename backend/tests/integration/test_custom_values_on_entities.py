"""WorkOrder custom_values 接入集成测试。

本文件为 Tasks 6–9（asset/request/location/part）逐实体追加的起点。
每个测试覆盖三要素：① 写前校验（未知 key / 必填缺失各 422）；
② roundtrip（建单含值 → GET 取回）；③ update 走 key 级合并（保留归档字段值）。
"""


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _def(client, h, entity_type, key="note", field_type="text", required=False, options=None):
    return client.post(
        "/api/v1/custom-fields",
        headers=h,
        json={
            "entity_type": entity_type,
            "key": key,
            "name": key,
            "field_type": field_type,
            "required": required,
            "options": options or [],
        },
    ).json()


# ---------------------------------------------------------------------------
# WorkOrder
# ---------------------------------------------------------------------------


def test_work_order_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="note", field_type="text")
    wo = client.post(
        "/api/v1/work-orders", headers=h, json={"title": "T", "custom_values": {"note": "hello"}}
    )
    assert wo.status_code == 201, wo.text
    wid = wo.json()["id"]
    assert wo.json()["custom_values"] == {"note": "hello"}
    got = client.get(f"/api/v1/work-orders/{wid}", headers=h).json()
    assert got["custom_values"]["note"] == "hello"


def test_work_order_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post(
        "/api/v1/work-orders", headers=h, json={"title": "T", "custom_values": {"ghost": 1}}
    )
    assert r.status_code == 422


def test_work_order_required_missing_422(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="req", field_type="text", required=True)
    r = client.post("/api/v1/work-orders", headers=h, json={"title": "T", "custom_values": {}})
    assert r.status_code == 422


def test_work_order_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="a", field_type="text")
    d2 = _def(client, h, "work_order", key="b", field_type="text")
    wid = client.post(
        "/api/v1/work-orders",
        headers=h,
        json={"title": "T", "custom_values": {"a": "1", "b": "2"}},
    ).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    # 表单只提交 active 字段 a；归档字段 b 的值应保留
    client.patch(f"/api/v1/work-orders/{wid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/work-orders/{wid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------


def test_asset_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "asset", key="note", field_type="text")
    r = client.post("/api/v1/assets", headers=h, json={"name": "A", "custom_values": {"note": "x"}})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["custom_values"] == {"note": "x"}
    assert client.get(f"/api/v1/assets/{aid}", headers=h).json()["custom_values"]["note"] == "x"


def test_asset_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post("/api/v1/assets", headers=h, json={"name": "A", "custom_values": {"ghost": 1}})
    assert r.status_code == 422


def test_asset_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "asset", key="a", field_type="text")
    d2 = _def(client, h, "asset", key="b", field_type="text")
    aid = client.post(
        "/api/v1/assets", headers=h, json={"name": "A", "custom_values": {"a": "1", "b": "2"}}
    ).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    client.patch(f"/api/v1/assets/{aid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/assets/{aid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


def test_request_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "request", key="note", field_type="text")
    r = client.post(
        "/api/v1/requests", headers=h, json={"title": "T", "custom_values": {"note": "x"}}
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["custom_values"] == {"note": "x"}
    assert client.get(f"/api/v1/requests/{rid}", headers=h).json()["custom_values"]["note"] == "x"


def test_request_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post(
        "/api/v1/requests", headers=h, json={"title": "T", "custom_values": {"ghost": 1}}
    )
    assert r.status_code == 422


def test_request_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "request", key="a", field_type="text")
    d2 = _def(client, h, "request", key="b", field_type="text")
    rid = client.post(
        "/api/v1/requests",
        headers=h,
        json={"title": "T", "custom_values": {"a": "1", "b": "2"}},
    ).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    client.patch(f"/api/v1/requests/{rid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/requests/{rid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


def test_location_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "location", key="note", field_type="text")
    r = client.post(
        "/api/v1/locations", headers=h, json={"name": "L", "custom_values": {"note": "x"}}
    )
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert r.json()["custom_values"] == {"note": "x"}
    assert client.get(f"/api/v1/locations/{lid}", headers=h).json()["custom_values"]["note"] == "x"


def test_location_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post(
        "/api/v1/locations", headers=h, json={"name": "L", "custom_values": {"ghost": 1}}
    )
    assert r.status_code == 422


def test_location_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "location", key="a", field_type="text")
    d2 = _def(client, h, "location", key="b", field_type="text")
    lid = client.post(
        "/api/v1/locations",
        headers=h,
        json={"name": "L", "custom_values": {"a": "1", "b": "2"}},
    ).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    client.patch(f"/api/v1/locations/{lid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/locations/{lid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}


# ---------------------------------------------------------------------------
# Part
# ---------------------------------------------------------------------------


def test_part_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "part", key="note", field_type="text")
    r = client.post("/api/v1/parts", headers=h, json={"name": "P", "custom_values": {"note": "x"}})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["custom_values"] == {"note": "x"}
    assert client.get(f"/api/v1/parts/{pid}", headers=h).json()["custom_values"]["note"] == "x"


def test_part_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post("/api/v1/parts", headers=h, json={"name": "P", "custom_values": {"ghost": 1}})
    assert r.status_code == 422


def test_part_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "part", key="a", field_type="text")
    d2 = _def(client, h, "part", key="b", field_type="text")
    pid = client.post(
        "/api/v1/parts",
        headers=h,
        json={"name": "P", "custom_values": {"a": "1", "b": "2"}},
    ).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    client.patch(f"/api/v1/parts/{pid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/parts/{pid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}
