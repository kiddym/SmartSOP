"""到期提醒 + 低库存调度任务（Phase 5A）。

跨租户扫描（bypass_tenant_scope）计算"应武装"条件集，与现有 arm 行做集合差：
新增条件 -> 解析接收人 + notify + arm；消失条件 -> disarm。边沿语义，零刷屏。
CLI：python -m app.tasks.due_reminder
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.models.notification import NotificationArm
from app.models.part import Part
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.services import notification_service as notif
from app.tenant import (
    bypass_tenant_scope,
    reset_current_company_id,
    set_current_company_id,
)

logger = logging.getLogger(__name__)
TASK_NAME = "due_reminder"

_TERMINAL = (WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED)


def _compute_should(
    db: Session, today: date, soon_cutoff: date
) -> dict[tuple[str, str], dict[str, Any]]:
    """跨租户计算应武装条件集：{(company_id, key): info}。"""
    should: dict[tuple[str, str], dict[str, Any]] = {}
    wo_rows = db.execute(
        select(
            WorkOrder.id,
            WorkOrder.company_id,
            WorkOrder.custom_id,
            WorkOrder.title,
            WorkOrder.due_date,
            WorkOrder.status,
        ).where(
            WorkOrder.is_active.is_(True),
            WorkOrder.due_date.is_not(None),
            WorkOrder.status.not_in(_TERMINAL),
        )
    ).all()
    for wid, cid, cust, title, due, _status in wo_rows:
        if due < today:
            key = f"WO_OVERDUE:{wid}:{due.isoformat()}"
            kind = "WO_OVERDUE"
        elif due < soon_cutoff:
            key = f"WO_DUE_SOON:{wid}:{due.isoformat()}"
            kind = "WO_DUE_SOON"
        else:
            continue
        should[(cid, key)] = {
            "kind": kind,
            "key": key,
            "company_id": cid,
            "entity_id": wid,
            "entity_type": "work_order",
            "params": {"custom_id": cust, "title": title, "due_date": due.isoformat()},
        }
    part_rows = db.execute(
        select(
            Part.id, Part.company_id, Part.custom_id, Part.name, Part.quantity, Part.min_quantity
        ).where(
            Part.is_active.is_(True), Part.non_stock.is_(False), Part.quantity < Part.min_quantity
        )
    ).all()
    for pid, cid, cust, name, qty, minq in part_rows:
        key = f"PART_LOW_STOCK:{pid}"
        should[(cid, key)] = {
            "kind": "PART_LOW_STOCK",
            "key": key,
            "company_id": cid,
            "entity_id": pid,
            "entity_type": "part",
            "params": {
                "custom_id": cust,
                "name": name,
                "quantity": str(qty),
                "min_quantity": str(minq),
            },
        }
    return should


def _fire(db: Session, info: dict[str, Any]) -> None:
    cid = info["company_id"]
    kind = info["kind"]
    if kind in ("WO_DUE_SOON", "WO_OVERDUE"):
        wo = db.get(WorkOrder, info["entity_id"])
        recips = notif.resolve_wo_recipients(db, wo, exclude_actor_id=None) if wo else set()
    else:  # PART_LOW_STOCK
        recips = notif.resolve_permission_holders(db, cid, "part.edit", exclude_actor_id=None)
    notif.notify(
        db,
        company_id=cid,
        recipient_ids=recips,
        type=kind,
        entity_type=info["entity_type"],
        entity_id=info["entity_id"],
        params=info["params"],
        actor_user_id=None,
        dedup_key=info["key"],
    )
    notif.arm(db, cid, info["key"])


def run(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    started = now or utcnow()
    today = started.date()
    soon_cutoff = today + timedelta(days=settings.notify_due_soon_days)

    with bypass_tenant_scope():
        should = _compute_should(db, today, soon_cutoff)
        armed = {(a.company_id, a.key) for a in db.execute(select(NotificationArm)).scalars().all()}

    fired = 0
    for (cid, key), info in should.items():
        if (cid, key) in armed:
            continue
        token = set_current_company_id(cid)
        try:
            _fire(db, info)
            fired += 1
        finally:
            reset_current_company_id(token)

    disarmed = 0
    should_keys = set(should.keys())
    for cid, key in armed:
        if (cid, key) in should_keys:
            continue
        token = set_current_company_id(cid)
        try:
            notif.disarm(db, cid, key)
            disarmed += 1
        finally:
            reset_current_company_id(token)

    db.commit()
    summary = {"fired": fired, "disarmed": disarmed, "armed_before": len(armed)}
    logger.info(
        json.dumps(
            {"task": TASK_NAME, "started_at": started.isoformat(), **summary}, ensure_ascii=False
        )
    )
    return summary


def main() -> None:  # pragma: no cover
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
