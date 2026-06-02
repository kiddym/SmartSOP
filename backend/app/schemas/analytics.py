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


class InventoryAnalytics(BaseModel):
    total_inventory_value: Decimal
    inventory_value_by_category: list[CategoryValueRow]
    low_stock_count: int
    low_stock_items: list[LowStockRow]
    top_consumed_parts: list[TopConsumedRow]
    abc_classification: list[ABCRow]
    abc_summary: dict[str, int]
