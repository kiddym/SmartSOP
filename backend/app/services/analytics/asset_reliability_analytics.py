"""资产可靠性聚合（只读）：可用率/MTTR/MTBF。停机区间裁剪 + 时长在 Python 计算。

语义：基于窗内全部停机区间，未区分故障/计划（现停机无故障分类）。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.services.analytics._common import clip_interval, hours_between, resolve_window


def asset_reliability_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    category_id: str | None = None,
) -> dict:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    window_hours = round(hours_between(start, end_excl), 2)

    a_stmt = select(Asset).where(Asset.is_active.is_(True))
    if asset_id is not None:
        a_stmt = a_stmt.where(Asset.id == asset_id)
    if location_id is not None:
        a_stmt = a_stmt.where(Asset.location_id == location_id)
    if category_id is not None:
        a_stmt = a_stmt.where(Asset.category_id == category_id)
    assets = list(db.execute(a_stmt.order_by(Asset.custom_id)).scalars().all())

    asset_rows = []
    for a in assets:
        downs = db.execute(
            select(AssetDowntime).where(
                AssetDowntime.asset_id == a.id,
                AssetDowntime.started_at < end_excl,
                or_(AssetDowntime.ended_at.is_(None), AssetDowntime.ended_at > start),
            )
        ).scalars().all()
        clipped = [
            clip_interval(d.started_at, d.ended_at, start, end_excl) for d in downs
        ]
        clipped = [c for c in clipped if c is not None]
        total_down = sum((hours_between(lo, hi) for lo, hi in clipped), 0.0)
        count = len(clipped)
        availability = round((window_hours - total_down) / window_hours * 100, 2) \
            if window_hours > 0 else 0.0
        availability = max(0.0, min(100.0, availability))
        # MTTR 仅计已结束区间
        ended_durations = [
            hours_between(*clip_interval(d.started_at, d.ended_at, start, end_excl))
            for d in downs
            if d.ended_at is not None
            and clip_interval(d.started_at, d.ended_at, start, end_excl) is not None
        ]
        mttr = round(sum(ended_durations) / len(ended_durations), 2) if ended_durations else None
        mtbf = round((window_hours - total_down) / count, 2) if count else None
        asset_rows.append({
            "asset_id": a.id, "custom_id": a.custom_id, "name": a.name,
            "availability_pct": availability, "downtime_count": count,
            "total_downtime_hours": round(total_down, 2),
            "mttr_hours": mttr, "mtbf_hours": mtbf,
        })

    fleet_total_down = round(sum(r["total_downtime_hours"] for r in asset_rows), 2)
    fleet_availability = round(
        sum(r["availability_pct"] for r in asset_rows) / len(asset_rows), 2
    ) if asset_rows else None
    mttrs = [r["mttr_hours"] for r in asset_rows if r["mttr_hours"] is not None]
    fleet_mttr = round(sum(mttrs) / len(mttrs), 2) if mttrs else None
    mtbfs = [r["mtbf_hours"] for r in asset_rows if r["mtbf_hours"] is not None]
    fleet_mtbf = round(sum(mtbfs) / len(mtbfs), 2) if mtbfs else None

    return {
        "date_from": df, "date_to": dt, "window_hours": window_hours,
        "assets": asset_rows,
        "fleet_availability_pct": fleet_availability,
        "fleet_total_downtime_hours": fleet_total_down,
        "fleet_mttr_hours": fleet_mttr, "fleet_mtbf_hours": fleet_mtbf,
    }
