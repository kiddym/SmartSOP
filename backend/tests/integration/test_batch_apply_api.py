"""apply 端到端：建批次→apply 入队→apply worker 落库→程序生成。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import storage, tenant
from app.deps import get_current_user
from app.main import app
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.company import Company
from app.models.procedure import Procedure
from app.models.user import User
from app.services import batch_apply_service


@pytest.fixture
def auth_client(client: TestClient, db: Session):
    # 挂闸后 require_feature 会按 fake user 的 company_id 查公司套餐；建一家 enterprise
    # 公司（id 即 co-1）以解锁 sop，并设 tenant 上下文让 factory 直建行落到该公司。
    db.add(
        Company(
            id="co-1",
            name="BatchCo",
            slug="batchco",
            plan="enterprise",
            subscription_status="active",
        )
    )
    db.commit()
    fake = User(id="u-1", email="t@e.com", password_hash="x", company_id="co-1", name="测试")
    app.dependency_overrides[get_current_user] = lambda: fake
    tenant.set_current_company_id("co-1")
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _seed_blob(item: BatchImportItem) -> None:
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
                "title": "章",
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
                "children": [],
            }
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


def test_apply_flow_creates_procedure(
    auth_client: TestClient, engine: Engine, storage_tmp, factory, db: Session
) -> None:
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    factory.sequence(folder.id)
    job = BatchImportJob(
        folder_id=folder.id,
        parse_mode="smart",
        counts={"total": 1, "parsed": 1, "review": 1, "applied": 0, "failed": 0},
    )
    db.add(job)
    db.flush()
    item = BatchImportItem(job_id=job.id, filename="a.docx", status="review", docx_ref="x")
    db.add(item)
    db.flush()
    _seed_blob(item)
    db.commit()

    resp = auth_client.post(f"/api/v1/batch-imports/{job.id}/apply", json={"item_ids": [item.id]})
    assert resp.status_code == 200
    assert resp.json()["enqueued"] == 1

    with Session(engine, expire_on_commit=False) as worker_db:
        batch_apply_service.run_apply_once(worker_db, max_items=10)

    fresh = db.get(BatchImportItem, item.id)
    db.refresh(fresh)
    assert fresh.status == "applied"
    proc = db.get(Procedure, fresh.created_procedure_id)
    assert proc is not None and proc.code.startswith("QC-")
