"""PM 工单自动生成任务（Phase 2B）。

每日扫描到期 PM（next_due_date<=today 且启用），逐 PM 设租户上下文生成工单并
锥摆推进 next_due_date。跨租户扫描用 bypass_tenant_scope；逐项提交隔离。
CLI：python -m app.tasks.pm_generate --once
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.models.preventive_maintenance import PreventiveMaintenance
from app.services import pm_service
from app.tenant import (
    bypass_tenant_scope,
    reset_current_company_id,
    set_current_company_id,
)

logger = logging.getLogger(__name__)
TASK_NAME = "pm_generate"
# 提醒广扫窗口（天）：先用宽窗取候选，再按各公司 days_before_pm_notification 精筛。
_MAX_REMIND_HORIZON = 90


def _remind_upcoming(db: Session, *, today: date) -> int:
    """对"即将到期但尚未生成"的 PM 给指派人发一次到期前提醒（边沿去重）。

    复用站内通知 + arm/disarm 机制；每个(PM, next_due_date)仅发一次，next_due
    推进后键变化自然重发。返回本次发送条数。轻量实现：与生单同 tick 内完成。"""
    from sqlalchemy import select

    from app.models.preventive_maintenance import PMAssignee, PMTeam
    from app.services import company_settings_service as css
    from app.services import notification_service as notif
    from app.services import pm_service

    with bypass_tenant_scope():
        cand_ids = pm_service.upcoming_candidates(db, today=today, horizon=_MAX_REMIND_HORIZON)
    fired = 0
    for pm_id in cand_ids:
        pm = db.get(PreventiveMaintenance, pm_id)
        if pm is None:
            continue
        token = set_current_company_id(pm.company_id)
        try:
            horizon = css.get_or_create(db, pm.company_id).days_before_pm_notification
            if horizon <= 0 or (pm.next_due_date - today).days > horizon:
                continue
            key = f"PM_DUE_SOON:{pm.id}:{pm.next_due_date.isoformat()}"
            if notif.is_armed(db, pm.company_id, key):
                continue
            recips: set[str] = set()
            if pm.primary_user_id:
                recips.add(pm.primary_user_id)
            recips |= {
                r
                for (r,) in db.execute(
                    select(PMAssignee.user_id).where(PMAssignee.pm_id == pm.id)
                ).all()
            }
            team_ids = {
                r for (r,) in db.execute(select(PMTeam.team_id).where(PMTeam.pm_id == pm.id)).all()
            }
            recips |= notif.resolve_team_members(db, pm.company_id, team_ids)
            recips = notif.active_recipient_subset(db, pm.company_id, recips, None)
            if not recips:
                continue
            notif.notify(
                db,
                company_id=pm.company_id,
                recipient_ids=recips,
                type="PM_DUE_SOON",
                entity_type="preventive_maintenance",
                entity_id=pm.id,
                params={
                    "custom_id": pm.custom_id,
                    "title": pm.title,
                    "next_due_date": pm.next_due_date.isoformat(),
                },
                actor_user_id=None,
                dedup_key=key,
            )
            notif.arm(db, pm.company_id, key)
            db.commit()
            fired += 1
        finally:
            reset_current_company_id(token)
    return fired


def run(db: Session, *, now: datetime | None = None, commit: bool = True) -> dict[str, int]:
    """执行一次扫描生成（逐项提交）。返回 {scanned, generated, errors}。"""
    started = now or utcnow()
    today = started.date()
    with bypass_tenant_scope():
        due_ids = pm_service.due_candidates(db, today=today)
    generated = 0
    errors = 0
    for pm_id in due_ids:
        try:
            pm = db.get(PreventiveMaintenance, pm_id)
            if pm is None:
                continue
            token = set_current_company_id(pm.company_id)
            try:
                wo = pm_service.generate_once(
                    db, pm, actor_user_id=None, now=started, enforce_due=True
                )
                if wo is not None:  # None=ends_on 终止或失效自停，未生单
                    generated += 1
            finally:
                reset_current_company_id(token)
        except Exception:  # 单项失败回滚自身、记日志、继续
            if commit:
                db.rollback()
            errors += 1
            logger.exception("pm_generate 失败 pm_id=%s", pm_id)

    try:
        reminded = _remind_upcoming(db, today=today)
    except Exception:  # 提醒为轻量附加项，失败不影响生单结果
        if commit:
            db.rollback()
        reminded = 0
        logger.exception("pm_generate 到期提醒失败")

    summary = {
        "scanned": len(due_ids),
        "generated": generated,
        "errors": errors,
        "reminded": reminded,
    }
    logger.info(
        json.dumps(
            {"task": TASK_NAME, "started_at": started.isoformat(), **summary}, ensure_ascii=False
        )
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PM 工单自动生成（一次性）")
    parser.add_argument("--once", action="store_true", help="执行一次后退出（默认行为）")
    parser.parse_args(argv)
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
