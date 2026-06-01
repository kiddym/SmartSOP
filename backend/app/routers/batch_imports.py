"""批量导入路由（parse-stage：创建 + 查询 + 暂存 blob/media 读取）。

审阅改判 / dry-run / apply 属 Plan 2。所有端点经 get_current_user 进入请求
租户上下文，行级隔离自动生效。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app import storage
from app.db import get_db
from app.deps import get_current_user
from app.errors import not_found
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.user import User
from app.parser.utils import images
from app.schemas.batch import (
    ApplyPreviewOut,
    BatchApplyRequest,
    BatchApplyResult,
    BatchImportCreate,
    BatchImportItemOut,
    BatchImportJobOut,
    ReviewPatchRequest,
    ReviewPatchResult,
)
from app.services import batch_import_service, batch_review_service

router = APIRouter(prefix="/api/v1/batch-imports", tags=["batch-imports"])


def _job_out(job: BatchImportJob) -> BatchImportJobOut:
    return BatchImportJobOut(
        id=job.id,
        folder_id=job.folder_id,
        parse_mode=job.parse_mode,
        status=job.status,
        counts=job.counts or {},
        created_at=job.created_at,
    )


def _item_out(item: BatchImportItem) -> BatchImportItemOut:
    return BatchImportItemOut(
        id=item.id,
        job_id=item.job_id,
        filename=item.filename,
        status=item.status,
        content_hash=item.content_hash,
        summary=item.summary or {},
        review_revision=item.review_revision,
        error=item.error,
    )


@router.post("", response_model=BatchImportJobOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchImportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchImportJobOut:
    job = batch_import_service.create_batch(db, payload=payload, created_by=user.id)
    db.commit()
    return _job_out(job)


@router.get("/{job_id}", response_model=BatchImportJobOut)
def get_batch(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchImportJobOut:
    return _job_out(batch_import_service.get_job(db, job_id))


@router.get("/{job_id}/items", response_model=list[BatchImportItemOut])
def list_items(
    job_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BatchImportItemOut]:
    batch_import_service.get_job(db, job_id)  # 404 if absent / cross-tenant
    items = batch_import_service.list_items(db, job_id, status_filter=status_filter)
    return [_item_out(i) for i in items]


@router.get("/{job_id}/items/{item_id}/parse-result")
def get_parse_result(
    job_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return batch_import_service.load_blob(db, job_id, item_id)


@router.post("/{job_id}/apply", response_model=BatchApplyResult)
def apply_batch(
    job_id: str,
    payload: BatchApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchApplyResult:
    n = batch_review_service.enqueue_apply(
        db, job_id, item_ids=payload.item_ids, high_confidence_only=payload.high_confidence_only
    )
    db.commit()
    return BatchApplyResult(enqueued=n)


@router.post("/{job_id}/apply-preview", response_model=ApplyPreviewOut)
def apply_preview(
    job_id: str,
    payload: BatchApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplyPreviewOut:
    return batch_review_service.preview_apply(db, job_id, item_ids=payload.item_ids)


@router.patch("/{job_id}/items/{item_id}/review", response_model=ReviewPatchResult)
def patch_review(
    job_id: str,
    item_id: str,
    payload: ReviewPatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReviewPatchResult:
    result = batch_review_service.apply_review_ops(db, job_id, item_id, payload=payload)
    db.commit()
    return result


@router.post("/{job_id}/items/{item_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
def retry_item(
    job_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.retry_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/items/{item_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip_item(
    job_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.skip_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/items/{item_id}/undo", status_code=status.HTTP_204_NO_CONTENT)
def undo_item(
    job_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch_review_service.undo_item(db, job_id, item_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/items/{item_id}/media/{filename}")
def serve_media(
    job_id: str,
    item_id: str,
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    batch_import_service.get_item(db, job_id, item_id)  # 404 / 租户隔离
    media_dir = storage.batch_media_dir(job_id, item_id)
    target = media_dir / filename
    try:
        target.resolve().relative_to(media_dir.resolve())
    except ValueError:
        raise not_found("NOT_FOUND", "图片不存在") from None
    if not target.exists():
        raise not_found("NOT_FOUND", "图片不存在")
    return Response(content=target.read_bytes(), media_type=images.mime_for_ext(target.suffix))
