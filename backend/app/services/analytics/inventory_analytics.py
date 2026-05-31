"""库存聚合（只读）：库存价值（当前快照）+ 低库存 + 窗内 top 消耗。金额 Python Decimal。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.services.analytics._common import resolve_window


def inventory_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    category_id: str | None = None,
) -> dict:
    p_stmt = select(Part).where(Part.is_active.is_(True), Part.non_stock.is_(False))
    if category_id is not None:
        p_stmt = p_stmt.where(Part.category_id == category_id)
    parts = list(db.execute(p_stmt.order_by(Part.custom_id)).scalars().all())

    # 分类名映射
    cat_names = dict(db.execute(select(PartCategory.id, PartCategory.name)).all())

    total_value = Decimal("0")
    by_cat_value: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    low_items = []
    for p in parts:
        value = p.quantity * p.cost
        total_value += value
        by_cat_value[p.category_id] += value
        if p.quantity < p.min_quantity:
            low_items.append({
                "part_id": p.id, "custom_id": p.custom_id, "name": p.name,
                "quantity": p.quantity, "min_quantity": p.min_quantity,
                "shortfall": p.min_quantity - p.quantity,
            })

    inventory_value_by_category = sorted(
        ({"category_id": k, "name": cat_names.get(k), "value": v}
         for k, v in by_cat_value.items()),
        key=lambda r: r["value"], reverse=True)

    # 窗内 top 消耗（按量降序）
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    c_stmt = (
        select(PartConsumption.part_id, Part.custom_id, Part.name, PartConsumption.quantity)
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if category_id is not None:
        c_stmt = c_stmt.where(Part.category_id == category_id)
    consumed: dict[str, dict] = {}
    for part_id, custom_id, name, qty in db.execute(c_stmt).all():
        slot = consumed.setdefault(
            part_id, {"part_id": part_id, "custom_id": custom_id, "name": name,
                      "qty": Decimal("0")})
        slot["qty"] += qty
    top_consumed = sorted(consumed.values(), key=lambda r: r["qty"], reverse=True)

    return {
        "total_inventory_value": total_value,
        "inventory_value_by_category": inventory_value_by_category,
        "low_stock_count": len(low_items),
        "low_stock_items": low_items,
        "top_consumed_parts": top_consumed,
    }
