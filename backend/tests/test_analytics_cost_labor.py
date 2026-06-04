"""/costs 扩展：labor + additional + total_maintenance_cost + by_asset。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_costs_includes_labor_and_additional(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(
        custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co, asset_id="asset-1"
    )
    db.add(wo)
    db.flush()
    # 1 小时 @ 60 = 60.00 labor；additional 40.00
    db.add(
        WorkOrderLabor(
            work_order_id=wo.id, duration_seconds=3600, hourly_rate=Decimal("60"), company_id=co
        )
    )
    db.add(
        WorkOrderAdditionalCost(
            work_order_id=wo.id, title="耗材", amount=Decimal("40"), company_id=co
        )
    )
    db.commit()
    body = client.get("/api/v1/analytics/costs", headers=_h(t)).json()
    assert body["labor_cost"] == "60.00"
    assert body["additional_cost"] == "40.00"
    assert body["total_maintenance_cost"] == "100.00"
    by_asset = {r["asset_id"]: r for r in body["maintenance_cost_by_asset"]}
    assert by_asset["asset-1"]["labor_cost"] == "60.00"
    assert by_asset["asset-1"]["total"] == "100.00"


def test_running_timer_costs_zero(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co)
    db.add(wo)
    db.flush()
    db.add(
        WorkOrderLabor(
            work_order_id=wo.id,
            duration_seconds=0,
            hourly_rate=Decimal("60"),
            started_at=datetime.utcnow(),
            company_id=co,
        )
    )
    db.commit()
    body = client.get("/api/v1/analytics/costs", headers=_h(t)).json()
    assert body["labor_cost"] == "0.00"
