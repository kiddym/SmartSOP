"""采购单服务：CRUD（软删）、行全量替换（draft-only）、状态机、审批入库。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.part import Part
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_category import PurchaseOrderCategory
from app.models.purchase_order_status import PurchaseOrderStatus, can_transition
from app.schemas.purchase_order import (
    POLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services import sequence_service


def _log(
    db: Session,
    purchase_order_id: str,
    company_id: str,
    activity_type: str,
    actor_user_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    comment: str = "",
) -> None:
    db.add(
        PurchaseOrderActivity(
            purchase_order_id=purchase_order_id,
            company_id=company_id,
            activity_type=activity_type,
            actor_user_id=actor_user_id,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
        )
    )


def lines(db: Session, purchase_order_id: str) -> list[PurchaseOrderLine]:
    # 按录入行序 line_no 稳定排序（id 是随机 UUID，不可用作顺序）；line_no 同值再以 id 兜底。
    return list(
        db.execute(
            select(PurchaseOrderLine)
            .where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
            .order_by(PurchaseOrderLine.line_no, PurchaseOrderLine.id)
        )
        .scalars()
        .all()
    )


def _set_lines(
    db: Session, purchase_order_id: str, company_id: str, line_list: list[POLineCreate]
) -> None:
    for i, ln in enumerate(line_list):
        db.add(
            PurchaseOrderLine(
                purchase_order_id=purchase_order_id,
                line_no=i,
                part_id=ln.part_id,
                quantity=ln.quantity,
                unit_cost=ln.unit_cost,
                company_id=company_id,
            )
        )


def _validate_category_id(db: Session, category_id: str | None, company_id: str) -> None:
    if category_id is None:
        return
    cat = db.get(PurchaseOrderCategory, category_id)
    if cat is None or not cat.is_active or cat.company_id != company_id:
        raise not_found("PURCHASE_ORDER_CATEGORY_NOT_FOUND", "采购单分类不存在")


def create_purchase_order(
    db: Session, payload: PurchaseOrderCreate, company_id: str, actor_user_id: str | None
) -> PurchaseOrder:
    _validate_category_id(db, payload.category_id, company_id)
    seq = sequence_service.next_value(db, "purchase_order", company_id)
    po = PurchaseOrder(
        custom_id=sequence_service.format_custom_id("PO", seq),
        vendor_id=payload.vendor_id,
        notes=payload.notes,
        category_id=payload.category_id,
        shipping_address=payload.shipping_address,
        shipping_method=payload.shipping_method,
        terms_of_payment=payload.terms_of_payment,
        expected_delivery_date=payload.expected_delivery_date,
        company_id=company_id,
    )
    db.add(po)
    db.flush()
    _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def list_purchase_orders(
    db: Session, *, status: str | None = None, vendor_id: str | None = None
) -> list[PurchaseOrder]:
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


def update_purchase_order(
    db: Session,
    po: PurchaseOrder,
    payload: PurchaseOrderUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> PurchaseOrder:
    _assert_draft(po)
    data = payload.model_dump(exclude_unset=True)
    data.pop("lines", None)
    if "category_id" in data:
        _validate_category_id(db, data["category_id"], company_id)
    for k, v in data.items():
        setattr(po, k, v)
    if payload.lines is not None:
        db.execute(delete(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id))
        _set_lines(db, po.id, company_id, payload.lines)
    db.commit()
    db.refresh(po)
    return po


def delete_purchase_order(db: Session, po: PurchaseOrder) -> None:
    po.is_active = False
    po.deleted_at = utcnow()
    db.commit()


def list_activities(db: Session, purchase_order_id: str) -> list[PurchaseOrderActivity]:
    return list(
        db.execute(
            select(PurchaseOrderActivity)
            .where(PurchaseOrderActivity.purchase_order_id == purchase_order_id)
            .order_by(PurchaseOrderActivity.created_at, PurchaseOrderActivity.id)
        )
        .scalars()
        .all()
    )


def submit_purchase_order(
    db: Session, po: PurchaseOrder, company_id: str, actor_user_id: str | None
) -> PurchaseOrder:
    if not can_transition(po.status, PurchaseOrderStatus.SUBMITTED):
        raise bad_request(
            "PURCHASE_ORDER_BAD_TRANSITION", f"非法状态转移 {po.status.value}->SUBMITTED"
        )
    if not lines(db, po.id):
        raise bad_request("PURCHASE_ORDER_EMPTY", "采购单无明细行，不可提交")
    from_status = po.status.value
    po.status = PurchaseOrderStatus.SUBMITTED
    _log(
        db,
        po.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=PurchaseOrderStatus.SUBMITTED.value,
    )
    from app.services import notification_service as _notif

    _notif.on_po_submitted(db, po, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(po)
    return po


def _resolve(
    db: Session,
    po: PurchaseOrder,
    dst: PurchaseOrderStatus,
    note: str,
    company_id: str,
    actor_user_id: str | None,
) -> PurchaseOrder:
    if not can_transition(po.status, dst):
        raise bad_request(
            "PURCHASE_ORDER_BAD_TRANSITION", f"非法状态转移 {po.status.value}->{dst.value}"
        )
    from_status = po.status.value
    po.status = dst
    po.resolution_note = note
    po.resolved_by_user_id = actor_user_id
    po.resolved_at = utcnow()
    _log(
        db,
        po.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=dst.value,
        comment=note,
    )
    db.commit()
    db.refresh(po)
    return po


def reject_purchase_order(
    db: Session, po: PurchaseOrder, note: str, company_id: str, actor_user_id: str | None
) -> PurchaseOrder:
    return _resolve(db, po, PurchaseOrderStatus.REJECTED, note, company_id, actor_user_id)


def cancel_purchase_order(
    db: Session, po: PurchaseOrder, note: str, company_id: str, actor_user_id: str | None
) -> PurchaseOrder:
    return _resolve(db, po, PurchaseOrderStatus.CANCELED, note, company_id, actor_user_id)


def approve_purchase_order(
    db: Session, po: PurchaseOrder, note: str, company_id: str, actor_user_id: str | None
) -> PurchaseOrder:
    """审批通过=整单入库：逐行把数量加回 Part.quantity（non_stock 跳过、不报错）。

    终态守卫（can_transition）保证库存恰好回写一次；单次 commit。
    """
    if not can_transition(po.status, PurchaseOrderStatus.APPROVED):
        raise bad_request(
            "PURCHASE_ORDER_BAD_TRANSITION", f"非法状态转移 {po.status.value}->APPROVED"
        )
    for ln in lines(db, po.id):
        part = db.get(Part, ln.part_id)
        if part is not None and part.is_active and not part.non_stock:
            part.quantity = part.quantity + ln.quantity
    from_status = po.status.value
    po.status = PurchaseOrderStatus.APPROVED
    po.resolution_note = note
    po.resolved_by_user_id = actor_user_id
    po.resolved_at = utcnow()
    _log(
        db,
        po.id,
        company_id,
        "STATUS_CHANGE",
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=PurchaseOrderStatus.APPROVED.value,
        comment=note,
    )
    _log(db, po.id, company_id, "RECEIVED", actor_user_id=actor_user_id)
    from app.services import notification_service as _notif

    _notif.on_po_approved(db, po, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(po)
    return po
