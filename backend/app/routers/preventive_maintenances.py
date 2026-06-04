"""预防性维护 API（/api/v1/preventive-maintenances）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.pm_activity import PMActivity
from app.models.preventive_maintenance import PreventiveMaintenance
from app.models.user import User
from app.schemas.pm import (
    CommentCreate,
    PMActivityRead,
    PMCreate,
    PMRead,
    PMUpdate,
)
from app.schemas.work_order import WorkOrderRead
from app.services import pm_service as svc

router = APIRouter(prefix="/api/v1/preventive-maintenances", tags=["preventive-maintenances"])


def _ensure(pm: PreventiveMaintenance | None, company_id: str) -> PreventiveMaintenance:
    if pm is None or pm.company_id != company_id:
        raise not_found("PM_NOT_FOUND", "预防性维护不存在")
    return pm


def _read(db: Session, pm: PreventiveMaintenance) -> PMRead:
    data = PMRead.model_validate(pm)
    data.assignee_ids = svc.assignee_ids(db, pm.id)
    data.team_ids = svc.team_ids(db, pm.id)
    return data


@router.get("", response_model=list[PMRead])
def list_pms(
    is_enabled: bool | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_VIEW)),
) -> list[PMRead]:
    pms = svc.list_pms(db, is_enabled=is_enabled, asset_id=asset_id, location_id=location_id)
    return [_read(db, pm) for pm in pms]


@router.post("", response_model=PMRead, status_code=status.HTTP_201_CREATED)
def create_pm(
    payload: PMCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_CREATE)),
) -> PMRead:
    pm = svc.create_pm(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, pm)


@router.get("/{pm_id}", response_model=PMRead)
def get_pm(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_VIEW)),
) -> PMRead:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    return _read(db, pm)


@router.patch("/{pm_id}", response_model=PMRead)
def update_pm(
    pm_id: str,
    payload: PMUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_EDIT)),
) -> PMRead:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    svc.update_pm(db, pm, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, pm)


@router.delete("/{pm_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_pm(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_DELETE)),
) -> None:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    svc.delete_pm(db, pm)


@router.post("/{pm_id}/enable", response_model=PMRead)
def enable_pm(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_EDIT)),
) -> PMRead:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    svc.enable_pm(db, pm, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, pm)


@router.post("/{pm_id}/disable", response_model=PMRead)
def disable_pm(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_EDIT)),
) -> PMRead:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    svc.disable_pm(db, pm, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, pm)


@router.post("/{pm_id}/generate", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
def generate_now(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_CREATE)),
) -> dict[str, object]:
    from app.models.base import utcnow
    from app.services import work_order_service as wos

    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    wo = svc.generate_once(db, pm, actor_user_id=current_user.id, now=utcnow(), enforce_due=False)
    return wos.to_read(db, wo, viewer=current_user)


@router.get("/{pm_id}/activities", response_model=list[PMActivityRead])
def list_activities(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_VIEW)),
) -> list[PMActivity]:
    _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    return svc.list_activities(db, pm_id)


@router.post(
    "/{pm_id}/comments", response_model=PMActivityRead, status_code=status.HTTP_201_CREATED
)
def add_comment(
    pm_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PREVENTIVE_MAINTENANCE_VIEW)),
) -> PMActivity:
    pm = _ensure(svc.get_pm(db, pm_id), current_user.company_id)
    return svc.add_comment(
        db, pm, payload.comment, current_user.company_id, actor_user_id=current_user.id
    )
