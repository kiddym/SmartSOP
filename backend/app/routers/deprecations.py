"""资产折旧 API（/api/v1/assets/{asset_id}/deprecation）。

折旧与资产 1:1。GET 取（无则返回 null）/ PUT upsert / DELETE 204。
读权限复用 ASSET_VIEW、写权限复用 ASSET_EDIT。先校验 asset 属当前 company。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.deprecation import AssetDeprecation
from app.models.user import User
from app.schemas.deprecation import DeprecationRead, DeprecationUpdate
from app.services import deprecation_service as svc
from app.services import maintenance_asset_service as assets

router = APIRouter(prefix="/api/v1/assets/{asset_id}/deprecation", tags=["deprecations"])


def _ensure_asset(db: Session, asset_id: str, company_id: str) -> None:
    asset = assets.get_asset(db, asset_id)
    if asset is None or asset.company_id != company_id:
        raise not_found("ASSET_NOT_FOUND", "资产不存在")


@router.get("", response_model=DeprecationRead | None)
def get_deprecation(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_VIEW)),
) -> AssetDeprecation | None:
    _ensure_asset(db, asset_id, current_user.company_id)
    return svc.get_by_asset(db, asset_id)


@router.put("", response_model=DeprecationRead)
def put_deprecation(
    asset_id: str,
    payload: DeprecationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_EDIT)),
) -> AssetDeprecation:
    _ensure_asset(db, asset_id, current_user.company_id)
    return svc.upsert(db, asset_id, current_user.company_id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_deprecation(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_EDIT)),
) -> None:
    _ensure_asset(db, asset_id, current_user.company_id)
    row = svc.get_by_asset(db, asset_id)
    if row is None:
        raise not_found("DEPRECATION_NOT_FOUND", "折旧信息不存在")
    svc.delete(db, row)
