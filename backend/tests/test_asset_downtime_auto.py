"""状态跃迁自动停机：UP->DOWN 建 open auto；DOWN->UP 关闭；同向不触发。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _downtimes(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()


def test_up_to_down_creates_open_auto(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    rows = _downtimes(client, t, aid)
    assert len(rows) == 1
    assert rows[0]["downtime_type"] == "auto"
    assert rows[0]["ended_at"] is None
    assert rows[0]["source_asset_id"] is None


def test_down_to_up_closes_auto(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "OPERATIONAL"})
    rows = _downtimes(client, t, aid)
    assert len(rows) == 1
    assert rows[0]["ended_at"] is not None


def test_up_to_up_no_trigger(client):
    t = _admin(client)
    aid = client.post("/api/v1/assets", headers=_h(t), json={"name": "泵"}).json()["id"]
    # OPERATIONAL -> STANDBY 均属 UP，不应建停机
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "STANDBY"})
    assert _downtimes(client, t, aid) == []
