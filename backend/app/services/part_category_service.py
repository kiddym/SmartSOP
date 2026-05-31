"""备件分类服务：CRUD（软删）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.part_category import PartCategory
from app.schemas.part import PartCategoryCreate, PartCategoryUpdate


def create_category(db: Session, payload: PartCategoryCreate, company_id: str,
                    actor_user_id: str | None) -> PartCategory:
    cat = PartCategory(name=payload.name, description=payload.description,
                       company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[PartCategory]:
    return list(db.execute(
        select(PartCategory).where(PartCategory.is_active.is_(True))
        .order_by(PartCategory.name, PartCategory.id)).scalars().all())


def get_category(db: Session, category_id: str) -> PartCategory | None:
    c = db.get(PartCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_category(db: Session, cat: PartCategory, payload: PartCategoryUpdate,
                    company_id: str, actor_user_id: str | None) -> PartCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: PartCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
