"""工单分类 API（/api/v1/work-order-categories）。镜像 time-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order_category import WorkOrderCategory
from app.schemas.work_order_category import (
    WorkOrderCategoryCreate,
    WorkOrderCategoryRead,
    WorkOrderCategoryUpdate,
)
from app.services import work_order_category_service as svc

router = APIRouter(prefix="/api/v1/work-order-categories", tags=["work-order-categories"])


def _ensure(c: WorkOrderCategory | None, company_id: str) -> WorkOrderCategory:
    if c is None or c.company_id != company_id:
        raise not_found("WORK_ORDER_CATEGORY_NOT_FOUND", "工单分类不存在")
    return c


@router.get("", response_model=list[WorkOrderCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_VIEW)),
) -> list[WorkOrderCategory]:
    return svc.list_categories(db)


@router.post("", response_model=WorkOrderCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: WorkOrderCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> WorkOrderCategory:
    return svc.create_category(db, payload, current_user.company_id)


@router.get("/{category_id}", response_model=WorkOrderCategoryRead)
def get_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_VIEW)),
) -> WorkOrderCategory:
    return _ensure(svc.get_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=WorkOrderCategoryRead)
def update_category(
    category_id: str,
    payload: WorkOrderCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> WorkOrderCategory:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    return svc.update_category(db, c, payload)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_CATEGORY_MANAGE)),
) -> None:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    svc.delete_category(db, c)
