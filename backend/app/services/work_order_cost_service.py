"""工单总成本实时聚合：labor + additional + parts(现有 PartConsumption)。

不落字段；三个小计各自 2dp 量化，total = 已量化小计之和（保证明细之和==总计）。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor
from app.services import work_order_labor_service as labor

_CENT = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_UP)


def cost_summary(db: Session, work_order_id: str) -> dict[str, Decimal]:
    labor_rows = (
        db.execute(select(WorkOrderLabor).where(WorkOrderLabor.work_order_id == work_order_id))
        .scalars()
        .all()
    )
    add_rows = (
        db.execute(
            select(WorkOrderAdditionalCost).where(
                WorkOrderAdditionalCost.work_order_id == work_order_id
            )
        )
        .scalars()
        .all()
    )
    part_rows = (
        db.execute(select(PartConsumption).where(PartConsumption.work_order_id == work_order_id))
        .scalars()
        .all()
    )

    # 仅累计 include_to_total=True 的 labor / additional 行；parts 不受此开关影响。
    labor_total = sum(
        (labor.compute_cost(r) for r in labor_rows if r.include_to_total), Decimal("0")
    )
    additional_total = sum((r.amount for r in add_rows if r.include_to_total), Decimal("0"))
    parts_total = sum((r.quantity * r.unit_cost for r in part_rows), Decimal("0"))

    lt, at, pt = _q(labor_total), _q(additional_total), _q(parts_total)
    return {
        "labor_total": lt,
        "additional_total": at,
        "parts_total": pt,
        "total": lt + at + pt,
    }
