"""暂存改判 / dry-run / 入队 / retry / skip / undo 测试。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import storage, tenant
from app.models.batch import BatchImportItem, BatchImportJob
from app.schemas.batch import ReviewOp, ReviewPatchRequest
from app.services import batch_import_service, batch_review_service


def _job(db: Session, folder_id: str = "f1", company_id: str = "co-1") -> BatchImportJob:
    tenant.set_current_company_id(company_id)
    job = BatchImportJob(
        folder_id=folder_id,
        counts={"total": 0, "parsed": 0, "review": 0, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    return job


def _item(
    db: Session,
    job: BatchImportJob,
    *,
    status: str,
    content_hash: str = "",
    procedure_id: str | None = None,
    summary: dict[str, Any] | None = None,
) -> BatchImportItem:
    item = BatchImportItem(
        job_id=job.id,
        filename="a.docx",
        status=status,
        content_hash=content_hash,
        created_procedure_id=procedure_id,
        summary=summary or {},
    )
    db.add(item)
    db.flush()
    return item


def test_enqueue_apply_none_means_all_review_items(db: Session) -> None:
    job = _job(db)
    a = _item(db, job, status="review")
    b = _item(db, job, status="review")
    _item(db, job, status="failed")  # 非 review 不入队
    db.commit()

    n = batch_review_service.enqueue_apply(db, job.id, item_ids=None, high_confidence_only=False)
    db.commit()
    assert n == 2
    assert db.get(BatchImportItem, a.id).status == "applying"
    assert db.get(BatchImportItem, b.id).status == "applying"


def test_enqueue_apply_specific_ids(db: Session) -> None:
    job = _job(db)
    a = _item(db, job, status="review")
    b = _item(db, job, status="review")
    db.commit()

    n = batch_review_service.enqueue_apply(db, job.id, item_ids=[a.id], high_confidence_only=False)
    db.commit()
    assert n == 1
    assert db.get(BatchImportItem, a.id).status == "applying"
    assert db.get(BatchImportItem, b.id).status == "review"  # 未选中保持不变


def test_enqueue_apply_empty_list_selects_nothing(db: Session) -> None:
    """显式空列表 = 未选任何项 → 0 候选 → bad_request（区别于 None=全部）。"""
    job = _job(db)
    _item(db, job, status="review")
    db.commit()

    with pytest.raises(Exception) as ei:
        batch_review_service.enqueue_apply(db, job.id, item_ids=[], high_confidence_only=False)
    assert "BATCH_NO_APPLICABLE_ITEMS" in str(ei.value)


def test_enqueue_apply_high_confidence_only_filters(db: Session) -> None:
    job = _job(db)
    hi = _item(db, job, status="review", summary={"confidence_tier": "high"})
    _item(db, job, status="review", summary={"confidence_tier": "low"})
    db.commit()

    n = batch_review_service.enqueue_apply(db, job.id, item_ids=None, high_confidence_only=True)
    db.commit()
    assert n == 1
    assert db.get(BatchImportItem, hi.id).status == "applying"


def test_enqueue_apply_no_review_items_raises(db: Session) -> None:
    job = _job(db)
    _item(db, job, status="failed")
    db.commit()
    with pytest.raises(Exception) as ei:
        batch_review_service.enqueue_apply(db, job.id, item_ids=None, high_confidence_only=False)
    assert "BATCH_NO_APPLICABLE_ITEMS" in str(ei.value)


def test_preview_counts_new_and_duplicates(db: Session) -> None:
    job = _job(db)
    _item(db, job, status="applied", content_hash="HASH1", procedure_id="p-existing")
    a = _item(db, job, status="review", content_hash="HASH2")
    b = _item(db, job, status="review", content_hash="HASH1")  # 与已 applied 重复
    db.commit()

    out = batch_review_service.preview_apply(db, job.id, item_ids=[a.id, b.id])
    assert out.to_create == 1
    assert out.duplicate_skip == 1
    assert out.target_folder_id == "f1"


def _review_item_with_blob(db: Session, job: BatchImportJob) -> BatchImportItem:
    item = _item(db, job, status="review")
    blob = {
        "metadata": {},
        "assets": [],
        "detected_patterns": [],
        "validation": None,
        "warnings": [],
        "review_required": 1,
        "parse_method": "smart",
        "chapters": [
            {
                "id": "n1",
                "title": "标题",
                "level": 2,
                "order": 0,
                "parent_id": None,
                "content_type": "chapter",
                "rich_content": "",
                "skip_numbering": False,
                "confidence": 0.5,
                "confidence_tier": "medium",
                "mark_status": "review",
                "heading_source": "heuristic",
                "children": [],
            }
        ],
    }
    path = storage.batch_blob_path(item.job_id, item.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")
    item.parse_blob_ref = str(path.relative_to(storage.storage_root()).as_posix())
    db.commit()
    return item


def test_apply_review_ops_rewrites_blob_and_bumps_revision(db: Session, storage_tmp: Any) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)
    assert item.review_revision == 1

    result = batch_review_service.apply_review_ops(
        db,
        job.id,
        item.id,
        payload=ReviewPatchRequest(
            review_revision=1,
            ops=[
                ReviewOp(node_id="n1", action="to_content"),
                ReviewOp(node_id="n1", action="accept"),
            ],
        ),
    )
    db.commit()
    assert result.review_revision == 2
    blob = batch_import_service.load_blob(db, job.id, item.id)
    assert blob["chapters"][0]["content_type"] == "content"
    assert blob["chapters"][0]["mark_status"] == "unmarked"


def test_apply_review_ops_conflict_raises_409(db: Session, storage_tmp: Any) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)
    with pytest.raises(HTTPException) as ei:
        batch_review_service.apply_review_ops(
            db,
            job.id,
            item.id,
            payload=ReviewPatchRequest(
                review_revision=99,  # 陈旧
                ops=[ReviewOp(node_id="n1", action="accept")],
            ),
        )
    assert ei.value.status_code == 409


def test_apply_review_ops_to_chapter_and_set_level(db: Session, storage_tmp: Any) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)

    result = batch_review_service.apply_review_ops(
        db,
        job.id,
        item.id,
        payload=ReviewPatchRequest(
            review_revision=1,
            ops=[
                ReviewOp(node_id="n1", action="to_content"),
                ReviewOp(node_id="n1", action="to_chapter"),  # 回到 chapter
                ReviewOp(node_id="n1", action="set_level", level=3),
            ],
        ),
    )
    db.commit()
    assert result.review_revision == 2
    blob = batch_import_service.load_blob(db, job.id, item.id)
    assert blob["chapters"][0]["content_type"] == "chapter"
    assert blob["chapters"][0]["level"] == 3


def test_apply_review_ops_set_level_without_level_raises_and_no_write(
    db: Session, storage_tmp: Any
) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)

    with pytest.raises(HTTPException) as ei:
        batch_review_service.apply_review_ops(
            db,
            job.id,
            item.id,
            payload=ReviewPatchRequest(
                review_revision=1,
                ops=[ReviewOp(node_id="n1", action="set_level", level=None)],
            ),
        )
    assert ei.value.status_code == 400
    # 校验失败 → 不写 blob、不递增 revision
    fresh = db.get(BatchImportItem, item.id)
    assert fresh is not None
    assert fresh.review_revision == 1
    blob = batch_import_service.load_blob(db, job.id, item.id)
    assert blob["chapters"][0]["level"] == 2  # 原值未动


def test_apply_review_ops_unknown_node_raises_404(db: Session, storage_tmp: Any) -> None:
    job = _job(db)
    item = _review_item_with_blob(db, job)
    with pytest.raises(HTTPException) as ei:
        batch_review_service.apply_review_ops(
            db,
            job.id,
            item.id,
            payload=ReviewPatchRequest(
                review_revision=1,
                ops=[ReviewOp(node_id="nope", action="accept")],
            ),
        )
    assert ei.value.status_code == 404
