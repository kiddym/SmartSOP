"""批量落库：节点树重建 / 图片提升 / 幂等。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import storage, tenant
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.procedure import Procedure
from app.services import batch_apply_service


def _seed_review_item(db: Session, *, folder_id: str, company_id: str = "co-1") -> BatchImportItem:
    job = BatchImportJob(
        folder_id=folder_id,
        parse_mode="smart",
        counts={"total": 1, "parsed": 1, "review": 1, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    item = BatchImportItem(
        job_id=job.id,
        filename="alpha.docx",
        status="review",
        docx_ref="batch/x/y/source.docx",
    )
    db.add(item)
    db.flush()
    blob = {
        "metadata": {
            "total_chapters": 1,
            "image_count": 0,
            "table_count": 0,
            "body_start_index": 0,
            "body_start_detected_by": "t",
            "format": "docx",
            "parse_time_ms": 0,
        },
        "chapters": [
            {
                "id": "n1",
                "title": "第一章",
                "level": 1,
                "order": 0,
                "parent_id": None,
                "content_type": "chapter",
                "rich_content": "",
                "skip_numbering": False,
                "confidence": 1.0,
                "confidence_tier": "high",
                "mark_status": "unmarked",
                "heading_source": "style",
                "children": [
                    {
                        "id": "n2",
                        "title": "",
                        "level": 2,
                        "order": 0,
                        "parent_id": "n1",
                        "content_type": "content",
                        "rich_content": "<p>正文</p>",
                        "skip_numbering": False,
                        "confidence": 1.0,
                        "confidence_tier": "high",
                        "mark_status": "unmarked",
                        "heading_source": None,
                        "children": [],
                    },
                ],
            },
        ],
        "assets": [],
        "detected_patterns": [],
        "validation": None,
        "warnings": [],
        "review_required": 0,
        "parse_method": "smart",
    }
    path = storage.batch_blob_path(item.job_id, item.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")
    item.parse_blob_ref = str(path.relative_to(storage.storage_root()).as_posix())
    db.commit()
    return item


def test_apply_item_creates_procedure_with_nodes(db: Session, storage_tmp, factory) -> None:
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    item = _seed_review_item(db, folder_id=folder.id)

    batch_apply_service.apply_item(db, item)
    db.commit()

    fresh = db.get(BatchImportItem, item.id)
    assert fresh.status == "applied"
    assert fresh.created_procedure_id is not None
    proc = db.get(Procedure, fresh.created_procedure_id)
    assert proc is not None
    assert proc.code.startswith("QC-")
    assert proc.level_of_use == "reference"


def test_apply_item_is_idempotent(db: Session, storage_tmp, factory) -> None:
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    item = _seed_review_item(db, folder_id=folder.id)

    batch_apply_service.apply_item(db, item)
    db.commit()
    first_pid = db.get(BatchImportItem, item.id).created_procedure_id

    item.status = "applying"
    db.commit()
    batch_apply_service.apply_item(db, item)
    db.commit()
    assert db.get(BatchImportItem, item.id).created_procedure_id == first_pid


def test_apply_item_skips_content_hash_duplicate(db: Session, storage_tmp, factory) -> None:
    """已有同 content_hash 的已落库条目 → 本项跳过、不建程序（兑现 dry-run 承诺）。"""
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    item = _seed_review_item(db, folder_id=folder.id)
    item.content_hash = "DUPHASH"
    # 同租户、同 hash 的既有已落库条目
    sibling = BatchImportItem(
        job_id=item.job_id, filename="prior.docx", status="applied",
        content_hash="DUPHASH", created_procedure_id="p-prior",
    )
    db.add(sibling)
    db.commit()

    batch_apply_service.apply_item(db, item)
    db.commit()

    fresh = db.get(BatchImportItem, item.id)
    assert fresh is not None
    assert fresh.status == "skipped"
    assert fresh.created_procedure_id is None  # 未建程序
