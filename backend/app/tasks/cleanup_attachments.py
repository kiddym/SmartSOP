"""附件磁盘清理任务（§53.2 / Q115 / Q332 / Q371）。

每日删除「无 active 引用 + 软删 ≥ 30 天」的孤儿附件：按 storage_path 分组，**先删
文件再硬删行**（行 + 文件同删）+ **逐项提交**（一个坏文件不拖垮整批）。
CLI：``python -m app.tasks.cleanup_attachments --once``。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.services import attachment_service

logger = logging.getLogger(__name__)
TASK_NAME = "cleanup_attachments"


def run(
    db: Session,
    *,
    now: datetime | None = None,
    retention_days: int | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """执行一次清理（逐项提交）。返回 ``{scanned, deleted, errors}`` 摘要。"""
    started = now or utcnow()
    retention = retention_days if retention_days is not None else settings.attachment_retention_days
    paths = attachment_service.orphan_storage_paths(db, retention_days=retention, now=started)
    deleted = 0
    errors = 0
    for path in paths:
        try:
            removed = attachment_service.delete_orphan_path(
                db, path, retention_days=retention, now=started
            )
            if removed > 0:
                if commit:
                    db.commit()
                deleted += removed
            elif commit:
                db.rollback()
        except Exception:  # 单项失败记日志并继续（§53.2 逐项提交）
            if commit:
                db.rollback()
            errors += 1
            logger.exception("cleanup_attachments 删除失败 storage_path=%s", path)

    summary = {"scanned": len(paths), "deleted": deleted, "errors": errors}
    logger.info(
        json.dumps(
            {"task": TASK_NAME, "started_at": started.isoformat(), **summary}, ensure_ascii=False
        )
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="附件孤儿磁盘清理（一次性）")
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
