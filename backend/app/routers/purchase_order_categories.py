"""采购单分类 API（/api/v1/purchase-order-categories）。镜像 time-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.purchase_order_category import PurchaseOrderCategory
from app.models.user import User
from app.schemas.purchase_order_category import (
    PurchaseOrderCategoryCreate,
    PurchaseOrderCategoryRead,
    PurchaseOrderCategoryUpdate,
)
from app.services import purchase_order_category_service as svc

router = APIRouter(
    prefix="/api/v1/purchase-order-categories", tags=["purchase-order-categories"]
)


def _ensure(c: PurchaseOrderCategory | None, company_id: str) -> PurchaseOrderCategory:
    if c is None or c.company_id != company_id:
        raise not_found("PURCHASE_ORDER_CATEGORY_NOT_FOUND", "采购单分类不存在")
    return c


@router.get("", response_model=list[PurchaseOrderCategoryRead])
def list_purchase_order_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(permissions.PURCHASE_ORDER_CATEGORY_VIEW)
    ),
) -> list[PurchaseOrderCategory]:
    return svc.list_categories(db)


@router.post(
    "", response_model=PurchaseOrderCategoryRead, status_code=status.HTTP_201_CREATED
)
def create_purchase_order_category(
    payload: PurchaseOrderCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(permissions.PURCHASE_ORDER_CATEGORY_MANAGE)
    ),
) -> PurchaseOrderCategory:
    return svc.create_category(
        db, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.get("/{category_id}", response_model=PurchaseOrderCategoryRead)
def get_purchase_order_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(permissions.PURCHASE_ORDER_CATEGORY_VIEW)
    ),
) -> PurchaseOrderCategory:
    return _ensure(svc.get_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=PurchaseOrderCategoryRead)
def update_purchase_order_category(
    category_id: str,
    payload: PurchaseOrderCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(permissions.PURCHASE_ORDER_CATEGORY_MANAGE)
    ),
) -> PurchaseOrderCategory:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    return svc.update_category(
        db, c, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_purchase_order_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(permissions.PURCHASE_ORDER_CATEGORY_MANAGE)
    ),
) -> None:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    svc.delete_category(db, c)
