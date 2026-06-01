"""批次创建与查询（parse-stage 前半：建 job/items + 持久化 docx）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.errors import bad_request, not_found
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.folder import Folder
from app.parser import VALID_MODES
from app.schemas.batch import BatchImportCreate
from app.services import upload_service


def create_batch(
    db: Session, *, payload: BatchImportCreate, created_by: str | None
) -> BatchImportJob:
    if payload.parse_mode not in VALID_MODES:
        raise bad_request(
            "PARSE_FAILED",
            f"未知解析模式：{payload.parse_mode}",
            "parse_mode",
        )

    folder = db.execute(
        select(Folder).where(Folder.id == payload.folder_id, Folder.is_active.is_(True))
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("FOLDER_NOT_FOUND", "目标文件夹不存在", "folder_id")

    job = BatchImportJob(
        folder_id=payload.folder_id,
        parse_mode=payload.parse_mode,
        status="parsing",
        counts={
            "total": len(payload.items),
            "parsed": 0,
            "review": 0,
            "applied": 0,
            "failed": 0,
        },
        created_by=created_by,
    )
    db.add(job)
    db.flush()

    for spec in payload.items:
        read = upload_service.try_read_source(spec.upload_token)
        if read is None:
            raise bad_request(
                "UPLOAD_TOKEN_INVALID",
                f"上传凭证无效或已过期：{spec.filename}",
                "upload_token",
            )
        data, _src_filename = read
        item = BatchImportItem(
            job_id=job.id,
            filename=spec.filename,
            content_hash=hashlib.sha256(data).hexdigest(),
            status="queued",
        )
        db.add(item)
        db.flush()

        path = storage.batch_docx_path(job.id, item.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        item.docx_ref = str(path.relative_to(storage.storage_root()).as_posix())

    return job


def get_job(db: Session, job_id: str) -> BatchImportJob:
    job = db.execute(
        select(BatchImportJob).where(
            BatchImportJob.id == job_id,
            BatchImportJob.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if job is None:
        raise not_found("BATCH_JOB_NOT_FOUND", "批次不存在")
    return job


def list_items(
    db: Session, job_id: str, *, status_filter: str | None = None
) -> list[BatchImportItem]:
    stmt = (
        select(BatchImportItem)
        .where(
            BatchImportItem.job_id == job_id,
            BatchImportItem.is_active.is_(True),
        )
        .order_by(BatchImportItem.created_at)
    )
    if status_filter:
        stmt = stmt.where(BatchImportItem.status == status_filter)
    return list(db.execute(stmt).scalars())


def get_item(db: Session, job_id: str, item_id: str) -> BatchImportItem:
    item = db.execute(
        select(BatchImportItem).where(
            BatchImportItem.id == item_id,
            BatchImportItem.job_id == job_id,
            BatchImportItem.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if item is None:
        raise not_found("BATCH_ITEM_NOT_FOUND", "批次条目不存在")
    return item


def load_blob(db: Session, job_id: str, item_id: str) -> dict[str, Any]:
    item = get_item(db, job_id, item_id)
    if not item.parse_blob_ref:
        raise not_found("BATCH_BLOB_NOT_READY", "该条目尚未解析完成")
    path = storage.batch_blob_path(job_id, item_id)
    if not path.exists():
        raise not_found("BATCH_BLOB_NOT_FOUND", "解析结果已丢失")
    blob: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return blob
