"""工单额外成本服务：CRUD（硬删）。cost_category 复用现有 CostCategory。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.cost_category import CostCategory
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.schemas.work_order_cost import AdditionalCostCreate, AdditionalCostUpdate


def _validate_category(db: Session, company_id: str, cost_category_id: str | None) -> None:
    if cost_category_id is None:
        return
    cat = db.get(CostCategory, cost_category_id)
    if cat is None or cat.company_id != company_id or not cat.is_active:
        raise not_found("COST_CATEGORY_NOT_FOUND", "成本分类不存在")


def list_additional_costs(db: Session, work_order_id: str) -> list[WorkOrderAdditionalCost]:
    return list(
        db.execute(
            select(WorkOrderAdditionalCost)
            .where(WorkOrderAdditionalCost.work_order_id == work_order_id)
            .order_by(WorkOrderAdditionalCost.created_at, WorkOrderAdditionalCost.id)
        )
        .scalars()
        .all()
    )


def create_additional_cost(
    db: Session,
    wo: WorkOrder,
    payload: AdditionalCostCreate,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderAdditionalCost:
    _validate_category(db, company_id, payload.cost_category_id)
    row = WorkOrderAdditionalCost(
        work_order_id=wo.id,
        cost_category_id=payload.cost_category_id,
        title=payload.title,
        amount=payload.amount,
        description=payload.description,
        include_to_total=payload.include_to_total,
        created_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_additional_cost(
    db: Session,
    row: WorkOrderAdditionalCost,
    payload: AdditionalCostUpdate,
    company_id: str,
) -> WorkOrderAdditionalCost:
    data = payload.model_dump(exclude_unset=True)
    if "cost_category_id" in data:
        _validate_category(db, company_id, data["cost_category_id"])
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def delete_additional_cost(db: Session, row: WorkOrderAdditionalCost) -> None:
    db.delete(row)
    db.commit()
