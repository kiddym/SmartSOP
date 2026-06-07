"""业务实体自定义字段定义 API（/api/v1/custom-fields）。读=任意认证，写=company.settings。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, require_permission
from app.models.custom_field_def import CustomFieldDef
from app.models.user import User
from app.schemas.custom_field import (
    CustomFieldCreate,
    CustomFieldOut,
    CustomFieldReorderIn,
    CustomFieldUpdate,
)
from app.services import custom_field_service as svc

router = APIRouter(prefix="/api/v1/custom-fields", tags=["custom-fields"])


@router.get("", response_model=list[CustomFieldOut])
def list_fields(
    entity_type: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CustomFieldDef]:
    return svc.list_defs(db, entity_type, include_archived=include_archived)


@router.post("", response_model=CustomFieldOut, status_code=status.HTTP_201_CREATED)
def create_field(
    payload: CustomFieldCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.create(db, payload)
    db.commit()
    return row


@router.patch("/{field_id}", response_model=CustomFieldOut)
def update_field(
    field_id: str,
    payload: CustomFieldUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.update(db, field_id, payload)
    db.commit()
    return row


@router.patch("/{field_id}/archive", response_model=CustomFieldOut)
def archive_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.set_status(db, field_id, "archived")
    db.commit()
    return row


@router.patch("/{field_id}/restore", response_model=CustomFieldOut)
def restore_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.set_status(db, field_id, "active")
    db.commit()
    return row


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> None:
    svc.delete(db, field_id)
    db.commit()


@router.post("/reorder", response_model=list[CustomFieldOut])
def reorder_fields(
    payload: CustomFieldReorderIn,
    entity_type: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> list[CustomFieldDef]:
    rows = svc.reorder(db, entity_type, payload.ordered_ids)
    db.commit()
    return rows
