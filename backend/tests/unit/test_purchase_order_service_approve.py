from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.purchase_order_status import PurchaseOrderStatus
from app.schemas.purchase_order import POLineCreate, PurchaseOrderCreate
from app.services import purchase_order_service as svc

CO = "co-1"


def _part(db, *, qty="0", non_stock=False, cost="0"):
    p = Part(custom_id="PRT000001", name="x", quantity=Decimal(qty),
             non_stock=non_stock, cost=Decimal(cost), company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _submit(db, lines):
    po = svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1", lines=lines),
                                   CO, actor_user_id="a")
    svc.submit_purchase_order(db, po, CO, actor_user_id="a")
    return po


def test_approve_writes_back_stock(db: Session):
    p1 = _part(db, qty="10")
    p2 = _part(db, qty="5", non_stock=True)
    po = _submit(db, [
        POLineCreate(part_id=p1.id, quantity=Decimal("3"), unit_cost=Decimal("2")),
        POLineCreate(part_id=p2.id, quantity=Decimal("4")),
    ])
    svc.approve_purchase_order(db, po, "ok", CO, actor_user_id="a")
    db.refresh(p1)
    db.refresh(p2)
    assert po.status == PurchaseOrderStatus.APPROVED
    assert p1.quantity == Decimal("13")   # 10 + 3
    assert p2.quantity == Decimal("5")    # non_stock 不增
    acts = [a.activity_type for a in svc.list_activities(db, po.id)]
    assert "RECEIVED" in acts


def test_double_approve_blocked_writes_once(db: Session):
    p1 = _part(db, qty="10")
    po = _submit(db, [POLineCreate(part_id=p1.id, quantity=Decimal("3"))])
    svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    with pytest.raises(HTTPException):
        svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    db.refresh(p1)
    assert p1.quantity == Decimal("13")   # 仅回写一次


def test_approve_requires_submitted(db: Session):
    p1 = _part(db, qty="10")
    po = svc.create_purchase_order(db, PurchaseOrderCreate(vendor_id="v-1", lines=[
        POLineCreate(part_id=p1.id, quantity=Decimal("3"))]), CO, actor_user_id="a")
    with pytest.raises(HTTPException):   # DRAFT->APPROVED 非法
        svc.approve_purchase_order(db, po, "", CO, actor_user_id="a")
    db.refresh(p1)
    assert p1.quantity == Decimal("10")  # 未变
