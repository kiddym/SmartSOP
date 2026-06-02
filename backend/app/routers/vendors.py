"""供应商 API（/api/v1/vendors）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.partner import VendorCreate, VendorMini, VendorRead, VendorUpdate
from app.services import vendor_service as svc

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])


def _ensure(v: Vendor | None, company_id: str) -> Vendor:
    if v is None or v.company_id != company_id:
        raise not_found("VENDOR_NOT_FOUND", "供应商不存在")
    return v


def _read(db: Session, v: Vendor) -> VendorRead:
    data = VendorRead.model_validate(v)
    data.part_ids = svc.part_ids(db, v.id)
    data.asset_ids = svc.asset_ids(db, v.id)
    data.location_ids = svc.location_ids(db, v.id)
    return data


@router.get("", response_model=list[VendorRead])
def list_vendors(
    part_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_VIEW)),
) -> list[VendorRead]:
    return [_read(db, v) for v in svc.list_vendors(db, part_id=part_id)]


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_CREATE)),
) -> VendorRead:
    v = svc.create_vendor(db, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, v)


# 注：/mini 必须注册在 /{vendor_id} 之前，否则会被路径参数吞掉
@router.get("/mini", response_model=list[VendorMini])
def list_vendors_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_VIEW)),
) -> list[Vendor]:
    return svc.list_vendors(db)


@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_VIEW)),
) -> VendorRead:
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    return _read(db, v)


@router.patch("/{vendor_id}", response_model=VendorRead)
def update_vendor(
    vendor_id: str,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_EDIT)),
) -> VendorRead:
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    svc.update_vendor(db, v, payload, current_user.company_id, actor_user_id=current_user.id)
    return _read(db, v)


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.VENDOR_DELETE)),
) -> None:
    v = _ensure(svc.get_vendor(db, vendor_id), current_user.company_id)
    svc.delete_vendor(db, v)
