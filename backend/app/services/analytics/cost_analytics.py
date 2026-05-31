"""成本聚合（只读）：备件消耗成本 + PO 承诺采购额。金额在 Python 用 Decimal 计算。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.purchase_order_status import PurchaseOrderStatus
from app.models.work_order import WorkOrder
from app.services.analytics._common import resolve_window


def cost_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
) -> dict:
    start, end_excl, df, dt = resolve_window(date_from, date_to)

    # 备件消耗：join WorkOrder 取 asset_id、join Part 取 custom_id/name
    c_stmt = (
        select(
            PartConsumption.part_id, Part.custom_id, Part.name,
            PartConsumption.quantity, PartConsumption.unit_cost, WorkOrder.asset_id,
        )
        .join(WorkOrder, PartConsumption.work_order_id == WorkOrder.id)
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if asset_id is not None:
        c_stmt = c_stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        c_stmt = c_stmt.where(WorkOrder.location_id == location_id)
    rows = db.execute(c_stmt).all()

    total_consumption = Decimal("0")
    by_part: dict[str, dict] = {}
    by_asset: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    for part_id, custom_id, name, qty, unit_cost, a_id in rows:
        line_cost = (qty * unit_cost)
        total_consumption += line_cost
        slot = by_part.setdefault(
            part_id, {"part_id": part_id, "custom_id": custom_id, "name": name,
                      "qty": Decimal("0"), "cost": Decimal("0")})
        slot["qty"] += qty
        slot["cost"] += line_cost
        by_asset[a_id] += line_cost

    consumption_by_part = sorted(by_part.values(), key=lambda r: r["cost"], reverse=True)
    consumption_by_asset = sorted(
        ({"asset_id": k, "cost": v} for k, v in by_asset.items()),
        key=lambda r: r["cost"], reverse=True)

    # PO 承诺采购额：仅 APPROVED 且 resolved_at 在窗
    p_stmt = (
        select(PurchaseOrder.vendor_id, PurchaseOrderLine.quantity, PurchaseOrderLine.unit_cost)
        .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.is_active.is_(True),
            PurchaseOrder.status == PurchaseOrderStatus.APPROVED,
            PurchaseOrder.resolved_at >= start,
            PurchaseOrder.resolved_at < end_excl,
        )
    )
    po_total = Decimal("0")
    by_vendor: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for vendor_id, qty, unit_cost in db.execute(p_stmt).all():
        line = qty * unit_cost
        po_total += line
        by_vendor[vendor_id] += line
    po_spend_by_vendor = sorted(
        ({"vendor_id": k, "spend": v} for k, v in by_vendor.items()),
        key=lambda r: r["spend"], reverse=True)

    return {
        "date_from": df, "date_to": dt,
        "parts_consumption_cost": total_consumption,
        "consumption_by_part": consumption_by_part,
        "consumption_by_asset": consumption_by_asset,
        "po_spend_approved": po_total,
        "po_spend_by_vendor": po_spend_by_vendor,
    }
