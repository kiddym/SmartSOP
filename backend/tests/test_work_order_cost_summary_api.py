"""工单总成本汇总端点测试（GET /work-orders/{id}/cost-summary）。

覆盖：空汇总全零、三类成本聚合、运行中计时器排除、小计之和==总计、多租户隔离。
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
    return client.post("/api/v1/work-orders", json={"title": "检修"}, headers=_h(t)).json()["id"]


def test_empty_summary_all_zero(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    r = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert float(body["labor_total"]) == 0.0
    assert float(body["additional_total"]) == 0.0
    assert float(body["parts_total"]) == 0.0
    assert float(body["total"]) == 0.0


def test_summary_aggregates_three_sources(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # labor: 2h * 50 = 100
    client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 7200, "hourly_rate": "50"},
        headers=_h(t),
    )
    # additional: 33.50
    client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "差旅", "amount": "33.50"},
        headers=_h(t),
    )
    # parts: 3 * 12.5 = 37.5
    pid = client.post(
        "/api/v1/parts",
        json={"name": "轴承", "cost": "12.5", "quantity": "10"},
        headers=_h(t),
    ).json()["id"]
    client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        json={"part_id": pid, "quantity": "3"},
        headers=_h(t),
    )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 100.0
    assert float(body["additional_total"]) == 33.5
    assert float(body["parts_total"]) == 37.5
    assert float(body["total"]) == 171.0  # 100 + 33.5 + 37.5


def test_running_timer_excluded_from_summary(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    client.post(f"/api/v1/work-orders/{wo}/labor/start", json={"hourly_rate": "99"}, headers=_h(t))
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 0.0  # 运行中不入账


def test_summary_subtotals_sum_to_total(client):
    t = _admin(client)
    wo = _wo_id(client, t)
    # 验证 total == labor_total + additional_total + parts_total（已量化小计之和）公式
    for _ in range(3):
        client.post(
            f"/api/v1/work-orders/{wo}/labor",
            json={"duration_seconds": 1, "hourly_rate": "36"},
            headers=_h(t),
        )
    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    s = float(body["labor_total"]) + float(body["additional_total"]) + float(body["parts_total"])
    assert abs(s - float(body["total"])) < 1e-9  # 明细之和 == 总计


def test_summary_quantizes_each_subtotal_independently(client):
    """证明 cost_summary 是「逐小计量化后相加」而非「先相加后量化」。

    构造：
      - labor:      1 秒 × 18/hr → 原始 1/3600×18 = 0.005 → ROUND_HALF_UP → 0.01
      - additional: amount=0.005 → ROUND_HALF_UP → 0.01
      - parts:      无（0.00）
    期望 total = 0.01 + 0.01 + 0.00 = 0.02。

    若实现误用「先相加后量化」：_q(0.005 + 0.005) = _q(0.01) = 0.01，本测试即可捕获。
    """
    t = _admin(client, company="RoundCo", email="admin@roundco.com")
    wo = _wo_id(client, t)

    # labor 小计 = _q(0.005) = 0.01
    r_labor = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        json={"duration_seconds": 1, "hourly_rate": "18"},
        headers=_h(t),
    )
    assert r_labor.status_code == 201, r_labor.text

    # additional 小计 = _q(0.005) = 0.01
    r_add = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        json={"title": "舍入验证", "amount": "0.005"},
        headers=_h(t),
    )
    assert r_add.status_code == 201, r_add.text

    body = client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(t)).json()
    assert float(body["labor_total"]) == 0.01
    assert float(body["additional_total"]) == 0.01
    assert float(body["parts_total"]) == 0.0
    # 逐小计量化后相加：0.01 + 0.01 + 0.00 = 0.02
    # 若先相加后量化：_q(0.005 + 0.005) = _q(0.01) = 0.01（会在此断言失败）
    assert float(body["total"]) == 0.02


def test_summary_tenant_isolation(client):
    a = _admin(client)
    wo = _wo_id(client, a)
    b = _admin(client, company="Beta", email="admin@beta.com")
    assert client.get(f"/api/v1/work-orders/{wo}/cost-summary", headers=_h(b)).status_code == 404
