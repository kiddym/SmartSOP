"""成本分类 API（/api/v1/cost-categories）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.cost_category import CostCategory
from app.models.user import User
from app.schemas.partner import (
    CostCategoryCreate,
    CostCategoryRead,
    CostCategoryUpdate,
)
from app.services import cost_category_service as svc

router = APIRouter(prefix="/api/v1/cost-categories", tags=["cost-categories"])


def _ensure(c: CostCategory | None, company_id: str) -> CostCategory:
    if c is None or c.company_id != company_id:
        raise not_found("COST_CATEGORY_NOT_FOUND", "成本分类不存在")
    return c


@router.get("", response_model=list[CostCategoryRead])
def list_cost_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.COST_CATEGORY_VIEW)),
):
    return svc.list_cost_categories(db)


@router.post("", response_model=CostCategoryRead, status_code=status.HTTP_201_CREATED)
def create_cost_category(
    payload: CostCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE)),
):
    return svc.create_cost_category(
        db, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.get("/{category_id}", response_model=CostCategoryRead)
def get_cost_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.COST_CATEGORY_VIEW)),
):
    return _ensure(svc.get_cost_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=CostCategoryRead)
def update_cost_category(
    category_id: str,
    payload: CostCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE)),
):
    c = _ensure(svc.get_cost_category(db, category_id), current_user.company_id)
    return svc.update_cost_category(
        db, c, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cost_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.COST_CATEGORY_MANAGE)),
):
    c = _ensure(svc.get_cost_category(db, category_id), current_user.company_id)
    svc.delete_cost_category(db, c)
