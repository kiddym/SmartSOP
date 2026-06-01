"""多备件套件 API（/api/v1/multi-parts）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.multi_part import MultiPart
from app.models.user import User
from app.schemas.part import MultiPartCreate, MultiPartRead, MultiPartUpdate
from app.services import multi_part_service as svc

router = APIRouter(prefix="/api/v1/multi-parts", tags=["multi-parts"])


def _ensure(mp: MultiPart | None, company_id: str) -> MultiPart:
    if mp is None or mp.company_id != company_id:
        raise not_found("MULTI_PART_NOT_FOUND", "套件不存在")
    return mp


def _read(db: Session, mp: MultiPart) -> MultiPartRead:
    data = MultiPartRead.model_validate(mp)
    data.part_ids = svc.part_ids(db, mp.id)
    return data


@router.get("", response_model=list[MultiPartRead])
def list_multi_parts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> list[MultiPartRead]:
    return [_read(db, mp) for mp in svc.list_multi_parts(db)]


@router.post("", response_model=MultiPartRead, status_code=status.HTTP_201_CREATED)
def create_multi_part(
    payload: MultiPartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_CREATE)),
) -> MultiPartRead:
    mp = svc.create_multi_part(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, mp)


@router.get("/{multi_part_id}", response_model=MultiPartRead)
def get_multi_part(
    multi_part_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_VIEW)),
) -> MultiPartRead:
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    return _read(db, mp)


@router.patch("/{multi_part_id}", response_model=MultiPartRead)
def update_multi_part(
    multi_part_id: str,
    payload: MultiPartUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_EDIT)),
) -> MultiPartRead:
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    svc.update_multi_part(db, mp, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, mp)


@router.delete("/{multi_part_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_multi_part(
    multi_part_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.PART_DELETE)),
) -> None:
    mp = _ensure(svc.get_multi_part(db, multi_part_id), current_user.company_id)
    svc.delete_multi_part(db, mp)
