"""采购单 API（/api/v1/purchase-orders）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.billing.catalog import Feature
from app.deps import get_db, require_feature, require_permission
from app.errors import not_found
from app.models.purchase_order import PurchaseOrder, PurchaseOrderActivity
from app.models.user import User
from app.schemas.purchase_order import (
    POActivityRead,
    POLineRead,
    POResolve,
    PurchaseOrderCreate,
    PurchaseOrderMini,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from app.services import purchase_order_service as svc

router = APIRouter(
    prefix="/api/v1/purchase-orders",
    tags=["purchase-orders"],
    dependencies=[Depends(require_feature(Feature.purchasing))],
)


def _ensure(po: PurchaseOrder | None, company_id: str) -> PurchaseOrder:
    if po is None or po.company_id != company_id:
        raise not_found("PURCHASE_ORDER_NOT_FOUND", "采购单不存在")
    return po


def _read(db: Session, po: PurchaseOrder) -> PurchaseOrderRead:
    data = PurchaseOrderRead.model_validate(po)
    line_reads = [POLineRead.model_validate(ln) for ln in svc.lines(db, po.id)]
    data.lines = line_reads
    data.total_cost = sum((lr.line_total for lr in line_reads), Decimal("0"))
    return data


@router.get("", response_model=list[PurchaseOrderRead])
def list_purchase_orders(
    status: str | None = None,
    vendor_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW)),
) -> list[PurchaseOrderRead]:
    return [
        _read(db, po) for po in svc.list_purchase_orders(db, status=status, vendor_id=vendor_id)
    ]


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_CREATE)),
) -> PurchaseOrderRead:
    po = svc.create_purchase_order(
        db, payload, current_user.company_id, actor_user_id=current_user.id
    )
    return _read(db, po)


# 注：/mini 必须注册在 /{po_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[PurchaseOrderMini])
def list_purchase_orders_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW)),
) -> list[PurchaseOrder]:
    return svc.list_purchase_orders(db)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    return _read(db, po)


@router.patch("/{po_id}", response_model=PurchaseOrderRead)
def update_purchase_order(
    po_id: str,
    payload: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.update_purchase_order(
        db, po, payload, current_user.company_id, actor_user_id=current_user.id
    )
    return _read(db, po)


@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_DELETE)),
) -> None:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.delete_purchase_order(db, po)


@router.post("/{po_id}/submit", response_model=PurchaseOrderRead)
def submit_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.submit_purchase_order(db, po, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, po)


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
def approve_purchase_order(
    po_id: str,
    payload: POResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_APPROVE)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.approve_purchase_order(
        db, po, payload.note, current_user.company_id, actor_user_id=current_user.id
    )
    return _read(db, po)


@router.post("/{po_id}/reject", response_model=PurchaseOrderRead)
def reject_purchase_order(
    po_id: str,
    payload: POResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_APPROVE)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.reject_purchase_order(
        db, po, payload.note, current_user.company_id, actor_user_id=current_user.id
    )
    return _read(db, po)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
def cancel_purchase_order(
    po_id: str,
    payload: POResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_EDIT)),
) -> PurchaseOrderRead:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    svc.cancel_purchase_order(
        db, po, payload.note, current_user.company_id, actor_user_id=current_user.id
    )
    return _read(db, po)


@router.get("/{po_id}/activities", response_model=list[POActivityRead])
def list_purchase_order_activities(
    po_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PURCHASE_ORDER_VIEW)),
) -> list[PurchaseOrderActivity]:
    po = _ensure(svc.get_purchase_order(db, po_id), current_user.company_id)
    return svc.list_activities(db, po.id)
