"""资产可靠性聚合（只读）：可用率/MTTR/MTBF。停机区间裁剪 + 时长在 Python 计算。

语义：基于窗内全部停机区间，未区分故障/计划（现停机无故障分类）。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.services.analytics import _cost_attribution
from app.services.analytics._common import clip_interval, hours_between, resolve_window


def asset_reliability_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
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

    attrib = _cost_attribution.cost_by_asset(db, start, end_excl)
    cent = Decimal("0.01")

    def _asset_total(a_id: str) -> Decimal:
        v = attrib.get(a_id)
        if v is None:
            return Decimal("0.00")
        return (
            v["parts"].quantize(cent, rounding=ROUND_HALF_UP)
            + v["labor"].quantize(cent, rounding=ROUND_HALF_UP)
            + v["additional"].quantize(cent, rounding=ROUND_HALF_UP)
        )

    asset_rows: list[dict[str, Any]] = []
    for a in assets:
        downs = (
            db.execute(
                select(AssetDowntime).where(
                    AssetDowntime.asset_id == a.id,
                    AssetDowntime.started_at < end_excl,
                    or_(AssetDowntime.ended_at.is_(None), AssetDowntime.ended_at > start),
                )
            )
            .scalars()
            .all()
        )
        clipped_raw = [clip_interval(d.started_at, d.ended_at, start, end_excl) for d in downs]
        clipped: list[tuple[datetime, datetime]] = [c for c in clipped_raw if c is not None]
        total_down = sum((hours_between(lo, hi) for lo, hi in clipped), 0.0)
        count = len(clipped)
        availability = (
            round((window_hours - total_down) / window_hours * 100, 2) if window_hours > 0 else 0.0
        )
        availability = max(0.0, min(100.0, availability))
        # MTTR 仅计已结束区间
        ended_durations: list[float] = []
        for d in downs:
            if d.ended_at is not None:
                interval = clip_interval(d.started_at, d.ended_at, start, end_excl)
                if interval is not None:
                    ended_durations.append(hours_between(interval[0], interval[1]))
        mttr = round(sum(ended_durations) / len(ended_durations), 2) if ended_durations else None
        mtbf = round((window_hours - total_down) / count, 2) if count else None
        tmc = _asset_total(a.id)
        acq = cast("Decimal | None", a.acquisition_cost)
        asset_rows.append(
            {
                "asset_id": a.id,
                "custom_id": a.custom_id,
                "name": a.name,
                "availability_pct": availability,
                "downtime_count": count,
                "total_downtime_hours": round(total_down, 2),
                "mttr_hours": mttr,
                "mtbf_hours": mtbf,
                "total_maintenance_cost": tmc,
                "acquisition_cost": (
                    acq.quantize(cent, rounding=ROUND_HALF_UP) if acq is not None else None
                ),
                "cost_to_value_ratio": (
                    round(float(tmc / acq), 4) if acq is not None and acq > 0 else None
                ),
            }
        )

    fleet_total_down = round(sum(cast(float, r["total_downtime_hours"]) for r in asset_rows), 2)
    fleet_availability = (
        round(sum(cast(float, r["availability_pct"]) for r in asset_rows) / len(asset_rows), 2)
        if asset_rows
        else None
    )
    mttrs = [cast(float, r["mttr_hours"]) for r in asset_rows if r["mttr_hours"] is not None]
    fleet_mttr = round(sum(mttrs) / len(mttrs), 2) if mttrs else None
    mtbfs = [cast(float, r["mtbf_hours"]) for r in asset_rows if r["mtbf_hours"] is not None]
    fleet_mtbf = round(sum(mtbfs) / len(mtbfs), 2) if mtbfs else None

    fleet_total_maintenance_cost = sum(
        (cast(Decimal, r["total_maintenance_cost"]) for r in asset_rows), Decimal("0")
    )

    return {
        "date_from": df,
        "date_to": dt,
        "window_hours": window_hours,
        "assets": asset_rows,
        "fleet_availability_pct": fleet_availability,
        "fleet_total_downtime_hours": fleet_total_down,
        "fleet_mttr_hours": fleet_mttr,
        "fleet_mtbf_hours": fleet_mtbf,
        "fleet_total_maintenance_cost": fleet_total_maintenance_cost,
    }
