"""asset_service 物理 IO 经 StorageBackend（Phase 5B 收口）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services import asset_service
from app.storage_backends import get_storage_backend
from tests.unit.parser._docx_builder import tiny_png


def test_find_or_create_writes_via_backend(db: Session, storage_tmp: Path):
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    # 收口后：物理字节可经 backend.read(相对 key) 取回
    assert get_storage_backend().read(asset.storage_path) == tiny_png()


def test_get_asset_reads_via_backend(db: Session, storage_tmp: Path):
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    data, _mime = asset_service.get_asset(db, asset.id)
    assert data == tiny_png()
