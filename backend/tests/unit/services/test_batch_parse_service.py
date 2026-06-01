"""领取租约 / 解析单项 / reaper 测试（解析用 monkeypatch 桩，不依赖真实 docx）。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app import tenant
from app.models.base import utcnow
from app.models.batch import BatchImportItem, BatchImportJob
from app.parser.result import ParseMetadata, ParseResult
from app.services import batch_parse_service


def _make_job_with_item(db: Session, company_id: str = "co-1") -> tuple[str, str]:
    tenant.set_current_company_id(company_id)
    job = BatchImportJob(
        folder_id="f1",
        counts={"total": 1, "parsed": 0, "review": 0, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    item = BatchImportItem(job_id=job.id, filename="a.docx", status="queued", docx_ref="x")
    db.add(item)
    db.commit()
    tenant.set_current_company_id(None)
    return job.id, item.id


def _fake_parse_result() -> ParseResult:
    return ParseResult(
        metadata=ParseMetadata(
            total_chapters=2,
            image_count=0,
            table_count=0,
            body_start_index=0,
            body_start_detected_by="heuristic",
        ),
        chapters=[],
        parse_method="smart",
    )


def test_claim_marks_parsing_and_sets_lease(db: Session) -> None:
    _job_id, item_id = _make_job_with_item(db)
    now = utcnow()
    with tenant.bypass_tenant_scope():
        claimed = batch_parse_service.claim_queued(db, limit=10, now=now, lease_ttl_seconds=300)
        db.commit()
    assert [c.id for c in claimed] == [item_id]
    fresh = db.get(BatchImportItem, item_id)
    assert fresh is not None
    assert fresh.status == "parsing"
    assert fresh.leased_until is not None and fresh.leased_until > now
    assert fresh.attempts == 1


def test_parse_item_writes_blob_and_sets_review(db: Session, storage_tmp, monkeypatch) -> None:
    job_id, item_id = _make_job_with_item(db)
    monkeypatch.setattr(batch_parse_service, "_read_docx", lambda item: b"fake")
    monkeypatch.setattr(batch_parse_service, "_parse", lambda data, mode: _fake_parse_result())
    item = db.get(BatchImportItem, item_id)
    assert item is not None
    item.status = "parsing"
    db.commit()

    batch_parse_service.parse_item(db, item)
    db.commit()

    fresh = db.get(BatchImportItem, item_id)
    assert fresh is not None
    assert fresh.status == "review"
    assert fresh.summary["chapter_count"] == 2
    assert fresh.summary["confidence_tier"] in {"high", "medium", "low"}
    assert fresh.parse_blob_ref
    from app import storage

    assert storage.batch_blob_path(job_id, item_id).exists()


def test_reclaim_expired_resets_to_queued(db: Session) -> None:
    _job_id, item_id = _make_job_with_item(db)
    item = db.get(BatchImportItem, item_id)
    assert item is not None
    item.status = "parsing"
    item.leased_until = utcnow() - timedelta(seconds=10)
    db.commit()
    n = batch_parse_service.reclaim_expired(db, now=utcnow())
    db.commit()
    assert n == 1
    fresh = db.get(BatchImportItem, item_id)
    assert fresh is not None
    assert fresh.status == "queued"


def test_recompute_counts_all_failed_marks_job_failed(db: Session) -> None:
    """全部条目失败的批次应判 failed，而非 completed（终态判定）。"""
    job_id, item_id = _make_job_with_item(db)
    item = db.get(BatchImportItem, item_id)
    assert item is not None
    batch_parse_service.mark_failed(db, item, "boom")
    db.commit()
    job = db.get(BatchImportJob, job_id)
    assert job is not None
    assert job.counts["failed"] == 1
    assert job.status == "failed"


def test_recompute_counts_terminal_with_some_success_marks_completed(db: Session) -> None:
    """终态混合（部分 applied + 部分 failed）应判 completed。"""
    tenant.set_current_company_id("co-1")
    job = BatchImportJob(
        folder_id="f1",
        counts={"total": 0, "parsed": 0, "review": 0, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    ok = BatchImportItem(job_id=job.id, filename="ok.docx", status="applied", docx_ref="a")
    bad = BatchImportItem(job_id=job.id, filename="bad.docx", status="failed", docx_ref="b")
    db.add_all([ok, bad])
    db.commit()

    batch_parse_service.recompute_counts(db, job.id)
    db.commit()
    tenant.set_current_company_id(None)

    fresh = db.get(BatchImportJob, job.id)
    assert fresh is not None
    assert fresh.status == "completed"
    assert fresh.counts == {
        "total": 2, "parsed": 1, "review": 0, "applied": 1, "failed": 1, "skipped": 0,
    }


def test_recompute_counts_skipped_items_reach_terminal(db: Session) -> None:
    """skipped 也算已了结：applied + skipped 占满 → completed（不卡 reviewing）。"""
    tenant.set_current_company_id("co-1")
    job = BatchImportJob(
        folder_id="f1",
        counts={"total": 0, "parsed": 0, "review": 0, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    ok = BatchImportItem(job_id=job.id, filename="ok.docx", status="applied", docx_ref="a")
    sk = BatchImportItem(job_id=job.id, filename="sk.docx", status="skipped", docx_ref="b")
    db.add_all([ok, sk])
    db.commit()

    batch_parse_service.recompute_counts(db, job.id)
    db.commit()
    tenant.set_current_company_id(None)

    fresh = db.get(BatchImportJob, job.id)
    assert fresh is not None
    assert fresh.status == "completed"  # 而非永久卡 reviewing
    assert fresh.counts["skipped"] == 1


def test_scheduler_registers_batch_jobs() -> None:
    from apscheduler.schedulers.base import STATE_STOPPED

    from app.tasks.scheduler import build_scheduler

    sched = build_scheduler()
    ids = {j.id for j in sched.get_jobs()}
    assert "batch_parse" in ids
    assert "batch_reaper" in ids
    # scheduler was only built, not started — skip shutdown to avoid SchedulerNotRunningError
    assert sched.state == STATE_STOPPED
