"""CMMS 资产 API（/api/v1/assets）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.models.user import User
from app.schemas.asset import (
    AssetCreate,
    AssetMini,
    AssetRead,
    AssetUpdate,
    DowntimeClose,
    DowntimeCreate,
    DowntimeRead,
)
from app.services import maintenance_asset_service as svc

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _ensure(a: Asset | None, company_id: str) -> Asset:
    if a is None or a.company_id != company_id:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return a


def _ensure_dt(dt: AssetDowntime | None, asset_id: str, company_id: str) -> AssetDowntime:
    if dt is None or dt.asset_id != asset_id or dt.company_id != company_id:
        raise not_found("DOWNTIME_NOT_FOUND", "停机记录不存在")
    return dt


@router.get("", response_model=list[AssetRead])
def list_assets(
    location_id: str | None = None,
    category_id: str | None = None,
    status: str | None = None,
    parent_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> list[dict[str, object]]:
    rows = svc.list_assets(
        db, location_id=location_id, category_id=category_id, status=status, parent_id=parent_id
    )
    return [svc.to_read(db, a) for a in rows]


@router.get("/mini", response_model=list[AssetMini])
def list_mini(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> list[Asset]:
    return svc.list_assets(db)


@router.get("/by-barcode/{code}", response_model=AssetRead)
def get_by_barcode(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> dict[str, object]:
    a = svc.get_by_barcode(db, code)
    if a is None:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return svc.to_read(db, a)


@router.get("/by-nfc/{nfc}", response_model=AssetRead)
def get_by_nfc(
    nfc: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> dict[str, object]:
    a = svc.get_by_nfc(db, nfc)
    if a is None:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")
    return svc.to_read(db, a)


@router.post("", response_model=AssetRead, status_code=201)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_CREATE)),
) -> dict[str, object]:
    a = svc.create_asset(db, payload, current_user.company_id)
    return svc.to_read(db, a)


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> dict[str, object]:
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.to_read(db, a)


@router.get("/{asset_id}/children", response_model=list[AssetRead])
def list_children(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> list[dict[str, object]]:
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return [svc.to_read(db, a) for a in svc.list_children(db, asset_id)]


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_EDIT)),
) -> dict[str, object]:
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    a = svc.update_asset(db, a, payload, current_user.company_id)
    return svc.to_read(db, a)


@router.delete("/{asset_id}", status_code=204, response_model=None)
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_DELETE)),
) -> None:
    a = _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    svc.delete_asset(db, a)


@router.post("/{asset_id}/downtimes", response_model=DowntimeRead, status_code=201)
def add_downtime(
    asset_id: str,
    payload: DowntimeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_EDIT)),
) -> AssetDowntime:
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.add_downtime(db, asset_id, payload, current_user.company_id)


@router.get("/{asset_id}/downtimes", response_model=list[DowntimeRead])
def list_downtimes(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> list[AssetDowntime]:
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    return svc.list_downtimes(db, asset_id)


@router.patch("/{asset_id}/downtimes/{downtime_id}", response_model=DowntimeRead)
def close_downtime(
    asset_id: str,
    downtime_id: str,
    payload: DowntimeClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_EDIT)),
) -> AssetDowntime:
    _ensure(svc.get_asset(db, asset_id), current_user.company_id)
    dt = _ensure_dt(svc.get_downtime(db, downtime_id), asset_id, current_user.company_id)
    return svc.close_downtime(db, dt, payload)
