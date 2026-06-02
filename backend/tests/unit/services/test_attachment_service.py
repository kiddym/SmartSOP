"""attachment_service 单测（M9-B1）：上传 / 上限 / CRUD / 复制 / 30 天清理。"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.attachment import Attachment
from app.models.base import utcnow
from app.services import attachment_service
from tests.conftest import Factory

META = RequestMeta(ip_address="1.2.3.4", user_agent="ua", request_id="r")


def _proc(factory: Factory, **kw: object) -> object:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id, **kw)  # type: ignore[arg-type]


def _upload(db: Session, proc_id: str, data: bytes = b"hello", name: str = "a.txt") -> object:
    return attachment_service.upload_for(
        db, None, "procedure", proc_id, data, name, content_type=None, description="说明", meta=META
    )


def test_upload_success(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = attachment_service.upload_for(
        db, None, "procedure", proc.id,
        b"hello",
        "报告.pdf",
        content_type="application/pdf",
        description="x",
        meta=META,
    )
    assert att.file_name == "报告.pdf"
    assert att.mime_type == "application/pdf"
    assert att.size_bytes == 5
    assert (storage_tmp / att.storage_path).exists()


def test_upload_mime_guessed_from_name(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id, name="note.txt")
    assert att.mime_type == "text/plain"


def test_upload_single_file_too_large(
    db: Session, factory: Factory, storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(attachment_service, "MAX_FILE_BYTES", 4)
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        _upload(db, proc.id, data=b"toolong")
    assert exc.value.detail["code"] == "ATTACHMENT_LIMIT_EXCEEDED"  # type: ignore[index]


def test_upload_count_limit(
    db: Session, factory: Factory, storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(attachment_service, "MAX_COUNT", 2)
    proc = _proc(factory)
    _upload(db, proc.id)
    _upload(db, proc.id)
    with pytest.raises(HTTPException) as exc:
        _upload(db, proc.id)
    assert exc.value.detail["code"] == "ATTACHMENT_LIMIT_EXCEEDED"  # type: ignore[index]


def test_upload_total_size_limit(
    db: Session, factory: Factory, storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(attachment_service, "MAX_TOTAL_BYTES", 8)
    proc = _proc(factory)
    _upload(db, proc.id, data=b"12345")
    with pytest.raises(HTTPException) as exc:
        _upload(db, proc.id, data=b"6789")
    assert exc.value.detail["code"] == "ATTACHMENT_LIMIT_EXCEEDED"  # type: ignore[index]


def test_upload_readonly_when_published(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory, status="PUBLISHED")
    with pytest.raises(HTTPException) as exc:
        _upload(db, proc.id)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"  # type: ignore[index]


def test_upload_deprecated(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    proc.deprecated_at = utcnow()
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _upload(db, proc.id)
    assert exc.value.detail["code"] == "PROCEDURE_DEPRECATED"  # type: ignore[index]


def test_list_returns_active_ordered(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    a1 = _upload(db, proc.id, name="1.txt")
    a2 = _upload(db, proc.id, name="2.txt")
    db.commit()
    rows = attachment_service.list_for(db, None, "procedure", proc.id)
    assert [r.id for r in rows] == [a1.id, a2.id]


def test_download_works_on_published(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id, data=b"PDFDATA")
    proc.status = "PUBLISHED"  # 下载不受只读/废止限制（Q118）
    db.commit()
    data, _mime, name = attachment_service.download_for(db, None, att.id)
    assert data == b"PDFDATA"
    assert name == "a.txt"


def test_preview_whitelist_and_415(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    img = attachment_service.upload_for(
        db, None, "procedure", proc.id, b"x", "p.png", content_type="image/png", description="", meta=META
    )
    _data, mime = attachment_service.preview_for(db, None, img.id)
    assert mime == "image/png"

    txt = _upload(db, proc.id, name="x.txt")
    with pytest.raises(HTTPException) as exc:
        attachment_service.preview_for(db, None, txt.id)
    assert exc.value.status_code == 415
    assert exc.value.detail["code"] == "ATTACHMENT_NOT_PREVIEWABLE"  # type: ignore[index]


def test_update_metadata(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id)
    updated = attachment_service.update_for(db, None, att.id, description="新说明", sort_order=5, meta=META)
    assert updated.description == "新说明"
    assert updated.sort_order == 5


def test_update_readonly_when_not_draft(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id)
    proc.status = "PUBLISHED"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        attachment_service.update_for(db, None, att.id, description="x", sort_order=None, meta=META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"  # type: ignore[index]


def test_delete_soft_deletes_keeps_file(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id)
    path = storage_tmp / att.storage_path
    attachment_service.delete_for(db, None, att.id, meta=META)
    db.commit()
    assert path.exists()  # 文件保留供其他版本引用（Q114）
    assert attachment_service.list_for(db, None, "procedure", proc.id) == []


def test_copy_for_version_reuses_storage_path(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc1 = _proc(factory)
    att = _upload(db, proc1.id)
    proc2 = factory.procedure(
        proc1.folder_id, code="QC-00002", procedure_group_id=proc1.procedure_group_id, version=2
    )
    attachment_service.copy_for_version(db, proc1.id, proc2.id)
    db.commit()
    rows = attachment_service.list_for(db, None, "procedure", proc2.id)
    assert len(rows) == 1
    assert rows[0].id != att.id
    assert rows[0].storage_path == att.storage_path  # 复用，物理文件不复制


def test_orphan_cleanup_deletes_after_retention(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id)
    path = storage_tmp / att.storage_path
    attachment_service.delete_for(db, None, att.id, meta=META)
    att.deleted_at = utcnow() - timedelta(days=31)
    db.commit()

    now = utcnow()
    assert att.storage_path in attachment_service.orphan_storage_paths(
        db, retention_days=30, now=now
    )
    removed = attachment_service.delete_orphan_path(
        db, att.storage_path, retention_days=30, now=now
    )
    assert removed == 1
    assert not path.exists()
    assert (
        db.execute(select(Attachment).where(Attachment.id == att.id)).first()
        is None
    )


def test_orphan_cleanup_keeps_referenced_path(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc1 = _proc(factory)
    att = _upload(db, proc1.id)
    proc2 = factory.procedure(
        proc1.folder_id, code="QC-00002", procedure_group_id=proc1.procedure_group_id, version=2
    )
    attachment_service.copy_for_version(db, proc1.id, proc2.id)  # proc2 仍 active 引用同 path
    attachment_service.delete_for(db, None, att.id, meta=META)
    att.deleted_at = utcnow() - timedelta(days=31)
    db.commit()

    now = utcnow()
    assert att.storage_path not in attachment_service.orphan_storage_paths(
        db, retention_days=30, now=now
    )
    assert (storage_tmp / att.storage_path).exists()


def test_orphan_cleanup_skips_recent_softdelete(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc = _proc(factory)
    att = _upload(db, proc.id)
    attachment_service.delete_for(db, None, att.id, meta=META)  # deleted_at=now（<30 天）
    db.commit()
    assert attachment_service.orphan_storage_paths(db, retention_days=30, now=utcnow()) == []
