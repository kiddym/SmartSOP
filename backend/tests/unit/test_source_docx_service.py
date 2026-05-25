"""P1 源 docx：存储路径 + 模型登记 + 服务存取删。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import storage
from app.config import settings
from app.models import Base
from app.services import source_docx_service, upload_service
from tests.unit.parser._docx_builder import styled_sop


def test_source_docx_path_under_group(storage_tmp: Path) -> None:
    p = storage.source_docx_path("grp-1")
    assert p == storage_tmp / "source_docx" / "grp-1" / "source.docx"


def test_model_registered_in_metadata() -> None:
    assert "tb_procedure_source_docx" in Base.metadata.tables


def test_store_from_token_writes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "原文.docx")
    row = source_docx_service.store_from_token(db, procedure_group_id="grp-1", upload_token=up.upload_token)
    assert row is not None
    assert row.filename == "原文.docx"
    assert row.size_bytes > 0 and len(row.sha256) == 64
    assert storage.source_docx_path("grp-1").exists()


def test_store_from_token_degrades_without_token(db: Session, storage_tmp: Path) -> None:
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token=None) is None
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token="ghost") is None


def test_store_rejects_non_docx_at_boundary(
    db: Session, storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 临时文件在上传后被改成非法 docx：永久化边界再校验 → 降级跳过、不阻断导入。
    monkeypatch.setattr(upload_service, "try_read_source", lambda _t: (b"not a docx", "x.docx"))
    row = source_docx_service.store_from_token(db, procedure_group_id="grp-x", upload_token="tok")
    assert row is None
    assert not storage.source_docx_path("grp-x").exists()


def test_store_rejects_oversized_at_boundary(
    db: Session, storage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    up = upload_service.save_upload(styled_sop(), "big.docx")
    monkeypatch.setattr(settings, "upload_max_size_mb", 0)  # 收紧上限到 0，模拟超限
    row = source_docx_service.store_from_token(
        db, procedure_group_id="grp-big", upload_token=up.upload_token
    )
    assert row is None
    assert not storage.source_docx_path("grp-big").exists()


def test_store_truncates_long_filename(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "x" * 300 + ".docx")
    row = source_docx_service.store_from_token(
        db, procedure_group_id="grp-ln", upload_token=up.upload_token
    )
    assert row is not None
    assert len(row.filename) <= 255  # 截到列宽，避免 MySQL DataError


def test_delete_for_group_removes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "a.docx")
    source_docx_service.store_from_token(db, procedure_group_id="grp-9", upload_token=up.upload_token)
    assert storage.source_docx_path("grp-9").exists()
    source_docx_service.delete_for_group(db, "grp-9")
    assert not storage.source_docx_path("grp-9").exists()
