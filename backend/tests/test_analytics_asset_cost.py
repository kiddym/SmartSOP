"""/asset-reliability 扩展：total_maintenance_cost + cost_to_value_ratio。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.company import Company
from app.models.maintenance_asset import Asset
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Acme",
            "email": "a@acme.com",
            "password": "secret123",
            "name": "Admin",
        },
    ).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_asset_maintenance_cost_and_ratio(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    a = Asset(custom_id="AS-1", name="泵", acquisition_cost=Decimal("1000"), company_id=co)
    db.add(a)
    db.flush()
    wo = WorkOrder(
        custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co, asset_id=a.id
    )
    db.add(wo)
    db.flush()
    db.add(
        WorkOrderAdditionalCost(
            work_order_id=wo.id, title="耗材", amount=Decimal("250"), company_id=co
        )
    )
    db.commit()
    body = client.get("/api/v1/analytics/asset-reliability", headers=_h(t)).json()
    row = next(r for r in body["assets"] if r["asset_id"] == a.id)
    assert row["total_maintenance_cost"] == "250.00"
    assert row["acquisition_cost"] == "1000.00"
    assert row["cost_to_value_ratio"] == 0.25
    assert body["fleet_total_maintenance_cost"] == "250.00"
