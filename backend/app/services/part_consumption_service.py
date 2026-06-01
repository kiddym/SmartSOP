"""备件消耗服务：挂工单消耗（扣库存、不足报错、单价快照台账）+ 台账查询。

请求内单次 commit；不调用内部 commit 的工单服务，无 partial-commit 风险。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder


def consume_part(
    db: Session,
    work_order: WorkOrder,
    part: Part,
    quantity: Decimal,
    company_id: str,
    actor_user_id: str | None,
) -> PartConsumption:
    """在工单上消耗备件：non_stock 不扣库存不报错；计库存则不足报错并扣减。"""
    if quantity <= 0:
        raise bad_request("PART_BAD_QUANTITY", "消耗数量必须大于 0")
    if not part.non_stock:
        if quantity > part.quantity:
            raise bad_request("PART_INSUFFICIENT_STOCK", "备件库存不足")
        part.quantity = part.quantity - quantity
    consumption = PartConsumption(
        part_id=part.id,
        work_order_id=work_order.id,
        quantity=quantity,
        unit_cost=part.cost,
        consumed_by_user_id=actor_user_id,
        company_id=company_id,
    )
    db.add(consumption)
    db.commit()
    db.refresh(consumption)
    return consumption


def list_consumptions(db: Session, work_order_id: str) -> list[PartConsumption]:
    return list(
        db.execute(
            select(PartConsumption)
            .where(PartConsumption.work_order_id == work_order_id)
            .order_by(PartConsumption.consumed_at, PartConsumption.id)
        )
        .scalars()
        .all()
    )
