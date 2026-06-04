"""/inventory 扩展：ABC 分级（按窗内消耗价值）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder

pytestmark = pytest.mark.usefixtures("_enterprise_default")


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


def test_abc_classification(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co)
    db.add(wo)
    db.flush()
    big = _part(db, co, "大头", "P-1")
    small = _part(db, co, "小头", "P-2")
    db.add(
        PartConsumption(
            work_order_id=wo.id,
            part_id=big.id,
            quantity=Decimal("90"),
            unit_cost=Decimal("1"),
            consumed_at=datetime.utcnow(),
            company_id=co,
        )
    )
    db.add(
        PartConsumption(
            work_order_id=wo.id,
            part_id=small.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("1"),
            consumed_at=datetime.utcnow(),
            company_id=co,
        )
    )
    db.commit()
    body = client.get("/api/v1/analytics/inventory", headers=_h(t)).json()
    rows = {r["part_id"]: r for r in body["abc_classification"]}
    assert rows[big.id]["consumption_value"] == "90.00"
    assert rows[big.id]["cumulative_pct"] == 90.0
    assert rows[big.id]["abc_class"] == "B"  # 累计 90% ∈ (80,95] → B
    assert rows[small.id]["abc_class"] == "C"  # 累计 100% > 95 → C
    assert body["abc_summary"]["B"] == 1 and body["abc_summary"]["C"] == 1


def test_abc_empty_when_no_consumption(client, db):
    t = _admin(client)
    body = client.get("/api/v1/analytics/inventory", headers=_h(t)).json()
    assert body["abc_classification"] == []
    assert body["abc_summary"] == {"A": 0, "B": 0, "C": 0}
