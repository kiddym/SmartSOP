from datetime import date
from decimal import Decimal

from app.schemas.analytics import (
    AssetReliabilityAnalytics,
    CostAnalytics,
    InventoryAnalytics,
    WorkOrderAnalytics,
)


def test_work_order_analytics_shape():
    m = WorkOrderAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), total=2,
        by_status={"OPEN": 1, "COMPLETE": 1}, by_priority={"HIGH": 2},
        completed=1, completion_rate=0.5, overdue=0,
        avg_cycle_time_hours=12.0, avg_response_time_hours=None,
    )
    assert m.completion_rate == 0.5 and m.avg_response_time_hours is None


def test_cost_analytics_decimal():
    m = CostAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31),
        parts_consumption_cost=Decimal("6.0000"),
        consumption_by_part=[{"part_id": "p1", "custom_id": "PRT1", "name": "x",
                              "qty": Decimal("3"), "cost": Decimal("6")}],
        consumption_by_asset=[{"asset_id": None, "cost": Decimal("6")}],
        po_spend_approved=Decimal("0"), po_spend_by_vendor=[],
    )
    assert m.consumption_by_part[0].cost == Decimal("6")


def test_asset_reliability_nullable_mtbf():
    m = AssetReliabilityAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), window_hours=744.0,
        assets=[{"asset_id": "a1", "custom_id": "AST1", "name": "pump",
                 "availability_pct": 100.0, "downtime_count": 0,
                 "total_downtime_hours": 0.0, "mttr_hours": None, "mtbf_hours": None}],
        fleet_availability_pct=100.0, fleet_total_downtime_hours=0.0,
        fleet_mttr_hours=None, fleet_mtbf_hours=None,
    )
    assert m.assets[0].mtbf_hours is None


def test_inventory_analytics_shape():
    m = InventoryAnalytics(
        total_inventory_value=Decimal("100"), inventory_value_by_category=[],
        low_stock_count=1,
        low_stock_items=[{"part_id": "p1", "custom_id": "PRT1", "name": "x",
                          "quantity": Decimal("1"), "min_quantity": Decimal("5"),
                          "shortfall": Decimal("4")}],
        top_consumed_parts=[],
    )
    assert m.low_stock_items[0].shortfall == Decimal("4")
