"""暂存改判 / dry-run / 入队 / retry / skip / undo 测试。"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from app import tenant
from app.models.batch import BatchImportItem, BatchImportJob
from app.services import batch_review_service


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
