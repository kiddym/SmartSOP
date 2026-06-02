"""请求分析（只读）：总览/优先级/周期/收到vs解决/转化。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.request import Request
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority
from app.services.analytics._common import hours_between, resolve_window


def request_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    stmt = select(Request).where(
        Request.is_active.is_(True),
        Request.created_at >= start,
        Request.created_at < end_excl,
    )
    if asset_id is not None:
        stmt = stmt.where(Request.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(Request.location_id == location_id)
    reqs = list(db.execute(stmt).scalars().all())

    by_status = {s.value: 0 for s in RequestStatus}
    by_priority = {p.value: 0 for p in WorkOrderPriority}
    converted = 0
    for r in reqs:
        by_status[r.status.value] += 1
        by_priority[r.priority.value] += 1
        if r.work_order_id is not None:
            converted += 1

    resolved_stmt = select(Request).where(
        Request.is_active.is_(True),
        Request.resolved_at.is_not(None),
        Request.resolved_at >= start,
        Request.resolved_at < end_excl,
    )
    resolved_rows = list(db.execute(resolved_stmt).scalars().all())
    cycles = [
        hours_between(r.created_at, r.resolved_at)
        for r in resolved_rows
        if r.resolved_at is not None
    ]
    avg_cycle = round(sum(cycles) / len(cycles), 2) if cycles else None

    return {
        "date_from": df,
        "date_to": dt,
        "total": len(reqs),
        "by_status": by_status,
        "by_priority": by_priority,
        # received 与 total 同值（均为窗内创建数），为"收到 vs 解决"对照语义而单列，刻意相等。
        "received": len(reqs),
        "resolved": len(resolved_rows),
        "converted": converted,
        "avg_resolution_cycle_hours": avg_cycle,
    }
