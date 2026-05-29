"""asset_service 单测（M6.3）：sha256 去重 + 直传 + 引用重建 + GC。"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.parser.utils import images
from app.services import asset_service
from tests.conftest import Factory
from tests.unit.parser._docx_builder import tiny_png


def _proc(factory: Factory):  # type: ignore[no-untyped-def]
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


def test_find_or_create_dedups_by_sha256(db: Session, factory: Factory, storage_tmp: Path) -> None:
    png = tiny_png()
    a1 = asset_service.find_or_create_asset(db, png, ext=".png")
    a2 = asset_service.find_or_create_asset(db, png, ext=".png")
    assert a1.id == a2.id  # 同字节去重
    assert a1.sha256 == images.sha256_hex(png)
    assert (storage_tmp / a1.storage_path).exists()
    assert a1.width == 8 and a1.height == 8


def test_store_from_upload_success(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    asset = asset_service.store_from_upload(db, proc.id, tiny_png(), "x.png")
    assert asset.mime_type == "image/png"
    data, mime = asset_service.get_asset(db, asset.id)
    assert mime == "image/png"
    assert len(data) > 0


def test_store_from_upload_too_large(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    big = b"\x89PNG\r\n" + b"0" * (10 * 1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc:
        asset_service.store_from_upload(db, proc.id, big, "big.png")
    assert exc.value.detail["code"] == "IMAGE_TOO_LARGE"  # type: ignore[index]


def test_store_from_upload_unsupported_format(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        asset_service.store_from_upload(db, proc.id, b"data", "x.tiff")
    assert exc.value.detail["code"] == "UNSUPPORTED_IMAGE_FORMAT"  # type: ignore[index]


def test_rebuild_references_tracks_and_releases(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    proc = _proc(factory)
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    url = asset_service.asset_url(proc.id, asset.id)
    # 图片引用嵌在节点 body（统一节点模型）
    node = factory.node(proc.id, body=f'<p><img src="{url}"></p>', sort_order=1000)
    asset_service.rebuild_references(db, proc.id)
    db.flush()
    assert asset_service.ref_count(db, asset.id) == 1

    # 移除引用 → ref_count 归零 + updated_at bump
    node.body = "<p>无图</p>"
    db.flush()
    asset_service.rebuild_references(db, proc.id)
    db.flush()
    assert asset_service.ref_count(db, asset.id) == 0


def test_gc_deletes_unreferenced_after_grace(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    path = storage_tmp / asset.storage_path
    assert path.exists()
    # 人为把 updated_at 设为 25h 前（超出 grace）
    asset.updated_at = utcnow() - timedelta(hours=25)
    db.flush()
    now = utcnow()
    candidates = asset_service.gc_candidates(db, grace_hours=24, now=now)
    assert asset.id in candidates
    deleted = asset_service.delete_asset_locked(db, asset.id, grace_hours=24, now=now)
    assert deleted is True
    assert not path.exists()


def test_gc_skips_recent_and_referenced(db: Session, factory: Factory, storage_tmp: Path) -> None:
    proc = _proc(factory)
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    # 刚创建（updated_at 新）→ 不在候选
    now = utcnow()
    assert asset.id not in asset_service.gc_candidates(db, grace_hours=24, now=now)
    # 加引用后即使过期也不删
    url = asset_service.asset_url(proc.id, asset.id)
    factory.node(proc.id, body=f'<img src="{url}">', sort_order=1000)
    asset_service.rebuild_references(db, proc.id)
    asset.updated_at = utcnow() - timedelta(hours=25)
    db.flush()
    assert asset.id not in asset_service.gc_candidates(db, grace_hours=24, now=utcnow())


def test_scan_referenced_asset_ids_reads_node_bodies(
    db: Session, factory: Factory, monkeypatch
) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)
    factory.node(proc.id, body="NODE_REF", sort_order=1000)
    factory.step(proc.id, content="STEP_REF")  # legacy row must now be ignored
    monkeypatch.setattr(asset_service, "extract_asset_ids", lambda s: {s} if s else set())
    ids = asset_service._scan_referenced_asset_ids(db, proc.id)
    assert ids == {"NODE_REF"}
