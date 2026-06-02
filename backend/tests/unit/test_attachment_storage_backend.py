"""attachment_service 物理 IO 经 StorageBackend（Phase 5B 收口）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.services import attachment_service
from app.storage_backends import get_storage_backend
from tests.conftest import Factory


def test_upload_then_download_via_backend(db: Session, factory: Factory, storage_tmp: Path):
    leaf = factory.folder(name="叶", prefix="QC", full_path="叶")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    meta = RequestMeta(ip_address="1.1.1.1", user_agent="ua", request_id="r")
    att = attachment_service.upload_for(
        db, None, "procedure", proc.id, b"hello", "a.txt", content_type="text/plain", description="", meta=meta
    )
    assert get_storage_backend().read(att.storage_path) == b"hello"
    data, _mime, _name = attachment_service.download_for(db, None, att.id)
    assert data == b"hello"
