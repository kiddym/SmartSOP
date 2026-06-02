"""工时分类 API（/api/v1/time-categories）。镜像 cost-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.time_category import TimeCategory
from app.models.user import User
from app.schemas.work_order_cost import (
    TimeCategoryCreate,
    TimeCategoryRead,
    TimeCategoryUpdate,
)
from app.services import time_category_service as svc

router = APIRouter(prefix="/api/v1/time-categories", tags=["time-categories"])


def _ensure(c: TimeCategory | None, company_id: str) -> TimeCategory:
    if c is None or c.company_id != company_id:
        raise not_found("TIME_CATEGORY_NOT_FOUND", "工时分类不存在")
    return c


@router.get("", response_model=list[TimeCategoryRead])
def list_time_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_VIEW)),
) -> list[TimeCategory]:
    return svc.list_time_categories(db)


@router.post("", response_model=TimeCategoryRead, status_code=status.HTTP_201_CREATED)
def create_time_category(
    payload: TimeCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> TimeCategory:
    return svc.create_time_category(
        db, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.get("/{category_id}", response_model=TimeCategoryRead)
def get_time_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_VIEW)),
) -> TimeCategory:
    return _ensure(svc.get_time_category(db, category_id), current_user.company_id)


@router.patch("/{category_id}", response_model=TimeCategoryRead)
def update_time_category(
    category_id: str,
    payload: TimeCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> TimeCategory:
    c = _ensure(svc.get_time_category(db, category_id), current_user.company_id)
    return svc.update_time_category(
        db, c, payload, current_user.company_id, actor_user_id=current_user.id
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_time_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TIME_CATEGORY_MANAGE)),
) -> None:
    c = _ensure(svc.get_time_category(db, category_id), current_user.company_id)
    svc.delete_time_category(db, c)
