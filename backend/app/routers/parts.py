"""备件 API（/api/v1/parts）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.part import Part
from app.models.user import User
from app.schemas.part import PartCreate, PartMini, PartRead, PartUpdate
from app.schemas.work_order import WorkOrderRead
from app.services import part_service as svc
from app.services import work_order_service as wo_svc

router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


def _ensure_part(p: Part | None, company_id: str) -> Part:
    if p is None or p.company_id != company_id:
        raise not_found("PART_NOT_FOUND", "备件不存在")
    return p


def _read_part(db: Session, p: Part) -> PartRead:
    data = PartRead.model_validate(p)
    data.assignee_ids = svc.assignee_ids(db, p.id)
    data.team_ids = svc.team_ids(db, p.id)
    data.asset_ids = svc.asset_ids(db, p.id)
    data.location_ids = svc.location_ids(db, p.id)
    data.pm_ids = svc.pm_ids(db, p.id)
    data.vendor_ids = svc.vendor_ids(db, p.id)
    data.customer_ids = svc.customer_ids(db, p.id)
    return data


@router.get("", response_model=list[PartRead])
def list_parts(
    category_id: str | None = None,
    asset_id: str | None = None,
    low_stock: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> list[PartRead]:
    return [
        _read_part(db, p)
        for p in svc.list_parts(db, category_id=category_id, asset_id=asset_id, low_stock=low_stock)
    ]


@router.post("", response_model=PartRead, status_code=status.HTTP_201_CREATED)
def create_part(
    payload: PartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CREATE)),
) -> PartRead:
    p = svc.create_part(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_part(db, p)


# 注：/mini 必须注册在 /{part_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[PartMini])
def list_parts_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> list[Part]:
    return svc.list_parts(db)


@router.get("/{part_id}", response_model=PartRead)
def get_part(
    part_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> PartRead:
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    return _read_part(db, p)


@router.get("/{part_id}/work-orders", response_model=list[WorkOrderRead])
def list_part_work_orders(
    part_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW)),
) -> list[dict[str, object]]:
    """反查：消耗过该备件的工单（经 PartConsumption 去重，当前租户隔离）。"""
    _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    rows = wo_svc.list_work_orders(db, part_id=part_id)
    return [wo_svc.to_read(db, w, viewer=current_user) for w in rows]


@router.patch("/{part_id}", response_model=PartRead)
def update_part(
    part_id: str,
    payload: PartUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_EDIT)),
) -> PartRead:
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    svc.update_part(db, p, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read_part(db, p)


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_part(
    part_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_DELETE)),
) -> None:
    p = _ensure_part(svc.get_part(db, part_id), current_user.company_id)
    svc.delete_part(db, p)
