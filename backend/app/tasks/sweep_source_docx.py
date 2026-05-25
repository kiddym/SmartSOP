"""孤儿源 docx 巡检/清理（P1 决定 C「手动清理」的配套工具，**不挂 scheduler**）。

扫 ``source_docx/*``，找出无对应 DB 行的 group 目录（落盘孤儿——如历史 C1 缺陷遗留、
或删除版本组后残留的空目录）。默认 dry-run 仅报告；``--delete`` 才物理删。
CLI：``python -m app.tasks.sweep_source_docx [--delete]``。
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
from app.services import source_docx_service

logger = logging.getLogger(__name__)
TASK_NAME = "sweep_source_docx"


def run(db: Session, *, delete: bool = False, now: datetime | None = None) -> dict[str, int]:
    """巡检一次。返回 ``{orphans, removed}``；``delete=False`` 时 removed 恒 0（仅报告）。"""
    started = now or utcnow()
    orphans = source_docx_service.orphan_group_ids(db)
    removed = sum(source_docx_service.delete_group_dir(gid) for gid in orphans) if delete else 0
    summary = {"orphans": len(orphans), "removed": removed}
    logger.info(
        json.dumps(
            {
                "task": TASK_NAME,
                "started_at": started.isoformat(),
                "delete": delete,
                "group_ids": orphans,
                **summary,
            },
            ensure_ascii=False,
        )
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="孤儿源 docx 巡检/清理（一次性）")
    parser.add_argument("--delete", action="store_true", help="物理删除孤儿目录（默认仅报告）")
    args = parser.parse_args(argv)
    configure_logging()
    db = SessionLocal()
    try:
        run(db, delete=args.delete)
    finally:
        db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
