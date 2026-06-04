"""人员分析（只读）：创建/完成/被指派 数 + 工时 + 工时成本。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_labor import WorkOrderLabor
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_labor_service as labor
from app.services.analytics._common import resolve_window

_CENT = Decimal("0.01")


def personnel_dashboard(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    start, end_excl, df, dt = resolve_window(date_from, date_to)

    created: dict[str, int] = defaultdict(int)
    completed: dict[str, int] = defaultdict(int)
    assigned: dict[str, int] = defaultdict(int)
    hours: dict[str, float] = defaultdict(float)
    cost: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for uid in db.execute(
        select(WorkOrder.created_by_user_id).where(
            WorkOrder.is_active.is_(True),
            WorkOrder.created_by_user_id.is_not(None),
            WorkOrder.created_at >= start,
            WorkOrder.created_at < end_excl,
        )
    ).scalars():
        if uid is None:
            continue
        created[uid] += 1

    for uid in db.execute(
        select(WorkOrderActivity.actor_user_id).where(
            WorkOrderActivity.actor_user_id.is_not(None),
            WorkOrderActivity.to_status == WorkOrderStatus.COMPLETE.value,
            WorkOrderActivity.created_at >= start,
            WorkOrderActivity.created_at < end_excl,
        )
    ).scalars():
        if uid is None:
            continue
        completed[uid] += 1

    for uid in db.execute(
        select(WorkOrderAssignee.user_id)
        .join(WorkOrder, WorkOrderAssignee.work_order_id == WorkOrder.id)
        .where(
            WorkOrder.is_active.is_(True),
            WorkOrder.created_at >= start,
            WorkOrder.created_at < end_excl,
        )
    ).scalars():
        assigned[uid] += 1

    for row in db.execute(
        select(WorkOrderLabor).where(
            WorkOrderLabor.user_id.is_not(None),
            WorkOrderLabor.created_at >= start,
            WorkOrderLabor.created_at < end_excl,
        )
    ).scalars():
        uid = row.user_id
        if uid is None:
            continue
        hours[uid] += row.duration_seconds / 3600.0
        cost[uid] += labor.compute_cost(row)

    uids = set(created) | set(completed) | set(assigned) | set(hours) | set(cost)
    names = (
        {u.id: u.name for u in db.execute(select(User).where(User.id.in_(uids))).scalars()}
        if uids
        else {}
    )

    users = [
        {
            "user_id": uid,
            "name": names.get(uid),
            "created_count": created.get(uid, 0),
            "completed_count": completed.get(uid, 0),
            "assigned_count": assigned.get(uid, 0),
            "labor_hours": round(hours.get(uid, 0.0), 2),
            "labor_cost": cost.get(uid, Decimal("0")).quantize(_CENT, rounding=ROUND_HALF_UP),
        }
        for uid in sorted(uids)
    ]
    return {"date_from": df, "date_to": dt, "users": users}
