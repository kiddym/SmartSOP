"""计量分类 API（/api/v1/meter-categories）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.meter_category import MeterCategory
from app.models.user import User
from app.schemas.meter_category import (
    MeterCategoryCreate,
    MeterCategoryRead,
    MeterCategoryUpdate,
)
from app.services import meter_category_service

router = APIRouter(prefix="/api/v1/meter-categories", tags=["meter-categories"])


def _ensure(cat: MeterCategory | None, company_id: str) -> MeterCategory:
    if cat is None or cat.company_id != company_id:
        raise not_found("METER_CATEGORY_NOT_FOUND", "计量分类不存在")
    return cat


@router.get("", response_model=list[MeterCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CATEGORY_VIEW)),
) -> list[MeterCategory]:
    return meter_category_service.list_categories(db)


@router.post("", response_model=MeterCategoryRead, status_code=201)
def create_category(
    payload: MeterCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CATEGORY_MANAGE)),
) -> MeterCategory:
    return meter_category_service.create_category(db, payload, current_user.company_id)


@router.patch("/{category_id}", response_model=MeterCategoryRead)
def update_category(
    category_id: str,
    payload: MeterCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CATEGORY_MANAGE)),
) -> MeterCategory:
    cat = _ensure(
        meter_category_service.get_category(db, category_id), current_user.company_id
    )
    return meter_category_service.update_category(db, cat, payload)


@router.delete("/{category_id}", status_code=204, response_model=None)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.METER_CATEGORY_MANAGE)),
) -> None:
    cat = _ensure(
        meter_category_service.get_category(db, category_id), current_user.company_id
    )
    meter_category_service.delete_category(db, cat)
