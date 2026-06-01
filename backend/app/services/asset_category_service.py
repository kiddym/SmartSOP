"""资产分类服务（租户作用域由 ORM 事件 + 显式 company_id 双重保证）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_category import AssetCategory
from app.models.base import utcnow
from app.schemas.asset_category import AssetCategoryCreate, AssetCategoryUpdate


def create_category(db: Session, payload: AssetCategoryCreate, company_id: str) -> AssetCategory:
    cat = AssetCategory(name=payload.name, company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[AssetCategory]:
    return list(
        db.execute(select(AssetCategory).where(AssetCategory.is_active.is_(True))).scalars().all()
    )


def get_category(db: Session, category_id: str) -> AssetCategory | None:
    cat = db.get(AssetCategory, category_id)
    if cat is None or not cat.is_active:
        return None
    return cat


def update_category(db: Session, cat: AssetCategory, payload: AssetCategoryUpdate) -> AssetCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: AssetCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
