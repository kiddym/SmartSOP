"""分析 API（/api/v1/analytics）。只读聚合，全部需 analytics.view。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
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
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return work_order_analytics.work_order_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id)


@router.get("/costs", response_model=CostAnalytics)
def cost_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return cost_analytics.cost_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id)


@router.get("/asset-reliability", response_model=AssetReliabilityAnalytics)
def asset_reliability_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return asset_reliability_analytics.asset_reliability_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id, category_id=category_id)


@router.get("/inventory", response_model=InventoryAnalytics)
def inventory_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return inventory_analytics.inventory_dashboard(
        db, date_from=date_from, date_to=date_to, category_id=category_id)
