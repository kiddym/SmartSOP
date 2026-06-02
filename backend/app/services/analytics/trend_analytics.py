"""趋势分析（只读）：按日/周分桶的吞吐时间序列。

桶为纯函数生成，覆盖整个窗口（含空桶）。完整状态历史重建超出范围。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.request import Request
from app.models.work_order import WorkOrder
from app.services.analytics._common import resolve_window

_GRANULARITIES = ("day", "week")


def _bucket_starts(df: date, dt: date, granularity: str) -> list[date]:
    """生成 [df, dt] 覆盖的桶起点列表。day=逐日；week=自 df 起每 7 天。"""
    step = timedelta(days=1 if granularity == "day" else 7)
    out: list[date] = []
    cur = df
    while cur <= dt:
        out.append(cur)
        cur = cur + step
    return out


def _bucket_index(starts: list[date], d: date) -> int | None:
    """d 落在哪个桶（最后一个 start <= d）。越界返回 None。"""
    idx: int | None = None
    for i, s in enumerate(starts):
        if s <= d:
            idx = i
        else:
            break
    return idx


def trend_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: str = "day",
) -> dict[str, Any]:
    if granularity not in _GRANULARITIES:
        raise bad_request("INVALID_GRANULARITY", "granularity 仅支持 day 或 week")
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    starts = _bucket_starts(df, dt, granularity)
    buckets: list[dict[str, Any]] = [
        {
            "bucket_start": s,
            "work_orders_created": 0,
            "work_orders_completed": 0,
            "requests_received": 0,
            "requests_resolved": 0,
        }
        for s in starts
    ]

    def _bump(ts: datetime | None, key: str) -> None:
        if ts is None:
            return
        i = _bucket_index(starts, ts.date())
        if i is not None:
            buckets[i][key] += 1

    for wo_c in db.execute(
        select(WorkOrder).where(
            WorkOrder.is_active.is_(True),
            WorkOrder.created_at >= start,
            WorkOrder.created_at < end_excl,
        )
    ).scalars():
        _bump(wo_c.created_at, "work_orders_created")
    for wo_d in db.execute(
        select(WorkOrder).where(
            WorkOrder.is_active.is_(True),
            WorkOrder.completed_at.is_not(None),
            WorkOrder.completed_at >= start,
            WorkOrder.completed_at < end_excl,
        )
    ).scalars():
        _bump(wo_d.completed_at, "work_orders_completed")
    for r_c in db.execute(
        select(Request).where(
            Request.is_active.is_(True),
            Request.created_at >= start,
            Request.created_at < end_excl,
        )
    ).scalars():
        _bump(r_c.created_at, "requests_received")
    for r_r in db.execute(
        select(Request).where(
            Request.is_active.is_(True),
            Request.resolved_at.is_not(None),
            Request.resolved_at >= start,
            Request.resolved_at < end_excl,
        )
    ).scalars():
        _bump(r_r.resolved_at, "requests_resolved")

    return {"date_from": df, "date_to": dt, "granularity": granularity, "buckets": buckets}
