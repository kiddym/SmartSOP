"""解析 worker（parse-stage 后半）：领取租约 + 解析单项 + 计数重算 + reaper。

租户铁律：领取用 bypass_tenant_scope() 跨租户；解析单项前 set_current_company_id
进入该 item 的租户上下文。SKIP LOCKED 在 SQLite 上是 no-op（仅 MySQL 真并发安全）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage, tenant
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.parser import parse_docx
from app.parser.result import ParseResult
from app.schemas.parse import build_parse_response
from app.services import batch_media_service

logger = logging.getLogger(__name__)

_LEASE_TTL_SECONDS = 300


def claim_queued(
    db: Session, *, limit: int, now: datetime, lease_ttl_seconds: int = _LEASE_TTL_SECONDS
) -> list[BatchImportItem]:
    """短事务领取 queued 项：SKIP LOCKED 选行 → 置 parsing + 租约 + attempts++。

    调用方须包在 `with tenant.bypass_tenant_scope():` 内并在返回后 commit。
    """
    rows = list(
        db.execute(
            select(BatchImportItem)
            .where(BatchImportItem.status == "queued", BatchImportItem.is_active.is_(True))
            .order_by(BatchImportItem.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for item in rows:
        item.status = "parsing"
        item.leased_until = now + timedelta(seconds=lease_ttl_seconds)
        item.attempts += 1
    db.flush()
    return rows


def _read_docx(item: BatchImportItem) -> bytes:
    path = storage.storage_root() / item.docx_ref
    return path.read_bytes()


def _parse(data: bytes, mode: str) -> ParseResult:
    return parse_docx(data, mode)


def parse_item(db: Session, item: BatchImportItem) -> None:
    """解析单项：进入租户上下文 → 解析 → 暂存图 + blob + summary → status=review。"""
    token = tenant.set_current_company_id(item.company_id)
    try:
        job = db.get(BatchImportJob, item.job_id)
        mode = job.parse_mode if job else "smart"
        data = _read_docx(item)
        result = _parse(data, mode)

        batch_media_service.stage_media_and_rewrite(result, job_id=item.job_id, item_id=item.id)
        response = build_parse_response(result, assets=[], parse_time_ms=0)

        blob_path = storage.batch_blob_path(item.job_id, item.id)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_text(
            json.dumps(response.model_dump(), ensure_ascii=False), encoding="utf-8"
        )
        item.parse_blob_ref = str(blob_path.relative_to(storage.storage_root()).as_posix())
        item.summary = {
            "chapter_count": result.metadata.total_chapters,
            "confidence_tier": _job_tier(result),
            "warning_count": len(result.warnings),
        }
        item.status = "review"
        item.leased_until = None
        item.error = None
        recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def _job_tier(result: ParseResult) -> str:
    """批次项整体置信：任一章节 low→low，否则任一 medium→medium，否则 high。"""
    tiers = set(_walk_tiers(result))
    if "low" in tiers:
        return "low"
    if "medium" in tiers:
        return "medium"
    return "high"


def _walk_tiers(result: ParseResult) -> list[str]:
    out: list[str] = []

    def walk(nodes: list[Any]) -> None:
        for n in nodes:
            out.append(n.confidence_tier)
            walk(n.children)

    walk(result.chapters)
    return out


def mark_failed(db: Session, item: BatchImportItem, message: str) -> None:
    """标记解析失败（在该 item 的租户上下文执行计数重算）。"""
    token = tenant.set_current_company_id(item.company_id)
    try:
        item.status = "failed"
        item.error = message[:2000]
        item.leased_until = None
        recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def recompute_counts(db: Session, job_id: str) -> None:
    """按当前 items 状态重算 job.counts 与 job.status（须在 job 的租户上下文内）。"""
    items = list(
        db.execute(
            select(BatchImportItem).where(
                BatchImportItem.job_id == job_id, BatchImportItem.is_active.is_(True)
            )
        ).scalars()
    )
    counts = {"total": len(items), "parsed": 0, "review": 0, "applied": 0, "failed": 0, "skipped": 0}
    for it in items:
        if it.status == "review":
            counts["review"] += 1
            counts["parsed"] += 1
        elif it.status == "applied":
            counts["applied"] += 1
            counts["parsed"] += 1
        elif it.status == "failed":
            counts["failed"] += 1
        elif it.status == "skipped":
            counts["skipped"] += 1
    job = db.get(BatchImportJob, job_id)
    if job is not None:
        job.counts = counts
        # 终态 = 无待处理项（applied/failed/skipped 占满），skipped 也算"已了结"，
        # 否则全跳过的批次会永远卡在 reviewing。
        terminal = (
            counts["total"] > 0
            and counts["applied"] + counts["failed"] + counts["skipped"] == counts["total"]
        )
        if terminal:
            # 终态：全失败 → failed；否则（含部分失败/跳过）→ completed
            job.status = "failed" if counts["failed"] == counts["total"] else "completed"
        elif counts["review"] > 0 or counts["applied"] > 0:
            job.status = "reviewing"
    db.flush()


def reclaim_expired(db: Session, *, now: datetime) -> int:
    """reaper：把租约过期的 parsing/applying 项重置回 queued（崩溃自愈）。"""
    with tenant.bypass_tenant_scope():
        rows = list(
            db.execute(
                select(BatchImportItem).where(
                    BatchImportItem.status.in_(["parsing", "applying"]),
                    BatchImportItem.leased_until.is_not(None),
                    BatchImportItem.leased_until < now,
                    BatchImportItem.is_active.is_(True),
                )
            ).scalars()
        )
        for item in rows:
            item.status = "queued" if item.status == "parsing" else "review"
            item.leased_until = None
        db.flush()
    return len(rows)


def run_parse_once(
    db: Session, *, max_items: int = 4, now: datetime | None = None
) -> dict[str, int]:
    """领取一批并逐项解析（逐项提交）。返回 {claimed, parsed, failed}。"""
    started = now or utcnow()
    with tenant.bypass_tenant_scope():
        items = claim_queued(db, limit=max_items, now=started)
        db.commit()
    parsed = 0
    failed = 0
    for item in items:
        try:
            parse_item(db, item)
            db.commit()
            parsed += 1
        except Exception as exc:  # 单项失败不拖垮整批
            db.rollback()
            failed += 1
            logger.exception("batch parse 失败 item_id=%s", item.id)
            try:
                fresh = db.get(BatchImportItem, item.id)
                if fresh is not None:
                    mark_failed(db, fresh, f"解析失败：{exc}")
                    db.commit()
            except Exception:  # 标失败本身再抛 → 回滚保会话干净，不拖垮后续项
                db.rollback()
                logger.exception("batch parse 标记失败也失败 item_id=%s", item.id)
    return {"claimed": len(items), "parsed": parsed, "failed": failed}
