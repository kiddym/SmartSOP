"""按资产维护成本归属（parts + labor + additional）。

公共纯函数，供 cost_analytics 与 asset_reliability_analytics 复用。
金额一律 Decimal；labor/additional 按 created_at 落窗，parts 按 consumed_at 落窗。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_labor import WorkOrderLabor
from app.services import work_order_labor_service as labor


def cost_by_asset(
    db: Session,
    start: datetime,
    end_excl: datetime,
    *,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> dict[str | None, dict[str, Decimal]]:
    """返回 {asset_id|None: {"parts","labor","additional"}}（未量化原值）。

    asset_id/location_id 过滤经 WorkOrder 关联生效。
    口径：账本（消耗/工时/附加成本）按实际发生额归属，不因宿主工单后续软删而剔除——
    与既有 /costs 口径一致；实体计数类面板才按宿主 is_active 过滤。
    """
    out: dict[str | None, dict[str, Decimal]] = defaultdict(
        lambda: {"parts": Decimal("0"), "labor": Decimal("0"), "additional": Decimal("0")}
    )

    def _wo_filter(stmt: Select) -> Select:  # type: ignore[type-arg]
        if asset_id is not None:
            stmt = stmt.where(WorkOrder.asset_id == asset_id)
        if location_id is not None:
            stmt = stmt.where(WorkOrder.location_id == location_id)
        return stmt

    parts_stmt = _wo_filter(
        select(PartConsumption.quantity, PartConsumption.unit_cost, WorkOrder.asset_id)
        .join(WorkOrder, PartConsumption.work_order_id == WorkOrder.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    for qty, unit_cost, a_id in db.execute(parts_stmt).all():
        out[a_id]["parts"] += qty * unit_cost

    labor_stmt = _wo_filter(
        select(WorkOrderLabor, WorkOrder.asset_id)
        .join(WorkOrder, WorkOrderLabor.work_order_id == WorkOrder.id)
        .where(WorkOrderLabor.created_at >= start, WorkOrderLabor.created_at < end_excl)
    )
    for row, a_id in db.execute(labor_stmt).all():
        out[a_id]["labor"] += labor.compute_cost(row)

    add_stmt = _wo_filter(
        select(WorkOrderAdditionalCost.amount, WorkOrder.asset_id)
        .join(WorkOrder, WorkOrderAdditionalCost.work_order_id == WorkOrder.id)
        .where(
            WorkOrderAdditionalCost.created_at >= start,
            WorkOrderAdditionalCost.created_at < end_excl,
        )
    )
    for amount, a_id in db.execute(add_stmt).all():
        out[a_id]["additional"] += amount

    return dict(out)
