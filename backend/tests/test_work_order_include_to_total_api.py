"""工时/附加成本 include_to_total 开关对 cost_summary 的影响（I 尾项第 1 批）。"""

from __future__ import annotations


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def _admin(client, *, company: str = "Acme", email: str = "admin@acme.com") -> str:
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _wo_id(client, t: str) -> str:
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def test_labor_excluded_when_include_false(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # 计入：2h*50=100
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 7200, "hourly_rate": "50"},
        headers=_h(t),
    )
    # 不计入：1h*99 但 include_to_total=False
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 3600, "hourly_rate": "99", "include_to_total": False},
        headers=_h(t),
    )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 100.0
    assert float(body["total"]) == 100.0


def test_additional_excluded_when_include_false(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "计入", "amount": "20"},
        headers=_h(t),
    )
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "不计入", "amount": "999", "include_to_total": False},
        headers=_h(t),
    )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["additional_total"]) == 20.0
    assert float(body["total"]) == 20.0


def test_include_flag_defaults_true_and_exposed(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    lr = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 3600, "hourly_rate": "10"},
        headers=_h(t),
    ).json()
    assert lr["include_to_total"] is True
    ar = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "x", "amount": "5"},
        headers=_h(t),
    ).json()
    assert ar["include_to_total"] is True


def test_patch_include_to_total_toggles_summary(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    lid = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 3600, "hourly_rate": "10"},
        headers=_h(t),
    ).json()["id"]
    assert (
        float(client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()["total"])
        == 10.0
    )
    client.patch(
        f"/api/v1/work-orders/{wo}/labor/{lid}",
        json={"include_to_total": False},
        headers=_h(t),
    )
    assert (
        float(client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()["total"])
        == 0.0
    )
