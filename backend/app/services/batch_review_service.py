"""批量审阅后端：应用入队 / dry-run / 暂存改判 / retry / skip / undo。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.batch import BatchImportItem
from app.schemas.batch import ApplyPreviewOut
from app.services import batch_import_service


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
