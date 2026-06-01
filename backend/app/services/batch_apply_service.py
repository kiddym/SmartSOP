"""批量落库 worker（apply-stage）：从暂存 blob 重建节点树并落定稿程序。

复用 procedure_service.create_procedure / node_numbering.recompute /
asset_service。图片从批次 media 提升为永久 asset。created_procedure_id 幂等。
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage, tenant
from app.deps import RequestMeta
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.node import ProcedureNode
from app.schemas.procedure import ProcedureCreate
from app.services import (
    asset_service,
    batch_parse_service,
    node_numbering,
    procedure_service,
    source_docx_service,
)

logger = logging.getLogger(__name__)

_SYSTEM_META = RequestMeta(ip_address="-", user_agent="batch-apply-worker", request_id="batch")
_MEDIA_RE = re.compile(r"/api/v1/batch-imports/[0-9a-fA-F-]+/items/[0-9a-fA-F-]+/media/([^\"]+)")
_LEASE_TTL_SECONDS = 600


def _proc_name(filename: str) -> str:
    base = filename.rsplit(".", 1)[0].strip() or filename
    return base[:200]


def _chapter_body(title: str) -> str:
    # 与 import_service._chapter_body 对齐：strip 后空标题产出空 body（而非 <p></p>），
    # 使批量落库与单份导入的章节 body 一致。
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def _promote_media(db: Session, procedure_id: str, body: str, *, job_id: str, item_id: str) -> str:
    media_dir = storage.batch_media_dir(job_id, item_id)

    def repl(m: re.Match[str]) -> str:
        filename = m.group(1)
        path = media_dir / filename
        try:
            path.resolve().relative_to(media_dir.resolve())
        except ValueError:
            return m.group(0)
        if not path.exists():
            return m.group(0)
        asset = asset_service.find_or_create_asset(
            db,
            path.read_bytes(),
            ext=Path(filename).suffix,
            source_meta={"source": "batch_import", "job_id": job_id},
        )
        return asset_service.asset_url(procedure_id, asset.id)

    return _MEDIA_RE.sub(repl, body)


def _build_nodes(
    db: Session, procedure_id: str, chapters: list[dict[str, Any]], *, job_id: str, item_id: str
) -> None:
    order = 0

    def walk(nodes: list[dict[str, Any]]) -> None:
        nonlocal order
        for n in nodes:
            order += 1
            if n.get("content_type") == "chapter":
                body = _chapter_body(n.get("title", ""))
                heading_level = n.get("level")
                # 保留解析期捕获的样式名（与 import_service 一致，供 round-trip/重导出）
                source_style_name = n.get("source_style_name")
            else:
                body = _promote_media(
                    db, procedure_id, n.get("rich_content", ""), job_id=job_id, item_id=item_id
                )
                heading_level = None
                source_style_name = None
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    body=body,
                    sort_order=order * 1000,
                    heading_level=heading_level,
                    kind="node",
                    skip_numbering=bool(n.get("skip_numbering", False)),
                    input_schema={},
                    # 整批已通过审阅 → 落库节点统一 unmarked（不沿用 blob 的 review 标记）
                    mark_status="unmarked",
                    source_style_name=source_style_name,
                )
            )
            walk(n.get("children", []))

    walk(chapters)
    db.flush()


def _has_applied_duplicate(db: Session, item: BatchImportItem) -> bool:
    """是否已有同 content_hash 的已落库条目（与 preview_apply 的 duplicate 判定同语义）。

    须在 item 的租户上下文内调用——查询受 ORM 隔离自动限定到本租户。
    """
    hit = db.execute(
        select(BatchImportItem.id).where(
            BatchImportItem.status == "applied",
            BatchImportItem.content_hash == item.content_hash,
            BatchImportItem.content_hash != "",
            BatchImportItem.is_active.is_(True),
            BatchImportItem.id != item.id,
        )
    ).first()
    return hit is not None


def apply_item(db: Session, item: BatchImportItem) -> None:
    """落库单项：进入租户上下文，幂等检查，建 procedure + 节点树 + 源 docx。"""
    token = tenant.set_current_company_id(item.company_id)
    try:
        if item.created_procedure_id is not None:
            item.status = "applied"
            batch_parse_service.recompute_counts(db, item.job_id)
            return
        # content_hash 去重：已有同 hash 的已落库条目 → 跳过（兑现 dry-run preview 的 duplicate_skip 承诺）
        if item.content_hash and _has_applied_duplicate(db, item):
            item.status = "skipped"
            item.leased_until = None
            item.error = None
            batch_parse_service.recompute_counts(db, item.job_id)
            return
        job = db.get(BatchImportJob, item.job_id)
        if job is None:
            raise RuntimeError("批次不存在")

        blob_path = storage.batch_blob_path(item.job_id, item.id)
        blob = json.loads(blob_path.read_text(encoding="utf-8"))

        proc = procedure_service.create_procedure(
            db,
            ProcedureCreate(
                folder_id=job.folder_id, name=_proc_name(item.filename), level_of_use="reference"
            ),
            _SYSTEM_META,
        )
        _build_nodes(db, proc.id, blob.get("chapters", []), job_id=item.job_id, item_id=item.id)
        node_numbering.recompute(db, proc.id)
        asset_service.rebuild_references(db, proc.id)

        docx_path = storage.storage_root() / item.docx_ref
        if docx_path.exists():
            source_docx_service.store_from_bytes(
                db,
                procedure_group_id=proc.procedure_group_id,
                data=docx_path.read_bytes(),
                filename=item.filename,
            )

        item.created_procedure_id = proc.id
        item.status = "applied"
        item.leased_until = None
        item.error = None
        batch_parse_service.recompute_counts(db, item.job_id)
    finally:
        tenant.reset_current_company_id(token)


def claim_applying(
    db: Session, *, limit: int, now: datetime, lease_ttl_seconds: int = _LEASE_TTL_SECONDS
) -> list[BatchImportItem]:
    rows = list(
        db.execute(
            select(BatchImportItem)
            .where(BatchImportItem.status == "applying", BatchImportItem.is_active.is_(True))
            .order_by(BatchImportItem.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for item in rows:
        item.leased_until = now + timedelta(seconds=lease_ttl_seconds)
        item.attempts += 1
    db.flush()
    return rows


def run_apply_once(
    db: Session, *, max_items: int = 4, now: datetime | None = None
) -> dict[str, int]:
    started = now or utcnow()
    with tenant.bypass_tenant_scope():
        items = claim_applying(db, limit=max_items, now=started)
        db.commit()
    applied = 0
    failed = 0
    for item in items:
        try:
            apply_item(db, item)
            db.commit()
            applied += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            logger.exception("batch apply 失败 item_id=%s", item.id)
            try:
                fresh = db.get(BatchImportItem, item.id)
                if fresh is not None:
                    batch_parse_service.mark_failed(db, fresh, f"落库失败：{exc}")
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception("batch apply 标记失败也失败 item_id=%s", item.id)
    return {"claimed": len(items), "applied": applied, "failed": failed}
