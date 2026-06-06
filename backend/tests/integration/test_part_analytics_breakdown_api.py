"""/inventory 备件消耗细分切面：按工单分类聚合 + 按月趋势（Pareto 复用既有 ABC，另测）。

覆盖：聚合正确性、租户隔离、权限（analytics.view）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.models.work_order_category import WorkOrderCategory

pytestmark = pytest.mark.usefixtures("_enterprise_default")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "company_name": company,
            "email": email,
            "password": "secret123",
            "name": "Admin",
        },
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def _part(db, co, name, custom_id):
    p = Part(
        custom_id=custom_id,
        name=name,
        quantity=Decimal("0"),
        min_quantity=Decimal("0"),
        cost=Decimal("1"),
        company_id=co,
    )
    db.add(p)
    db.flush()
    return p


def _category(db, co, name):
    c = WorkOrderCategory(name=name, company_id=co)
    db.add(c)
    db.flush()
    return c


def _wo(db, co, custom_id, *, category_id=None):
    wo = WorkOrder(
        custom_id=custom_id,
        title="t",
        created_at=datetime.utcnow(),
        company_id=co,
        category_id=category_id,
    )
    db.add(wo)
    db.flush()
    return wo


def _consume(db, co, wo, part, qty, unit_cost, when):
    db.add(
        PartConsumption(
            work_order_id=wo.id,
            part_id=part.id,
            quantity=Decimal(qty),
            unit_cost=Decimal(unit_cost),
            consumed_at=when,
            company_id=co,
        )
    )


def test_consumption_by_wo_category(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    cat_mech = _category(db, co, "机械维修")
    part = _part(db, co, "轴承", "P-1")
    wo_mech = _wo(db, co, "WO1", category_id=cat_mech.id)
    wo_uncat = _wo(db, co, "WO2", category_id=None)
    # 机械维修：10*2 + 5*2 = 30 成本，qty 15
    _consume(db, co, wo_mech, part, "10", "2", datetime(2026, 3, 10))
    _consume(db, co, wo_mech, part, "5", "2", datetime(2026, 3, 12))
    # 未分类：4*3 = 12 成本，qty 4
    _consume(db, co, wo_uncat, part, "4", "3", datetime(2026, 3, 15))
    db.commit()

    body = client.get(
        "/api/v1/analytics/inventory",
        params={"date_from": "2026-01-01", "date_to": "2026-06-30"},
        headers=_h(t),
    ).json()
    rows = body["consumption_by_wo_category"]
    # 成本降序：机械维修(30) 先于 未分类(12)
    assert [r["name"] for r in rows] == ["机械维修", None]
    assert rows[0]["category_id"] == cat_mech.id
    assert rows[0]["cost"] == "30.00"
    assert rows[0]["qty"] == "15.0000"
    assert rows[1]["category_id"] is None
    assert rows[1]["cost"] == "12.00"
    assert rows[1]["qty"] == "4.0000"


def test_consumption_monthly_trend(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    part = _part(db, co, "轴承", "P-1")
    wo = _wo(db, co, "WO1")
    # 2026-02: 10*1=10 ; 2026-03: 5*2 + 3*1 = 13
    _consume(db, co, wo, part, "10", "1", datetime(2026, 2, 5))
    _consume(db, co, wo, part, "5", "2", datetime(2026, 3, 1))
    _consume(db, co, wo, part, "3", "1", datetime(2026, 3, 20))
    db.commit()

    body = client.get(
        "/api/v1/analytics/inventory",
        params={"date_from": "2026-01-01", "date_to": "2026-06-30"},
        headers=_h(t),
    ).json()
    trend = body["consumption_monthly_trend"]
    # 月份升序
    assert [r["month"] for r in trend] == ["2026-02", "2026-03"]
    assert trend[0]["cost"] == "10.00"
    assert trend[1]["cost"] == "13.00"


def test_breakdown_tenant_isolation(client, db):
    """B 公司的消耗不得污染 A 公司的细分聚合。"""
    ta = _admin(client)
    _admin(client, company="Bravo", email="b@bravo.com")
    co_a = _company_id(db, "acme")
    co_b = _company_id(db, "bravo")

    cat_a = _category(db, co_a, "A类")
    part_a = _part(db, co_a, "A件", "PA-1")
    wo_a = _wo(db, co_a, "WOA", category_id=cat_a.id)
    _consume(db, co_a, wo_a, part_a, "10", "1", datetime(2026, 3, 10))

    cat_b = _category(db, co_b, "B类")
    part_b = _part(db, co_b, "B件", "PB-1")
    wo_b = _wo(db, co_b, "WOB", category_id=cat_b.id)
    _consume(db, co_b, wo_b, part_b, "99", "9", datetime(2026, 3, 10))
    db.commit()

    body = client.get(
        "/api/v1/analytics/inventory",
        params={"date_from": "2026-01-01", "date_to": "2026-06-30"},
        headers=_h(ta),
    ).json()
    cats = body["consumption_by_wo_category"]
    assert [r["name"] for r in cats] == ["A类"]
    assert cats[0]["cost"] == "10.00"
    trend = body["consumption_monthly_trend"]
    assert [r["month"] for r in trend] == ["2026-03"]
    assert trend[0]["cost"] == "10.00"


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post(
        "/api/v1/users",
        headers=_h(admin_token),
        json={"email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid},
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "tech@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_breakdown_requires_analytics_view(client):
    """无 analytics.view 的 technician 访问 /inventory 被拒（403）——切面挂同一端点同一守卫。"""
    admin = _admin(client)
    tech = _technician_token(client, admin)
    assert client.get("/api/v1/analytics/inventory", headers=_h(tech)).status_code == 403
