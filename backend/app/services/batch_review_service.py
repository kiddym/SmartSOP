"""批量审阅后端：应用入队 / dry-run / 暂存改判 / retry / skip / undo。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import bad_request, conflict, not_found
from app.models.base import utcnow
from app.models.batch import BatchImportItem
from app.models.procedure import Procedure
from app.schemas.batch import ApplyPreviewOut, ReviewPatchRequest, ReviewPatchResult
from app.services import batch_import_service, batch_parse_service


def enqueue_apply(
    db: Session, job_id: str, *, item_ids: list[str] | None, high_confidence_only: bool
) -> int:
    """把选中的 review 项置 applying 入队。返回入队数。"""
    batch_import_service.get_job(db, job_id)  # 404 / 租户隔离
    stmt = select(BatchImportItem).where(
        BatchImportItem.job_id == job_id,
        BatchImportItem.status == "review",
        BatchImportItem.is_active.is_(True),
    )
    if item_ids is not None:  # 空列表 = 显式未选 → .in_([]) 匹配 0 项（区别于 None=全部）
        stmt = stmt.where(BatchImportItem.id.in_(item_ids))
    items = list(db.execute(stmt).scalars())
    if high_confidence_only:
        items = [i for i in items if (i.summary or {}).get("confidence_tier") == "high"]
    if not items:
        raise bad_request("BATCH_NO_APPLICABLE_ITEMS", "没有可应用的待审阅条目")
    for item in items:
        item.status = "applying"
        item.leased_until = None
    batch_parse_service.recompute_counts(db, job_id)  # 入队后即时刷新计数（review 数下降）
    db.flush()
    return len(items)


def preview_apply(db: Session, job_id: str, *, item_ids: list[str] | None) -> ApplyPreviewOut:
    """dry-run：统计新建数 + content_hash 命中已落库的重复跳过数。

    无"编号冲突"——FolderSequence 自增取号不撞号。
    """
    job = batch_import_service.get_job(db, job_id)
    stmt = select(BatchImportItem).where(
        BatchImportItem.job_id == job_id,
        BatchImportItem.status == "review",
        BatchImportItem.is_active.is_(True),
    )
    if item_ids is not None:  # 空列表 = 显式未选（与 enqueue_apply 一致）
        stmt = stmt.where(BatchImportItem.id.in_(item_ids))
    candidates = list(db.execute(stmt).scalars())

    applied_hashes: set[str] = {
        h
        for (h,) in db.execute(
            select(BatchImportItem.content_hash).where(
                BatchImportItem.status == "applied",
                BatchImportItem.content_hash != "",
                BatchImportItem.is_active.is_(True),
            )
        )
    }
    duplicate = sum(1 for c in candidates if c.content_hash and c.content_hash in applied_hashes)
    return ApplyPreviewOut(
        to_create=len(candidates) - duplicate,
        duplicate_skip=duplicate,
        target_folder_id=job.folder_id,
    )


def apply_review_ops(
    db: Session, job_id: str, item_id: str, *, payload: ReviewPatchRequest
) -> ReviewPatchResult:
    """读-改-写暂存 blob 的节点判定，review_revision 乐观锁（冲突 409）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.review_revision != payload.review_revision:
        raise conflict("VERSION_CONFLICT", "该条目已被修改，请刷新后重试")
    if not item.parse_blob_ref:
        raise not_found("BATCH_BLOB_NOT_READY", "该条目尚未解析完成")

    path = storage.batch_blob_path(job_id, item_id)
    blob = json.loads(path.read_text(encoding="utf-8"))
    index = _index_nodes(blob.get("chapters", []))

    for op in payload.ops:
        node = index.get(op.node_id)
        if node is None:
            raise not_found("BATCH_NODE_NOT_FOUND", f"节点不存在：{op.node_id}")
        if op.action == "to_content":
            node["content_type"] = "content"
        elif op.action == "to_chapter":
            node["content_type"] = "chapter"
        elif op.action == "set_level":
            if op.level is None:
                raise bad_request("VALIDATION_FAILED", "set_level 需指定 level", field="level")
            node["level"] = op.level
        elif op.action == "accept":
            node["mark_status"] = "unmarked"

    path.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    item.review_revision += 1
    db.flush()
    return ReviewPatchResult(review_revision=item.review_revision)


def _index_nodes(chapters: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def walk(nodes: list[dict[str, Any]]) -> None:
        for n in nodes:
            out[n["id"]] = n
            walk(n.get("children", []))

    walk(chapters)
    return out


def retry_item(db: Session, job_id: str, item_id: str) -> None:
    """失败项重排队（重新被 parse worker 领取）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status != "failed":
        raise bad_request("BATCH_ITEM_NOT_FAILED", "仅失败条目可重试")
    item.status = "queued"
    item.error = None
    item.leased_until = None
    db.flush()


def skip_item(db: Session, job_id: str, item_id: str) -> None:
    """跳过该条目（不落库）。"""
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status not in ("review", "failed"):
        raise bad_request("BATCH_ITEM_NOT_SKIPPABLE", "仅待审阅/失败条目可跳过")
    item.status = "skipped"
    batch_parse_service.recompute_counts(db, item.job_id)
    db.flush()


def undo_item(db: Session, job_id: str, item_id: str) -> None:
    """撤销已落库（软删刚建程序，条目回 review）。

    MVP 直接软删 Procedure；接审计/版本流的完整废止留作演进。
    """
    item = batch_import_service.get_item(db, job_id, item_id)
    if item.status != "applied" or item.created_procedure_id is None:
        raise bad_request("BATCH_ITEM_NOT_APPLIED", "仅已应用条目可撤销")
    proc = db.get(Procedure, item.created_procedure_id)
    if proc is not None:
        proc.is_active = False
        proc.deleted_at = utcnow()
    item.created_procedure_id = None
    item.status = "review"
    batch_parse_service.recompute_counts(db, item.job_id)
    db.flush()
