"""工单日历聚合端点 /work-orders/events：聚合工单(due_date)与启用 PM(next_due_date)。

- 区间内返回两类事件、区间外不返回。
- 租户隔离：A 公司看不到 B 公司事件。
- 权限：无 WORK_ORDER_VIEW 的角色 403。
- 路由顺序：/events 不被 /{id} 遮蔽（200 且形状正确，而非把 "events" 当 id 走 404）。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _mk_wo(client, h, title, *, due_date=None):
    body: dict[str, object] = {"title": title}
    if due_date is not None:
        body["due_date"] = due_date
    r = client.post("/api/v1/work-orders", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _mk_pm(client, h, title, *, start_date):
    r = client.post(
        "/api/v1/preventive-maintenances",
        headers=h,
        json={
            "title": title,
            "start_date": start_date,
            "frequency_unit": "MONTH",
            "frequency_value": 1,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _events(client, h, start, end):
    r = client.get("/api/v1/work-orders/events", headers=h, params={"start": start, "end": end})
    assert r.status_code == 200, r.text
    return r.json()


def test_events_aggregates_both_types(client):
    t = _admin(client)
    h = _h(t)
    wo = _mk_wo(client, h, "巡检工单", due_date="2026-06-15")
    pid = _mk_pm(client, h, "月度保养", start_date="2026-06-20")  # next_due_date=start_date

    events = _events(client, h, "2026-06-01", "2026-06-30")
    by_type = {e["type"]: e for e in events}
    assert set(by_type) == {"work_order", "pm"}

    wo_ev = by_type["work_order"]
    assert wo_ev["id"] == wo
    assert wo_ev["date"] == "2026-06-15"
    assert wo_ev["status"] == "OPEN"
    assert wo_ev["priority"] == "NONE"
    assert wo_ev["custom_id"] == "WO000001"

    pm_ev = by_type["pm"]
    assert pm_ev["id"] == pid
    assert pm_ev["date"] == "2026-06-20"
    assert pm_ev["custom_id"] == "PM000001"
    assert pm_ev["status"] is None
    assert pm_ev["priority"] is None


def test_events_excludes_out_of_range(client):
    t = _admin(client)
    h = _h(t)
    _mk_wo(client, h, "区间内", due_date="2026-06-15")
    _mk_wo(client, h, "区间前", due_date="2026-05-31")
    _mk_wo(client, h, "区间后", due_date="2026-07-01")
    _mk_wo(client, h, "无截止日")  # due_date None -> 不应出现
    _mk_pm(client, h, "区间内PM", start_date="2026-06-10")
    _mk_pm(client, h, "区间后PM", start_date="2026-07-15")

    events = _events(client, h, "2026-06-01", "2026-06-30")
    titles = sorted(e["title"] for e in events)
    assert titles == ["区间内", "区间内PM"]


def test_events_includes_range_boundaries(client):
    t = _admin(client)
    h = _h(t)
    _mk_wo(client, h, "起始边界", due_date="2026-06-01")
    _mk_wo(client, h, "结束边界", due_date="2026-06-30")

    events = _events(client, h, "2026-06-01", "2026-06-30")
    titles = sorted(e["title"] for e in events)
    assert titles == ["结束边界", "起始边界"]


def test_events_excludes_disabled_pm(client):
    t = _admin(client)
    h = _h(t)
    pid = _mk_pm(client, h, "停用PM", start_date="2026-06-10")
    client.post(f"/api/v1/preventive-maintenances/{pid}/disable", headers=h)

    events = _events(client, h, "2026-06-01", "2026-06-30")
    assert events == []


def test_events_tenant_isolated(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    _mk_wo(client, _h(ta), "AcmeWO", due_date="2026-06-15")
    _mk_pm(client, _h(ta), "AcmePM", start_date="2026-06-20")
    _mk_wo(client, _h(tb), "BetaWO", due_date="2026-06-15")

    a_events = _events(client, _h(ta), "2026-06-01", "2026-06-30")
    assert sorted(e["title"] for e in a_events) == ["AcmePM", "AcmeWO"]

    b_events = _events(client, _h(tb), "2026-06-01", "2026-06-30")
    assert [e["title"] for e in b_events] == ["BetaWO"]


def test_events_requires_permission(client):
    admin = _admin(client)
    # 建一个无任何权限的角色用户：用 viewer? 这里用一个新角色不含 WORK_ORDER_VIEW。
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    # requester 角色通常不含工单查看权限；若不存在则跳过断言宽松处理。
    requester = next((r for r in roles if r["code"] == "requester"), None)
    assert requester is not None, "expected a 'requester' role without WORK_ORDER_VIEW"
    client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={
            "email": "req@acme.com",
            "password": "secret123",
            "name": "R",
            "role_id": requester["id"],
        },
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "req@acme.com", "password": "secret123"},
    ).json()["access_token"]
    r = client.get(
        "/api/v1/work-orders/events",
        headers=_h(tok),
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    assert r.status_code == 403, r.text


def test_events_not_shadowed_by_id_route(client):
    """/events 解析为聚合端点（200 list），而非被 /{id} 当作 id 吞掉走 404。"""
    t = _admin(client)
    r = client.get(
        "/api/v1/work-orders/events",
        headers=_h(t),
        params={"start": "2026-06-01", "end": "2026-06-30"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)
