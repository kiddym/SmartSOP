"""工单分类服务：CRUD（软删）。镜像 time_category_service。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict
from app.models.base import utcnow
from app.models.work_order_category import WorkOrderCategory
from app.schemas.work_order_category import (
    WorkOrderCategoryCreate,
    WorkOrderCategoryUpdate,
)


def create_category(
    db: Session, payload: WorkOrderCategoryCreate, company_id: str
) -> WorkOrderCategory:
    dup = db.execute(
        select(WorkOrderCategory).where(
            WorkOrderCategory.is_active.is_(True), WorkOrderCategory.name == payload.name
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise conflict("WORK_ORDER_CATEGORY_DUPLICATE", "工单分类名称已存在")
    cat = WorkOrderCategory(
        name=payload.name, description=payload.description, company_id=company_id
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[WorkOrderCategory]:
    return list(
        db.execute(
            select(WorkOrderCategory)
            .where(WorkOrderCategory.is_active.is_(True))
            .order_by(WorkOrderCategory.name, WorkOrderCategory.id)
        )
        .scalars()
        .all()
    )


def get_category(db: Session, category_id: str) -> WorkOrderCategory | None:
    c = db.get(WorkOrderCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_category(
    db: Session, cat: WorkOrderCategory, payload: WorkOrderCategoryUpdate
) -> WorkOrderCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: WorkOrderCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
