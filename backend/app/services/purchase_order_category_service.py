"""采购单分类服务：CRUD（软删）。create 校验同租户重名（409）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict
from app.models.base import utcnow
from app.models.purchase_order_category import PurchaseOrderCategory
from app.schemas.purchase_order_category import (
    PurchaseOrderCategoryCreate,
    PurchaseOrderCategoryUpdate,
)


def _name_taken(db: Session, company_id: str, name: str) -> bool:
    return (
        db.execute(
            select(PurchaseOrderCategory.id).where(
                PurchaseOrderCategory.company_id == company_id,
                PurchaseOrderCategory.name == name,
                PurchaseOrderCategory.is_active.is_(True),
            )
        ).first()
        is not None
    )


def create_category(
    db: Session, payload: PurchaseOrderCategoryCreate, company_id: str, actor_user_id: str | None
) -> PurchaseOrderCategory:
    if _name_taken(db, company_id, payload.name):
        raise conflict("PURCHASE_ORDER_CATEGORY_DUPLICATE", "采购单分类名称已存在")
    cat = PurchaseOrderCategory(
        name=payload.name, description=payload.description, company_id=company_id
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session) -> list[PurchaseOrderCategory]:
    return list(
        db.execute(
            select(PurchaseOrderCategory)
            .where(PurchaseOrderCategory.is_active.is_(True))
            .order_by(PurchaseOrderCategory.name, PurchaseOrderCategory.id)
        )
        .scalars()
        .all()
    )


def get_category(db: Session, category_id: str) -> PurchaseOrderCategory | None:
    c = db.get(PurchaseOrderCategory, category_id)
    if c is None or not c.is_active:
        return None
    return c


def update_category(
    db: Session,
    cat: PurchaseOrderCategory,
    payload: PurchaseOrderCategoryUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> PurchaseOrderCategory:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: PurchaseOrderCategory) -> None:
    cat.is_active = False
    cat.deleted_at = utcnow()
    db.commit()
