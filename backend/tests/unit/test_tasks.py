"""后台清理任务单测（M6.5 / M9，§53）：临时上传清理 + asset GC + 附件清理 + scheduler 装配。"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.services import asset_service, upload_service
from app.tasks import asset_gc, cleanup_attachments, cleanup_uploads, scheduler
from tests.conftest import Factory
from tests.unit.parser._docx_builder import styled_sop, tiny_png


def test_cleanup_uploads_run_removes_expired(storage_tmp: Path) -> None:
    res = upload_service.save_upload(styled_sop(), "a.docx")
    import json

    from app import storage

    meta = storage.token_dir(res.upload_token) / "meta.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["expires_at"] = (utcnow() - timedelta(hours=1)).isoformat()
    meta.write_text(json.dumps(data), encoding="utf-8")

    summary = cleanup_uploads.run(now=utcnow())
    assert summary["removed"] == 1
    assert not storage.token_dir(res.upload_token).exists()


def test_cleanup_uploads_cli_once(storage_tmp: Path) -> None:
    assert cleanup_uploads.main(["--once"]) == 0


def test_asset_gc_run_deletes_unreferenced(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    asset.updated_at = utcnow() - timedelta(hours=25)
    db.commit()
    path = storage_tmp / asset.storage_path
    assert path.exists()

    summary = asset_gc.run(db, now=utcnow(), grace_hours=24)
    assert summary["deleted"] == 1
    assert not path.exists()


def test_asset_gc_keeps_referenced(db: Session, factory: Factory, storage_tmp: Path) -> None:
    leaf = factory.folder(name="叶", prefix="QC", full_path="叶")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    ch = factory.chapter(proc.id, content_type="chapter")
    factory.chapter(
        proc.id,
        parent_id=ch.id,
        content_type="content",
        rich_content=f'<img src="{asset_service.asset_url(proc.id, asset.id)}">',
    )
    asset_service.rebuild_references(db, proc.id)
    asset.updated_at = utcnow() - timedelta(hours=25)
    db.commit()

    summary = asset_gc.run(db, now=utcnow(), grace_hours=24)
    assert summary["deleted"] == 0
    assert (storage_tmp / asset.storage_path).exists()


def test_cleanup_attachments_run_deletes_orphan(
    db: Session, factory: Factory, storage_tmp: Path
) -> None:
    from app.deps import RequestMeta
    from app.services import attachment_service

    leaf = factory.folder(name="叶", prefix="QC", full_path="叶")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    meta = RequestMeta(ip_address="1.1.1.1", user_agent="ua", request_id="r")
    att = attachment_service.upload(
        db, proc.id, b"hello", "a.txt", content_type="text/plain", description="", meta=meta
    )
    path = storage_tmp / att.storage_path
    assert path.exists()
    attachment_service.delete(db, att.id, meta)
    att.deleted_at = utcnow() - timedelta(days=31)
    db.commit()

    summary = cleanup_attachments.run(db, now=utcnow())
    assert summary["deleted"] == 1
    assert not path.exists()


def test_cleanup_attachments_keeps_recent(db: Session, factory: Factory, storage_tmp: Path) -> None:
    from app.deps import RequestMeta
    from app.services import attachment_service

    leaf = factory.folder(name="叶", prefix="QC", full_path="叶")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    meta = RequestMeta(ip_address="1.1.1.1", user_agent="ua", request_id="r")
    att = attachment_service.upload(
        db, proc.id, b"hello", "a.txt", content_type="text/plain", description="", meta=meta
    )
    attachment_service.delete(db, att.id, meta)  # 软删但 deleted_at=now（<30 天）
    db.commit()

    summary = cleanup_attachments.run(db, now=utcnow())
    assert summary["deleted"] == 0
    assert (storage_tmp / att.storage_path).exists()


def test_scheduler_has_three_jobs() -> None:
    sched = scheduler.build_scheduler()
    job_ids = {j.id for j in sched.get_jobs()}
    assert job_ids == {"cleanup_uploads", "asset_gc", "cleanup_attachments"}
