"""备件分类 API（/api/v1/part-categories）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.part_category import PartCategory
from app.models.user import User
from app.schemas.part import (
    PartCategoryCreate,
    PartCategoryRead,
    PartCategoryUpdate,
)
from app.services import part_category_service as svc

router = APIRouter(prefix="/api/v1/part-categories", tags=["part-categories"])


def _ensure(c: PartCategory | None, company_id: str) -> PartCategory:
    if c is None or c.company_id != company_id:
        raise not_found("PART_CATEGORY_NOT_FOUND", "备件分类不存在")
    return c


@router.get("", response_model=list[PartCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_VIEW)),
) -> list[PartCategory]:
    return svc.list_categories(db)


@router.post("", response_model=PartCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: PartCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE)),
) -> PartCategory:
    return svc.create_category(db, payload, current_user.company_id, actor_user_id=current_user.id)


@router.get("/{category_id}", response_model=PartCategoryRead)
def get_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_VIEW)),
) -> PartCategory:
    return _ensure(svc.get_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=PartCategoryRead)
def update_category(
    category_id: str,
    payload: PartCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE)),
) -> PartCategory:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    return svc.update_category(
        db, c, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CATEGORY_MANAGE)),
) -> None:
    c = _ensure(svc.get_category(db, category_id), current_user.company_id)
    svc.delete_category(db, c)
