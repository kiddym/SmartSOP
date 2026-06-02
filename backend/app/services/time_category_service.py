"""工时分类服务：CRUD（软删）。镜像 cost_category_service。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.time_category import TimeCategory
from app.schemas.work_order_cost import TimeCategoryCreate, TimeCategoryUpdate


def create_time_category(
    db: Session, payload: TimeCategoryCreate, company_id: str, actor_user_id: str | None
) -> TimeCategory:
    cat = TimeCategory(
        name=payload.name,
        hourly_rate=payload.hourly_rate,
        description=payload.description,
        company_id=company_id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_time_categories(db: Session) -> list[TimeCategory]:
    return list(
        db.execute(
            select(TimeCategory)
            .where(TimeCategory.is_active.is_(True))
            .order_by(TimeCategory.name, TimeCategory.id)
        )
        .scalars()
        .all()
    )


def get_time_category(db: Session, category_id: str) -> TimeCategory | None:
    c = db.get(TimeCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_time_category(
    db: Session,
    cat: TimeCategory,
    payload: TimeCategoryUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> TimeCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_time_category(db: Session, cat: TimeCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
