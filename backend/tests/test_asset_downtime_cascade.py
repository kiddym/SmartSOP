"""向下级联与反转：父 DOWN -> 后代 DOWN + cascade 记录；父恢复 -> 后代还原。"""

from __future__ import annotations


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _mk(client, t, name, parent=None):
    body = {"name": name}
    if parent:
        body["parent_id"] = parent
    return client.post("/api/v1/assets", headers=_h(t), json=body).json()["id"]


def _status(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}", headers=_h(t)).json()["status"]


def _downtimes(client, t, aid):
    return client.get(f"/api/v1/assets/{aid}/downtimes", headers=_h(t)).json()


def test_cascade_down_and_recover(client):
    t = _admin(client)
    a = _mk(client, t, "A")
    b = _mk(client, t, "B", a)
    c = _mk(client, t, "C", b)  # A->B->C 三层
    # 把 C 原状态设为 STANDBY 以验 prior 还原
    client.patch(f"/api/v1/assets/{c}", headers=_h(t), json={"status": "STANDBY"})

    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "DOWN"})
    assert _status(client, t, b) == "DOWN"
    assert _status(client, t, c) == "DOWN"
    # B、C 各有一条 source=A 的 open cascade
    for child in (b, c):
        rows = _downtimes(client, t, child)
        assert any(r["downtime_type"] == "cascade" and r["source_asset_id"] == a
                   and r["ended_at"] is None for r in rows)

    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "OPERATIONAL"})
    assert _status(client, t, b) == "OPERATIONAL"   # prior=OPERATIONAL 还原
    assert _status(client, t, c) == "STANDBY"        # prior=STANDBY 还原
    # cascade 记录均已闭合（显式断言至少一条，避免空集合 all() 误判通过）
    for child in (b, c):
        cascade_rows = [r for r in _downtimes(client, t, child)
                        if r["downtime_type"] == "cascade"]
        assert cascade_rows
        assert all(r["ended_at"] is not None for r in cascade_rows)


def test_recover_keeps_independently_down_descendant(client):
    t = _admin(client)
    a = _mk(client, t, "A")
    b = _mk(client, t, "B", a)
    # B 先独立手动 open 停机（解耦：不改状态），再让父级联
    client.post(f"/api/v1/assets/{b}/downtimes", headers=_h(t),
                json={"started_at": "2026-05-01T00:00:00"})
    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "DOWN"})
    assert _status(client, t, b) == "DOWN"
    # 父恢复，但 B 仍有独立 open 手动停机 -> 维持 DOWN
    client.patch(f"/api/v1/assets/{a}", headers=_h(t), json={"status": "OPERATIONAL"})
    assert _status(client, t, b) == "DOWN"


def test_manual_downtime_decoupled(client):
    t = _admin(client)
    aid = _mk(client, t, "孤立")
    client.post(f"/api/v1/assets/{aid}/downtimes", headers=_h(t),
                json={"started_at": "2026-05-01T00:00:00"})
    assert _status(client, t, aid) == "OPERATIONAL"  # 手动停机不改状态


def test_cross_tenant_cascade_isolation(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    # 两租户各建 父->子
    a_parent = _mk(client, ta, "A父")
    a_child = _mk(client, ta, "A子", a_parent)
    b_parent = _mk(client, tb, "B父")
    b_child = _mk(client, tb, "B子", b_parent)
    # A 父停机
    client.patch(f"/api/v1/assets/{a_parent}", headers=_h(ta), json={"status": "DOWN"})
    # B 侧完全不受影响
    assert _status(client, tb, b_child) == "OPERATIONAL"
    assert _downtimes(client, tb, b_child) == []
    # A 子被级联
    assert _status(client, ta, a_child) == "DOWN"


def test_down_internal_switch_no_extra_record(client):
    t = _admin(client)
    aid = _mk(client, t, "泵")
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "DOWN"})
    n1 = len(_downtimes(client, t, aid))
    # DOWN -> EMERGENCY_SHUTDOWN 仍属 DOWN 类，不应再建记录
    client.patch(f"/api/v1/assets/{aid}", headers=_h(t), json={"status": "EMERGENCY_SHUTDOWN"})
    assert len(_downtimes(client, t, aid)) == n1
