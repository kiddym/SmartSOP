"""位置平面图 API（/api/v1/locations/{location_id}/floor-plans）。

平面图与位置 1:N。GET 列表 / POST 新建(201) / PATCH /{id} / DELETE /{id}(204)。
读权限复用 LOCATION_VIEW、写权限复用 LOCATION_EDIT。先校验 location 属当前 company；
平面图须既存且属同一 location，否则 404。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.floor_plan import FloorPlan
from app.models.user import User
from app.schemas.floor_plan import FloorPlanCreate, FloorPlanRead, FloorPlanUpdate
from app.services import floor_plan_service as svc
from app.services import location_service as locations

router = APIRouter(prefix="/api/v1/locations/{location_id}/floor-plans", tags=["floor-plans"])


def _ensure_location(db: Session, location_id: str, company_id: str) -> None:
    loc = locations.get_location(db, location_id)
    if loc is None or loc.company_id != company_id:
        raise not_found("LOCATION_NOT_FOUND", "位置不存在")


def _get_owned(db: Session, location_id: str, floor_plan_id: str) -> FloorPlan:
    row = svc.get(db, floor_plan_id)
    if row is None or row.location_id != location_id:
        raise not_found("FLOOR_PLAN_NOT_FOUND", "平面图不存在")
    return row


@router.get("", response_model=list[FloorPlanRead])
def list_floor_plans(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_VIEW)),
) -> list[FloorPlan]:
    _ensure_location(db, location_id, current_user.company_id)
    return svc.list_by_location(db, location_id)


@router.post("", response_model=FloorPlanRead, status_code=status.HTTP_201_CREATED)
def create_floor_plan(
    location_id: str,
    payload: FloorPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_EDIT)),
) -> FloorPlan:
    _ensure_location(db, location_id, current_user.company_id)
    return svc.create(db, location_id, current_user.company_id, payload)


@router.patch("/{floor_plan_id}", response_model=FloorPlanRead)
def update_floor_plan(
    location_id: str,
    floor_plan_id: str,
    payload: FloorPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_EDIT)),
) -> FloorPlan:
    _ensure_location(db, location_id, current_user.company_id)
    row = _get_owned(db, location_id, floor_plan_id)
    return svc.update(db, row, payload)


@router.delete("/{floor_plan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_floor_plan(
    location_id: str,
    floor_plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.LOCATION_EDIT)),
) -> None:
    _ensure_location(db, location_id, current_user.company_id)
    row = _get_owned(db, location_id, floor_plan_id)
    svc.delete(db, row)
