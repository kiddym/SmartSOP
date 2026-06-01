"""分析 API（/api/v1/analytics）。只读聚合，全部需 analytics.view。"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.user import User
from app.schemas.analytics import (
    AssetReliabilityAnalytics,
    CostAnalytics,
    InventoryAnalytics,
    WorkOrderAnalytics,
)
from app.services.analytics import (
    asset_reliability_analytics,
    cost_analytics,
    inventory_analytics,
    work_order_analytics,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_VIEW = Depends(require_permission(permissions.ANALYTICS_VIEW))


@router.get("/work-orders", response_model=WorkOrderAnalytics)
def work_order_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
):
    return work_order_analytics.work_order_dashboard(
        db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
    )


@router.get("/costs", response_model=CostAnalytics)
def cost_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
):
    return cost_analytics.cost_dashboard(
        db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
    )


@router.get("/asset-reliability", response_model=AssetReliabilityAnalytics)
def asset_reliability_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
):
    return asset_reliability_analytics.asset_reliability_dashboard(
        db,
        date_from=date_from,
        date_to=date_to,
        asset_id=asset_id,
        location_id=location_id,
        category_id=category_id,
    )


@router.get("/inventory", response_model=InventoryAnalytics)
def inventory_dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
):
    return inventory_analytics.inventory_dashboard(
        db, date_from=date_from, date_to=date_to, category_id=category_id
    )


def _stream_csv(header: list[str], rows: list[list]) -> StreamingResponse:
    def gen():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics.csv"},
    )


def _work_orders_csv(data: dict) -> tuple[list[str], list[list]]:
    total = data["total"]
    rows = [
        [status_name, count, round(count / total, 4) if total else 0.0]
        for status_name, count in data["by_status"].items()
    ]
    return ["status", "count", "pct"], rows


def _costs_csv(data: dict) -> tuple[list[str], list[list]]:
    rows = [
        [r["part_id"], r["custom_id"], r["name"], r["qty"], r["cost"]]
        for r in data["consumption_by_part"]
    ]
    return ["part_id", "custom_id", "name", "qty", "cost"], rows


def _asset_reliability_csv(data: dict) -> tuple[list[str], list[list]]:
    rows = [
        [
            r["asset_id"],
            r["custom_id"],
            r["name"],
            r["availability_pct"],
            r["downtime_count"],
            r["total_downtime_hours"],
            r["mttr_hours"],
            r["mtbf_hours"],
        ]
        for r in data["assets"]
    ]
    return (
        [
            "asset_id",
            "custom_id",
            "name",
            "availability_pct",
            "downtime_count",
            "total_downtime_hours",
            "mttr_hours",
            "mtbf_hours",
        ],
        rows,
    )


def _inventory_csv(db: Session, data: dict) -> tuple[list[str], list[list]]:
    cat_names = dict(db.execute(select(PartCategory.id, PartCategory.name)).all())
    low_ids = {r["part_id"] for r in data["low_stock_items"]}
    parts = list(
        db.execute(
            select(Part)
            .where(Part.is_active.is_(True), Part.non_stock.is_(False))
            .order_by(Part.custom_id)
        )
        .scalars()
        .all()
    )
    rows = [
        [
            p.custom_id,
            p.name,
            cat_names.get(p.category_id),
            p.quantity,
            p.min_quantity,
            p.cost,
            p.quantity * p.cost,
            p.id in low_ids,
        ]
        for p in parts
    ]
    return (
        [
            "custom_id",
            "name",
            "category",
            "quantity",
            "min_quantity",
            "cost",
            "value",
            "is_low_stock",
        ],
        rows,
    )


@router.get("/{dashboard}/export")
def export_dashboard_csv(
    dashboard: str,
    date_from: date | None = None,
    date_to: date | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = _VIEW,
):
    if dashboard == "work-orders":
        data = work_order_analytics.work_order_dashboard(
            db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
        )
        header, rows = _work_orders_csv(data)
    elif dashboard == "costs":
        data = cost_analytics.cost_dashboard(
            db, date_from=date_from, date_to=date_to, asset_id=asset_id, location_id=location_id
        )
        header, rows = _costs_csv(data)
    elif dashboard == "asset-reliability":
        data = asset_reliability_analytics.asset_reliability_dashboard(
            db,
            date_from=date_from,
            date_to=date_to,
            asset_id=asset_id,
            location_id=location_id,
            category_id=category_id,
        )
        header, rows = _asset_reliability_csv(data)
    elif dashboard == "inventory":
        data = inventory_analytics.inventory_dashboard(
            db, date_from=date_from, date_to=date_to, category_id=category_id
        )
        header, rows = _inventory_csv(db, data)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ANALYTICS_DASHBOARD_NOT_FOUND", "message": "未知分析面板"},
        )
    return _stream_csv(header, rows)
