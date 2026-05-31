"""采购单服务：CRUD（软删）、行全量替换（draft-only）、状态机、审批入库。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.part import Part
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_status import PurchaseOrderStatus, can_transition
from app.schemas.purchase_order import (
    POLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services import sequence_service


def _log(db: Session, purchase_order_id: str, company_id: str, activity_type: str,
         actor_user_id: str | None = None, from_status: str | None = None,
         to_status: str | None = None, comment: str = "") -> None:
    db.add(PurchaseOrderActivity(
        purchase_order_id=purchase_order_id, company_id=company_id,
        activity_type=activity_type, actor_user_id=actor_user_id,
        from_status=from_status, to_status=to_status, comment=comment,
    ))


def lines(db: Session, purchase_order_id: str) -> list[PurchaseOrderLine]:
    return list(db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
        .order_by(PurchaseOrderLine.id)).scalars().all())


def _set_lines(db: Session, purchase_order_id: str, company_id: str,
               line_list: list[POLineCreate]) -> None:
    for ln in line_list:
        db.add(PurchaseOrderLine(
            purchase_order_id=purchase_order_id, part_id=ln.part_id,
            quantity=ln.quantity, unit_cost=ln.unit_cost, company_id=company_id,
        ))


def create_purchase_order(db: Session, payload: PurchaseOrderCreate, company_id: str,
                          actor_user_id: str | None) -> PurchaseOrder:
    seq = sequence_service.next_value(db, "purchase_order", company_id)
    po = PurchaseOrder(
        custom_id=sequence_service.format_custom_id("PO", seq),
        vendor_id=payload.vendor_id, notes=payload.notes, company_id=company_id,
    )
    db.add(po)
    db.flush()
    _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def list_purchase_orders(db: Session, *, status: str | None = None,
                         vendor_id: str | None = None) -> list[PurchaseOrder]:
    stmt = select(PurchaseOrder).where(PurchaseOrder.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(PurchaseOrder.status == status)
    if vendor_id is not None:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    return list(db.execute(stmt.order_by(PurchaseOrder.custom_id)).scalars().all())


def get_purchase_order(db: Session, purchase_order_id: str) -> PurchaseOrder | None:
    po = db.get(PurchaseOrder, purchase_order_id)
    if po is None or not po.is_active:
        return None
    return po


def _assert_draft(po: PurchaseOrder) -> None:
    if po.status != PurchaseOrderStatus.DRAFT:
        raise bad_request("PURCHASE_ORDER_NOT_DRAFT", "采购单非草稿，不可编辑")


def update_purchase_order(db: Session, po: PurchaseOrder, payload: PurchaseOrderUpdate,
                          company_id: str, actor_user_id: str | None) -> PurchaseOrder:
    _assert_draft(po)
    data = payload.model_dump(exclude_unset=True)
    data.pop("lines", None)
    for k, v in data.items():
        setattr(po, k, v)
    if payload.lines is not None:
        db.execute(PurchaseOrderLine.__table__.delete().where(
            PurchaseOrderLine.purchase_order_id == po.id))
        _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def delete_purchase_order(db: Session, po: PurchaseOrder) -> None:
    po.is_active = False
    po.deleted_at = utcnow()
    db.commit()
