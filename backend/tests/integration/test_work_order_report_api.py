"""工单 PDF 报告端点 GET /work-orders/{id}/report。

- 返回 200 + application/pdf + 非空响应体（PDF 魔数 %PDF）。
- 含工时/附加成本/备件消耗的工单也能正常生成（覆盖各明细块）。
- 租户隔离：他租户工单 404。
- 权限：无 WORK_ORDER_VIEW 的角色 403。
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


def _mk_wo(client, h, title="巡检工单", **extra):
    body: dict[str, object] = {"title": title, **extra}
    r = client.post("/api/v1/work-orders", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _report(client, h, wo_id):
    return client.get(f"/api/v1/work-orders/{wo_id}/report", headers=h)


def test_report_minimal_work_order(client):
    t = _admin(client)
    h = _h(t)
    wo = _mk_wo(client, h, due_date="2026-06-30")
    r = _report(client, h, wo)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert 'filename="WO-WO000001.pdf"' in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 1000


def test_report_with_costs_and_parts(client):
    t = _admin(client)
    h = _h(t)
    wo = _mk_wo(client, h, "带成本工单")

    # 工时（手填，含费率）
    rl = client.post(
        f"/api/v1/work-orders/{wo}/labor",
        headers=h,
        json={"duration_seconds": 3600, "hourly_rate": "50.00", "notes": "现场作业"},
    )
    assert rl.status_code == 201, rl.text

    # 附加成本
    rc = client.post(
        f"/api/v1/work-orders/{wo}/additional-costs",
        headers=h,
        json={"title": "外包检测", "amount": "120.50", "description": "第三方"},
    )
    assert rc.status_code == 201, rc.text

    # 备件消耗
    part = client.post(
        "/api/v1/parts",
        headers=h,
        json={"name": "轴承", "cost": "8.00", "quantity": "100"},
    )
    assert part.status_code == 201, part.text
    pid = part.json()["id"]
    rp = client.post(
        f"/api/v1/work-orders/{wo}/part-consumptions",
        headers=h,
        json={"part_id": pid, "quantity": "3"},
    )
    assert rp.status_code == 201, rp.text

    # 一条活动（评论）以覆盖时间线块
    client.post(
        f"/api/v1/work-orders/{wo}/activities",
        headers=h,
        json={"comment": "处理完毕"},
    )

    r = _report(client, h, wo)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 1000


def test_report_tenant_isolated(client):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    wo_a = _mk_wo(client, _h(ta), "AcmeWO")
    # B 租户访问 A 的工单 → 404
    r = _report(client, _h(tb), wo_a)
    assert r.status_code == 404, r.text


def test_report_requires_view_permission(client):
    admin = _admin(client)
    wo = _mk_wo(client, _h(admin), "受限工单")
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
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
    r = _report(client, _h(tok), wo)
    assert r.status_code == 403, r.text
