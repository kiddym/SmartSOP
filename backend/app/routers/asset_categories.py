"""资产分类 API（/api/v1/asset-categories）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.asset_category import AssetCategory
from app.models.user import User
from app.schemas.asset_category import (
    AssetCategoryCreate,
    AssetCategoryRead,
    AssetCategoryUpdate,
)
from app.services import asset_category_service

router = APIRouter(prefix="/api/v1/asset-categories", tags=["asset-categories"])


def _ensure(cat: AssetCategory | None, company_id: str) -> AssetCategory:
    if cat is None or cat.company_id != company_id:
        raise not_found("ASSET_CATEGORY_NOT_FOUND", "资产分类不存在")
    return cat


@router.get("", response_model=list[AssetCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_VIEW)),
):
    return asset_category_service.list_categories(db)


@router.post("", response_model=AssetCategoryRead, status_code=201)
def create_category(
    payload: AssetCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE)),
):
    return asset_category_service.create_category(db, payload, current_user.company_id)


@router.patch("/{category_id}", response_model=AssetCategoryRead)
def update_category(
    category_id: str,
    payload: AssetCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE)),
):
    cat = _ensure(asset_category_service.get_category(db, category_id), current_user.company_id)
    return asset_category_service.update_category(db, cat, payload)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.ASSET_CATEGORY_MANAGE)),
):
    cat = _ensure(asset_category_service.get_category(db, category_id), current_user.company_id)
    asset_category_service.delete_category(db, cat)
