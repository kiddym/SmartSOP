from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import POLineCreate, PurchaseOrderCreate, PurchaseOrderUpdate
from app.services import purchase_order_service as svc

CO = "co-1"


def _po_with_line(db):
    return svc.create_purchase_order(
        db,
        PurchaseOrderCreate(
            vendor_id="v-1", lines=[POLineCreate(part_id="p-1", quantity=Decimal("1"))]
        ),
        CO,
        actor_user_id="a",
    )


def test_submit_requires_lines(db: Session):
    empty = svc.create_purchase_order(
        db, PurchaseOrderCreate(vendor_id="v-1"), CO, actor_user_id="a"
    )
    with pytest.raises(HTTPException):
        svc.submit_purchase_order(db, empty, CO, actor_user_id="a")


def test_submit_moves_to_submitted_and_logs(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.SUBMITTED
    acts = svc.list_activities(db, po.id)
    assert acts[-1].activity_type == "STATUS_CHANGE"
    assert acts[-1].to_status == "SUBMITTED"


def test_update_blocked_after_submit(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    with pytest.raises(HTTPException):
        svc.update_purchase_order(db, po, PurchaseOrderUpdate(notes="x"), CO, actor_user_id="a")


def test_reject_from_submitted(db: Session):
    po = _po_with_line(db)
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    svc.reject_purchase_order(db, po, "no budget", CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.REJECTED
    assert po.resolution_note == "no budget" and po.resolved_by_user_id == "a"


def test_cancel_from_draft(db: Session):
    po = _po_with_line(db)
    svc.cancel_purchase_order(db, po, "mistake", CO, actor_user_id="a")
    assert po.status == PurchaseOrderStatus.CANCELED


def test_illegal_transition_rejected(db: Session):
    po = _po_with_line(db)  # DRAFT
    with pytest.raises(HTTPException):
        svc.reject_purchase_order(db, po, "", CO, actor_user_id="a")  # DRAFT->REJECTED illegal
