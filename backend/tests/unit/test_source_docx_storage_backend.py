"""source_docx_service per-file 写经 StorageBackend（Phase 5B 收口）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services import source_docx_service, upload_service
from app.storage_backends import get_storage_backend
from tests.unit.parser._docx_builder import styled_sop


def test_store_then_exists_via_backend(db: Session, storage_tmp: Path):
    up = upload_service.save_upload(styled_sop(), "ok.docx")
    row = source_docx_service.store_from_token(
        db, procedure_group_id="pg-1", upload_token=up.upload_token
    )
    db.commit()
    assert row is not None
    assert get_storage_backend().exists(row.storage_path) is True
