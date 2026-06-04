"""BatchImportJob / BatchImportItem 模型默认值与关系测试。"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.batch import BatchImportItem, BatchImportJob

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_job_defaults(db: Session) -> None:
    job = BatchImportJob(folder_id="f1", parse_mode="smart")
    db.add(job)
    db.commit()
    assert job.id  # UUID 自动生成
    assert job.status == "parsing"
    assert job.counts == {}
    assert job.is_active is True
    assert job.created_at is not None


def test_item_defaults_and_relationship(db: Session) -> None:
    job = BatchImportJob(folder_id="f1")
    db.add(job)
    db.commit()
    item = BatchImportItem(job_id=job.id, filename="a.docx")
    db.add(item)
    db.commit()
    assert item.status == "queued"
    assert item.summary == {}
    assert item.review_revision == 1
    assert item.attempts == 0
    assert item.created_procedure_id is None
    assert item.job.id == job.id
    assert job.items[0].id == item.id
