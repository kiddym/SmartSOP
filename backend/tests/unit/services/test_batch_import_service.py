"""批次暂存路径 + 创建/查询 service 测试。"""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy.orm import Session

from app import storage, tenant
from app.schemas.batch import BatchImportCreate, BatchImportItemIn
from app.services import batch_import_service, upload_service


def test_batch_paths_are_nested_under_storage_root(monkeypatch) -> None:
    import app.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_dir", "/tmp/sop-test-store")
    docx = storage.batch_docx_path("job1", "item1")
    blob = storage.batch_blob_path("job1", "item1")
    media = storage.batch_media_dir("job1", "item1")
    assert docx.as_posix().endswith("batch/job1/item1/source.docx")
    assert blob.as_posix().endswith("batch/job1/item1/parse.json")
    assert media.as_posix().endswith("batch/job1/item1/media")


def _minimal_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


def _upload(filename: str = "a.docx") -> str:
    res = upload_service.save_upload(_minimal_docx_bytes(), filename)
    return res.upload_token


def test_create_batch_persists_docx_and_queues_items(db: Session, storage_tmp, factory) -> None:
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    token = _upload("first.docx")

    job = batch_import_service.create_batch(
        db,
        payload=BatchImportCreate(
            folder_id=folder.id,
            parse_mode="smart",
            items=[BatchImportItemIn(filename="first.docx", upload_token=token)],
        ),
        created_by=None,
    )
    db.commit()

    assert job.status == "parsing"
    assert job.company_id == "co-1"
    items = batch_import_service.list_items(db, job.id)
    assert len(items) == 1
    assert items[0].status == "queued"
    assert items[0].content_hash
    assert storage.batch_docx_path(job.id, items[0].id).exists()


def test_create_batch_rejects_missing_folder(db: Session, storage_tmp) -> None:
    tenant.set_current_company_id("co-1")
    token = _upload()
    with pytest.raises(Exception) as ei:
        batch_import_service.create_batch(
            db,
            payload=BatchImportCreate(
                folder_id="nope",
                items=[BatchImportItemIn(filename="a.docx", upload_token=token)],
            ),
            created_by=None,
        )
    assert "FOLDER" in str(ei.value) or "404" in str(ei.value)


def test_create_batch_rejects_unknown_parse_mode(db: Session, storage_tmp, factory) -> None:
    tenant.set_current_company_id("co-1")
    folder = factory.folder(name="目标", prefix="QC")
    token = _upload()
    with pytest.raises(Exception) as ei:
        batch_import_service.create_batch(
            db,
            payload=BatchImportCreate(
                folder_id=folder.id,
                parse_mode="turbo",
                items=[BatchImportItemIn(filename="a.docx", upload_token=token)],
            ),
            created_by=None,
        )
    assert "parse_mode" in str(ei.value) or "PARSE_FAILED" in str(ei.value)
