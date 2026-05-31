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
from datetime import datetime

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
                pm_service.generate_once(db, pm, actor_user_id=None,
                                         now=started, enforce_due=True)
                generated += 1
            finally:
                reset_current_company_id(token)
        except Exception:  # 单项失败回滚自身、记日志、继续
            if commit:
                db.rollback()
            errors += 1
            logger.exception("pm_generate 失败 pm_id=%s", pm_id)

    summary = {"scanned": len(due_ids), "generated": generated, "errors": errors}
    logger.info(json.dumps(
        {"task": TASK_NAME, "started_at": started.isoformat(), **summary},
        ensure_ascii=False))
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
