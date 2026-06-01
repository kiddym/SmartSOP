"""邮件投递调度任务（Phase 5B）。

bypass_tenant_scope 扫所有租户 pending outbox，逐租户 set_current_company_id 后投递。
sent/failed 不再被扫，天然幂等。CLI：python -m app.tasks.email_dispatch
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.email import get_email_backend
from app.logging_config import configure_logging
from app.models.email_outbox import EmailOutbox
from app.services import email_outbox_service
from app.tenant import (
    bypass_tenant_scope,
    reset_current_company_id,
    set_current_company_id,
)

logger = logging.getLogger(__name__)
TASK_NAME = "email_dispatch"


def run(db: Session, *, backend=None, max_attempts: int | None = None) -> dict[str, int]:
    backend = backend if backend is not None else get_email_backend()
    max_attempts = max_attempts if max_attempts is not None else settings.email_max_attempts

    with bypass_tenant_scope():
        company_ids = {
            cid for (cid,) in db.execute(
                select(EmailOutbox.company_id).where(EmailOutbox.status == "pending").distinct()
            ).all()
        }

    total = {"sent": 0, "failed_attempt": 0}
    for cid in company_ids:
        token = set_current_company_id(cid)
        try:
            res = email_outbox_service.deliver_pending(
                db, backend=backend, max_attempts=max_attempts, company_id=cid)
            total["sent"] += res["sent"]
            total["failed_attempt"] += res["failed_attempt"]
        finally:
            reset_current_company_id(token)

    db.commit()
    logger.info(json.dumps({"task": TASK_NAME, **total}, ensure_ascii=False))
    return total


def main() -> None:  # pragma: no cover
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
