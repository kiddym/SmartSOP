"""批量解析后台任务入口（由 scheduler 周期调用）。

parse tick：领取并解析一批 queued 项。reaper tick：回收过期租约。
两者都自管 Session，逐项提交在 service 内完成。
CLI（手动跑一次）：python -m app.tasks.batch_parse --once
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.services import batch_parse_service

logger = logging.getLogger(__name__)


def run_parse(max_items: int = 4) -> dict[str, int]:
    db = SessionLocal()
    try:
        return batch_parse_service.run_parse_once(db, max_items=max_items)
    finally:
        db.close()


def run_reaper() -> int:
    db = SessionLocal()
    try:
        n = batch_parse_service.reclaim_expired(db, now=utcnow())
        db.commit()
        return n
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="批量解析（一次性）")
    parser.add_argument("--once", action="store_true", help="执行一次解析 tick 后退出")
    parser.parse_args(argv)
    configure_logging()
    summary = run_parse()
    logger.info("batch_parse once: %s", summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
