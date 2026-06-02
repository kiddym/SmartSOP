"""工单工时 REST API 测试（Task 3：Labor 路由）。

覆盖：手填 CRUD、计时器开/停、双开 409、停非运行 400、跨租户隔离 404、权限 403。
"""

from __future__ import annotations


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company: str = "Acme", email: str = "admin@acme.com") -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t: str) -> str:
    return client.post(
        "/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)
    ).json()["id"]


def _viewer_token(client, admin: str) -> str:
    # 自建只读角色（仅 work_order.view），用于 403 验证
    rid = client.post(
        "/api/v1/roles",
        headers=_h(admin),
        json={"code": "wo_viewer", "name": "工单只读", "permissions": ["work_order.view"]},
    ).json()["id"]
    client.post(
        "/api/v1/users",
        headers=_h(admin),
        json={"email": "v@acme.com", "password": "secret123", "name": "V", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "v@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_manual_labor_crud(client) -> None:
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 3600, "hourly_rate": "80"},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert float(r.json()["cost"]) == 80.0
    assert r.json()["running"] is False
    lst = client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(t)).json()
    assert len(lst) == 1
    upd = client.patch(
        f"/api/v1/work-orders/{wo}/labor/{lid}",
        json={"duration_seconds": 1800},
        headers=_h(t),
    )
    assert upd.json()["duration_seconds"] == 1800
    assert client.delete(f"/api/v1/work-orders/{wo}/labor/{lid}", headers=_h(t)).status_code == 204


def test_timer_start_stop(client) -> None:
    t = _admin(client)
    wo = _wo_id(client, t)
    start = client.post(
        f"/api/v1/work-orders/{wo}/labor/start", json={"hourly_rate": "60"}, headers=_h(t)
    )
    assert start.status_code == 201, start.text
    lid = start.json()["id"]
    assert start.json()["running"] is True
    assert float(start.json()["cost"]) == 0.0
    stop = client.post(f"/api/v1/work-orders/{wo}/labor/{lid}/stop", headers=_h(t))
    assert stop.status_code == 200, stop.text
    assert stop.json()["running"] is False


def test_timer_double_start_409(client) -> None:
    t = _admin(client)
    wo = _wo_id(client, t)
    client.post(f"/api/v1/work-orders/{wo}/labor/start", json={}, headers=_h(t))
    r = client.post(f"/api/v1/work-orders/{wo}/labor/start", json={}, headers=_h(t))
    assert r.status_code == 409


def test_stop_non_running_400(client) -> None:
    t = _admin(client)
    wo = _wo_id(client, t)
    lid = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(t),
    ).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wo}/labor/{lid}/stop", headers=_h(t))
    assert r.status_code == 400


def test_labor_tenant_isolation(client) -> None:
    a = _admin(client)
    wo = _wo_id(client, a)
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(a),
    )
    b = _admin(client, company="Beta", email="admin@beta.com")
    # B 访问 A 的工单 → 404
    assert client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(b)).status_code == 404


def test_labor_requires_edit_permission(client) -> None:
    admin = _admin(client)
    wo = _wo_id(client, admin)
    viewer = _viewer_token(client, admin)
    assert client.get(f"/api/v1/work-orders/{wo}/labor", headers=_h(viewer)).status_code == 200
    r = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 60, "hourly_rate": "10"},
        headers=_h(viewer),
    )
    assert r.status_code == 403
