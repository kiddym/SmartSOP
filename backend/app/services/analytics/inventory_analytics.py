"""库存聚合（只读）：库存价值（当前快照）+ 低库存 + 窗内 top 消耗。金额 Python Decimal。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.models.work_order_category import WorkOrderCategory
from app.services.analytics._common import resolve_window

# ABC/Pareto 累计占比阈值：累计 ≤ A 占比 → A 类（高价值少数），≤ B 占比 → B 类，其余 C 类。
_ABC_A_THRESHOLD = 80.0
_ABC_B_THRESHOLD = 95.0


def inventory_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
    p_stmt = select(Part).where(Part.is_active.is_(True), Part.non_stock.is_(False))
    if category_id is not None:
        p_stmt = p_stmt.where(Part.category_id == category_id)
    parts = list(db.execute(p_stmt.order_by(Part.custom_id)).scalars().all())

    # 分类名映射
    cat_names: dict[str, str] = {
        row[0]: row[1] for row in db.execute(select(PartCategory.id, PartCategory.name)).all()
    }

    total_value = Decimal("0")
    by_cat_value: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    low_items = []
    for p in parts:
        value = p.quantity * p.cost
        total_value += value
        by_cat_value[p.category_id] += value
        if p.quantity < p.min_quantity:
            low_items.append(
                {
                    "part_id": p.id,
                    "custom_id": p.custom_id,
                    "name": p.name,
                    "quantity": p.quantity,
                    "min_quantity": p.min_quantity,
                    "shortfall": p.min_quantity - p.quantity,
                }
            )

    inventory_value_by_category = sorted(
        (
            {"category_id": k, "name": cat_names.get(k) if k is not None else None, "value": v}
            for k, v in by_cat_value.items()
        ),
        key=lambda r: cast(Decimal, r["value"]),
        reverse=True,
    )

    # 窗内消耗：一次查询同时喂"按量"（top_consumed）与"按价值"（ABC）两累加器，
    # 避免对消耗台账二次全表扫描。仅比原 top 查询多取 unit_cost 一列。
    start, end_excl, _df, _dt = resolve_window(date_from, date_to)
    c_stmt = (
        select(
            PartConsumption.part_id,
            Part.custom_id,
            Part.name,
            PartConsumption.quantity,
            PartConsumption.unit_cost,
        )
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if category_id is not None:
        c_stmt = c_stmt.where(Part.category_id == category_id)
    consumed: dict[str, dict[str, Any]] = {}
    value_acc: dict[str, dict[str, Any]] = {}
    for part_id, custom_id, name, qty, unit_cost in db.execute(c_stmt).all():
        slot = consumed.setdefault(
            part_id, {"part_id": part_id, "custom_id": custom_id, "name": name, "qty": Decimal("0")}
        )
        slot["qty"] += qty
        vslot = value_acc.setdefault(
            part_id,
            {"part_id": part_id, "custom_id": custom_id, "name": name, "value": Decimal("0")},
        )
        vslot["value"] += qty * unit_cost
    top_consumed = sorted(consumed.values(), key=lambda r: cast(Decimal, r["qty"]), reverse=True)

    # ABC / Pareto 分级：按消耗价值降序累计，累计占比 ≤80%→A、≤95%→B、>95%→C。
    # 价值并列时以 custom_id 升序兜底，保证输出与类别归属确定（不随 DB 行序漂移）。
    ranked = sorted(
        value_acc.values(),
        key=lambda r: (-cast(Decimal, r["value"]), cast(str, r["custom_id"])),
    )
    total_consumption_value = sum((cast(Decimal, r["value"]) for r in ranked), Decimal("0"))
    abc_classification: list[dict[str, Any]] = []
    abc_summary = {"A": 0, "B": 0, "C": 0}
    running = Decimal("0")
    for r in ranked:
        running += cast(Decimal, r["value"])
        cum_pct = (
            float(running / total_consumption_value * 100) if total_consumption_value > 0 else 0.0
        )
        cls = "A" if cum_pct <= _ABC_A_THRESHOLD else "B" if cum_pct <= _ABC_B_THRESHOLD else "C"
        abc_summary[cls] += 1
        abc_classification.append(
            {
                "part_id": r["part_id"],
                "custom_id": r["custom_id"],
                "name": r["name"],
                "consumption_value": cast(Decimal, r["value"]).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "cumulative_pct": round(cum_pct, 2),
                "abc_class": cls,
            }
        )

    # 切面：按"所属工单分类"聚合窗内消耗（成本/数量）。经
    # PartConsumption→WorkOrder.category_id→WorkOrderCategory.name 左连，未挂分类的工单归
    # 「未分类」桶（category_id=None）。软删工单一并计入（消耗台账 append-only，成本须可追溯）。
    wo_cat_stmt = (
        select(
            WorkOrder.category_id,
            WorkOrderCategory.name,
            PartConsumption.quantity,
            PartConsumption.unit_cost,
        )
        .join(WorkOrder, PartConsumption.work_order_id == WorkOrder.id)
        .join(WorkOrderCategory, WorkOrder.category_id == WorkOrderCategory.id, isouter=True)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if category_id is not None:
        wo_cat_stmt = wo_cat_stmt.join(Part, PartConsumption.part_id == Part.id).where(
            Part.category_id == category_id
        )
    wo_cat_acc: dict[str | None, dict[str, Any]] = {}
    for cat_id, cat_name, qty, unit_cost in db.execute(wo_cat_stmt).all():
        slot = wo_cat_acc.setdefault(
            cat_id,
            {
                "category_id": cat_id,
                "name": cat_name,
                "cost": Decimal("0"),
                "qty": Decimal("0"),
            },
        )
        slot["cost"] += qty * unit_cost
        slot["qty"] += qty
    consumption_by_wo_category = sorted(
        (
            {
                "category_id": r["category_id"],
                "name": r["name"],
                "cost": cast(Decimal, r["cost"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "qty": cast(Decimal, r["qty"]),
            }
            for r in wo_cat_acc.values()
        ),
        # 成本降序；并列以分类名（未分类排末）兜底，保证稳定序。
        key=lambda r: (-cast(Decimal, r["cost"]), cast(str, r["name"] or "￿")),
    )

    # 切面：按月（consumed_at 月份）分桶的消耗成本时间序列。月键用方言无关的 Python 端聚合
    # （避免 SQL date_trunc/strftime 跨方言差异）。桶按月份升序，缺月不补零（前端连点即可）。
    m_stmt = select(
        PartConsumption.consumed_at,
        PartConsumption.quantity,
        PartConsumption.unit_cost,
    ).where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    if category_id is not None:
        m_stmt = m_stmt.join(Part, PartConsumption.part_id == Part.id).where(
            Part.category_id == category_id
        )
    month_acc: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for consumed_at, qty, unit_cost in db.execute(m_stmt).all():
        month_key = f"{consumed_at.year:04d}-{consumed_at.month:02d}"
        month_acc[month_key] += qty * unit_cost
    consumption_monthly_trend = [
        {
            "month": k,
            "cost": v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }
        for k, v in sorted(month_acc.items())
    ]

    return {
        "total_inventory_value": total_value,
        "inventory_value_by_category": inventory_value_by_category,
        "low_stock_count": len(low_items),
        "low_stock_items": low_items,
        "top_consumed_parts": top_consumed,
        "abc_classification": abc_classification,
        "abc_summary": abc_summary,
        "consumption_by_wo_category": consumption_by_wo_category,
        "consumption_monthly_trend": consumption_monthly_trend,
    }
