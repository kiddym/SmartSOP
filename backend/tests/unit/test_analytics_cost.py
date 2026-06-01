from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.purchase_order_status import PurchaseOrderStatus
from app.models.work_order import WorkOrder
from app.services.analytics import cost_analytics as svc

CO = "co-1"


def _part(db, custom_id="PRT1", name="x"):
    p = Part(custom_id=custom_id, name=name, company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _wo(db, *, asset_id=None, custom_id="WO1"):
    wo = WorkOrder(
        custom_id=custom_id,
        title="t",
        asset_id=asset_id,
        created_at=datetime(2026, 1, 5),
        company_id=CO,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def _consume(db, part, wo, qty, unit_cost, when):
    db.add(
        PartConsumption(
            part_id=part.id,
            work_order_id=wo.id,
            quantity=Decimal(qty),
            unit_cost=Decimal(unit_cost),
            consumed_at=when,
            company_id=CO,
        )
    )
    db.commit()


def test_empty_costs(db: Session):
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("0")
    assert r["po_spend_approved"] == Decimal("0")
    assert r["consumption_by_part"] == [] and r["po_spend_by_vendor"] == []


def test_consumption_cost_and_breakdowns(db: Session):
    p1, p2 = _part(db, "PRT1"), _part(db, "PRT2")
    wo = _wo(db, asset_id="a-1")
    _consume(db, p1, wo, "3", "2", datetime(2026, 1, 10))  # 6
    _consume(db, p2, wo, "1", "5", datetime(2026, 1, 11))  # 5
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("11")
    by_part = {row["custom_id"]: row["cost"] for row in r["consumption_by_part"]}
    assert by_part["PRT1"] == Decimal("6") and by_part["PRT2"] == Decimal("5")
    # 降序：cost 高的在前
    assert r["consumption_by_part"][0]["custom_id"] == "PRT1"
    by_asset = {row["asset_id"]: row["cost"] for row in r["consumption_by_asset"]}
    assert by_asset["a-1"] == Decimal("11")


def test_consumption_window_excludes(db: Session):
    p1 = _part(db)
    wo = _wo(db)
    _consume(db, p1, wo, "3", "2", datetime(2025, 12, 31))  # 窗外
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("0")


def test_po_spend_only_approved_in_window(db: Session):
    p1 = _part(db)
    # APPROVED 在窗 -> 计入
    po1 = PurchaseOrder(
        custom_id="PO1",
        vendor_id="v-1",
        status=PurchaseOrderStatus.APPROVED,
        resolved_at=datetime(2026, 1, 15),
        company_id=CO,
    )
    db.add(po1)
    db.flush()
    db.add(
        PurchaseOrderLine(
            purchase_order_id=po1.id,
            part_id=p1.id,
            quantity=Decimal("2"),
            unit_cost=Decimal("10"),
            company_id=CO,
        )
    )
    # SUBMITTED -> 不计
    po2 = PurchaseOrder(
        custom_id="PO2", vendor_id="v-2", status=PurchaseOrderStatus.SUBMITTED, company_id=CO
    )
    db.add(po2)
    db.flush()
    db.add(
        PurchaseOrderLine(
            purchase_order_id=po2.id,
            part_id=p1.id,
            quantity=Decimal("9"),
            unit_cost=Decimal("9"),
            company_id=CO,
        )
    )
    db.commit()
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["po_spend_approved"] == Decimal("20")
    assert {row["vendor_id"]: row["spend"] for row in r["po_spend_by_vendor"]} == {
        "v-1": Decimal("20")
    }
