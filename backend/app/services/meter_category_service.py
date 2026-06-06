"""计量分类服务（租户作用域由 ORM 事件 + 显式 company_id 双重保证）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.meter_category import MeterCategory
from app.schemas.meter_category import MeterCategoryCreate, MeterCategoryUpdate


def create_category(db: Session, payload: MeterCategoryCreate, company_id: str) -> MeterCategory:
    cat = MeterCategory(name=payload.name, description=payload.description, company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[MeterCategory]:
    return list(
        db.execute(select(MeterCategory).where(MeterCategory.is_active.is_(True))).scalars().all()
    )


def get_category(db: Session, category_id: str) -> MeterCategory | None:
    cat = db.get(MeterCategory, category_id)
    if cat is None or not cat.is_active:
        return None
    return cat


def update_category(db: Session, cat: MeterCategory, payload: MeterCategoryUpdate) -> MeterCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: MeterCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
