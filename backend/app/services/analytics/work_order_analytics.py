"""工单合规吞吐聚合（只读）。时长在 Python 计算以跨方言安全。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.services.analytics._common import hours_between, resolve_window


def work_order_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    stmt = select(WorkOrder).where(
        WorkOrder.is_active.is_(True),
        WorkOrder.created_at >= start,
        WorkOrder.created_at < end_excl,
    )
    if asset_id is not None:
        stmt = stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(WorkOrder.location_id == location_id)
    wos = list(db.execute(stmt).scalars().all())

    total = len(wos)
    by_status = {s.value: 0 for s in WorkOrderStatus}
    by_priority = {p.value: 0 for p in WorkOrderPriority}
    for wo in wos:
        by_status[wo.status.value] += 1
        by_priority[wo.priority.value] += 1
    completed = by_status[WorkOrderStatus.COMPLETE.value]
    completion_rate = round(completed / total, 4) if total else 0.0

    cycles = [
        hours_between(wo.created_at, wo.completed_at)
        for wo in wos
        if wo.status == WorkOrderStatus.COMPLETE and wo.completed_at is not None
    ]
    avg_cycle = round(sum(cycles) / len(cycles), 2) if cycles else None

    overdue = sum(
        1
        for wo in wos
        if wo.due_date is not None
        and wo.due_date < dt
        and wo.status not in (WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED)
    )

    # 首条 ->IN_PROGRESS 活动时间（取列入 Python 求 min，避免 SQLite func.min 丢类型）
    first_ip: dict[str, datetime] = {}
    wo_ids = [wo.id for wo in wos]
    if wo_ids:
        act_rows = db.execute(
            select(WorkOrderActivity.work_order_id, WorkOrderActivity.created_at).where(
                WorkOrderActivity.work_order_id.in_(wo_ids),
                WorkOrderActivity.to_status == WorkOrderStatus.IN_PROGRESS.value,
            )
        ).all()
        for wid, ts in act_rows:
            if wid not in first_ip or ts < first_ip[wid]:
                first_ip[wid] = ts
    resp = [hours_between(wo.created_at, first_ip[wo.id]) for wo in wos if wo.id in first_ip]
    avg_response = round(sum(resp) / len(resp), 2) if resp else None

    return {
        "date_from": df,
        "date_to": dt,
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "completed": completed,
        "completion_rate": completion_rate,
        "overdue": overdue,
        "avg_cycle_time_hours": avg_cycle,
        "avg_response_time_hours": avg_response,
    }
