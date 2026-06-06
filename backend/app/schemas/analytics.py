"""分析仪表盘响应 schema（Phase 4，只读）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CountRow(BaseModel):
    asset_id: str | None = None
    user_id: str | None = None
    category_id: str | None = None
    count: int


class WorkOrderAnalytics(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    completed: int
    completion_rate: float
    overdue: int
    avg_cycle_time_hours: float | None
    avg_response_time_hours: float | None
    by_asset: list[CountRow]
    by_user: list[CountRow]
    by_category: list[CountRow]


class RequestAnalytics(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    received: int
    resolved: int
    converted: int
    avg_resolution_cycle_hours: float | None


class PartCostRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    qty: Decimal
    cost: Decimal


class AssetCostRow(BaseModel):
    asset_id: str | None
    cost: Decimal


class VendorSpendRow(BaseModel):
    vendor_id: str
    spend: Decimal


class MaintenanceCostByAssetRow(BaseModel):
    asset_id: str | None
    parts_cost: Decimal
    labor_cost: Decimal
    additional_cost: Decimal
    total: Decimal


class CostAnalytics(BaseModel):
    date_from: date
    date_to: date
    parts_consumption_cost: Decimal
    consumption_by_part: list[PartCostRow]
    consumption_by_asset: list[AssetCostRow]
    po_spend_approved: Decimal
    po_spend_by_vendor: list[VendorSpendRow]
    labor_cost: Decimal
    additional_cost: Decimal
    total_maintenance_cost: Decimal
    maintenance_cost_by_asset: list[MaintenanceCostByAssetRow]


class AssetReliabilityRow(BaseModel):
    asset_id: str
    custom_id: str
    name: str
    availability_pct: float
    downtime_count: int
    total_downtime_hours: float
    mttr_hours: float | None
    mtbf_hours: float | None
    total_maintenance_cost: Decimal
    acquisition_cost: Decimal | None
    cost_to_value_ratio: float | None


class AssetReliabilityAnalytics(BaseModel):
    date_from: date
    date_to: date
    window_hours: float
    assets: list[AssetReliabilityRow]
    fleet_availability_pct: float | None
    fleet_total_downtime_hours: float
    fleet_mttr_hours: float | None
    fleet_mtbf_hours: float | None
    fleet_total_maintenance_cost: Decimal


class CategoryValueRow(BaseModel):
    category_id: str | None
    name: str | None
    value: Decimal


class LowStockRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    quantity: Decimal
    min_quantity: Decimal
    shortfall: Decimal


class TopConsumedRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    qty: Decimal


class ABCRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    consumption_value: Decimal
    cumulative_pct: float
    abc_class: str


class PersonnelRow(BaseModel):
    user_id: str
    name: str | None
    created_count: int
    completed_count: int
    assigned_count: int
    labor_hours: float
    labor_cost: Decimal


class PersonnelAnalytics(BaseModel):
    date_from: date
    date_to: date
    users: list[PersonnelRow]


class TrendBucket(BaseModel):
    bucket_start: date
    work_orders_created: int
    work_orders_completed: int
    requests_received: int
    requests_resolved: int


class TrendAnalytics(BaseModel):
    date_from: date
    date_to: date
    granularity: str
    buckets: list[TrendBucket]


class WoCategoryConsumptionRow(BaseModel):
    category_id: str | None
    name: str | None
    cost: Decimal
    qty: Decimal


class MonthlyConsumptionRow(BaseModel):
    month: str
    cost: Decimal


class InventoryAnalytics(BaseModel):
    total_inventory_value: Decimal
    inventory_value_by_category: list[CategoryValueRow]
    low_stock_count: int
    low_stock_items: list[LowStockRow]
    top_consumed_parts: list[TopConsumedRow]
    abc_classification: list[ABCRow]
    abc_summary: dict[str, int]
    consumption_by_wo_category: list[WoCategoryConsumptionRow] = []
    consumption_monthly_trend: list[MonthlyConsumptionRow] = []
