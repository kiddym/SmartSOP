"""独立 scheduler 进程（§53.1 / Q331）。

APScheduler BlockingScheduler，replicas=1（单实例天然单次执行，无需分布式锁、
无 broker）。临时上传清理每 1h；asset GC 每日 ``CLEANUP_HOUR``。
CLI：``python -m app.tasks.scheduler``。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.tasks import (
    asset_gc,
    cleanup_attachments,
    cleanup_uploads,
    due_reminder,
    email_dispatch,
    pm_generate,
)

logger = logging.getLogger(__name__)


def _run_cleanup_uploads() -> None:
    cleanup_uploads.run()


def _run_asset_gc() -> None:
    db = SessionLocal()
    try:
        asset_gc.run(db)
    finally:
        db.close()


def _run_cleanup_attachments() -> None:
    db = SessionLocal()
    try:
        cleanup_attachments.run(db)
    finally:
        db.close()


def _run_pm_generate() -> None:
    db = SessionLocal()
    try:
        pm_generate.run(db)
    finally:
        db.close()


def _run_due_reminder() -> None:
    db = SessionLocal()
    try:
        due_reminder.run(db)
    finally:
        db.close()


def _run_email_dispatch() -> None:
    db = SessionLocal()
    try:
        email_dispatch.run(db)
    finally:
        db.close()


def build_scheduler() -> BlockingScheduler:
    """装配 scheduler（不启动），便于测试。"""
    sched = BlockingScheduler(timezone=None)
    sched.add_job(
        _run_cleanup_uploads,
        IntervalTrigger(hours=1),
        id="cleanup_uploads",
        replace_existing=True,
    )
    sched.add_job(
        _run_asset_gc,
        CronTrigger(hour=settings.cleanup_hour, minute=0),
        id="asset_gc",
        replace_existing=True,
    )
    sched.add_job(
        _run_cleanup_attachments,
        CronTrigger(hour=settings.cleanup_hour, minute=30),
        id="cleanup_attachments",
        replace_existing=True,
    )
    sched.add_job(
        _run_pm_generate,
        CronTrigger(hour=settings.cleanup_hour, minute=45),
        id="pm_generate",
        replace_existing=True,
    )
    sched.add_job(
        _run_due_reminder,
        CronTrigger(hour=settings.cleanup_hour, minute=15),
        id="due_reminder",
        replace_existing=True,
    )
    sched.add_job(
        _run_email_dispatch,
        IntervalTrigger(minutes=5),
        id="email_dispatch",
        replace_existing=True,
    )
    return sched


def main() -> int:  # pragma: no cover — 长驻进程
    configure_logging()
    logger.info(
        "scheduler 启动：cleanup_uploads@1h, asset_gc@%02d:00, cleanup_attachments@%02d:30",
        settings.cleanup_hour,
        settings.cleanup_hour,
    )
    build_scheduler().start()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
