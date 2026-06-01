"""成本分类服务：CRUD（软删）。镜像 part_category_service。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.cost_category import CostCategory
from app.schemas.partner import CostCategoryCreate, CostCategoryUpdate


def create_cost_category(
    db: Session, payload: CostCategoryCreate, company_id: str, actor_user_id: str | None
) -> CostCategory:
    cat = CostCategory(name=payload.name, description=payload.description, company_id=company_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_cost_categories(db: Session) -> list[CostCategory]:
    return list(
        db.execute(
            select(CostCategory)
            .where(CostCategory.is_active.is_(True))
            .order_by(CostCategory.name, CostCategory.id)
        )
        .scalars()
        .all()
    )


def get_cost_category(db: Session, category_id: str) -> CostCategory | None:
    c = db.get(CostCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_cost_category(
    db: Session,
    cat: CostCategory,
    payload: CostCategoryUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> CostCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_cost_category(db: Session, cat: CostCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
