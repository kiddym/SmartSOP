from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_status import PurchaseOrderStatus


def test_purchase_order_row_defaults(db: Session):
    po = PurchaseOrder(custom_id="PO000001", vendor_id="v-1", company_id="co-1")
    db.add(po)
    db.commit()
    db.refresh(po)
    assert po.id and po.is_active is True
    assert po.status == PurchaseOrderStatus.DRAFT
    assert po.notes == "" and po.resolution_note == ""
    assert po.resolved_by_user_id is None and po.resolved_at is None


def test_line_and_activity_rows(db: Session):
    po = PurchaseOrder(custom_id="PO000002", vendor_id="v-1", company_id="co-1")
    db.add(po)
    db.flush()
    db.add(
        PurchaseOrderLine(
            purchase_order_id=po.id,
            part_id="p-1",
            quantity=Decimal("3"),
            unit_cost=Decimal("2.5"),
            company_id="co-1",
        )
    )
    db.add(
        PurchaseOrderActivity(
            purchase_order_id=po.id,
            activity_type="STATUS_CHANGE",
            from_status="DRAFT",
            to_status="SUBMITTED",
            company_id="co-1",
        )
    )
    db.commit()
    ln = db.query(PurchaseOrderLine).filter_by(purchase_order_id=po.id).one()
    assert ln.part_id == "p-1" and ln.quantity == Decimal("3")
    act = db.query(PurchaseOrderActivity).filter_by(purchase_order_id=po.id).one()
    assert act.activity_type == "STATUS_CHANGE" and act.comment == ""


def test_purchase_order_exports_registered():
    import app.models as mod

    for name in ("PurchaseOrder", "PurchaseOrderLine", "PurchaseOrderActivity"):
        assert name in mod.__all__ and hasattr(mod, name)
