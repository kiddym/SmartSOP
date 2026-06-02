"""version_flow_service 单测（Phase 7 / §22 / §31）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.folder import Folder
from app.models.procedure import Procedure
from app.schemas.procedure import ProcedureUpdate
from app.services import procedure_service, version_flow_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.20", user_agent="pytest", request_id="r-vf")


def _leaf(factory: Factory, name: str = "叶子", prefix: str = "QC") -> Folder:
    f = factory.folder(name=name, prefix=prefix, full_path=name)
    factory.sequence(f.id)
    return f


def _deprecated_folder(factory: Factory) -> Folder:
    return factory.folder(name="废止", system=True, full_path="废止")


def _published(factory: Factory, folder: Folder, **kw: object) -> Procedure:
    return factory.procedure(folder.id, status="PUBLISHED", **kw)


# --------------------------------------------------------------------------- #
# upgrade
# --------------------------------------------------------------------------- #
def test_upgrade_forks_new_draft(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    proc = _published(factory, folder, version=1)
    factory.node(proc.id, body="<p>章A</p>", heading_level=1, sort_order=1000)
    new = version_flow_service.upgrade_version(db, proc.id, META)

    assert new.version == 2
    assert new.status == "DRAFT"
    assert new.is_current is True
    assert new.procedure_group_id == proc.procedure_group_id
    assert new.code == proc.code
    db.refresh(proc)
    assert proc.is_current is False
    assert proc.status == "ARCHIVED"
    # 内容已深拷贝
    children = version_flow_service._group_records(db, new.procedure_group_id)
    assert len(children) == 2
    from app.models.node import ProcedureNode

    cloned = list(
        db.execute(ProcedureNode.__table__.select().where(ProcedureNode.procedure_id == new.id))
    )
    assert len(cloned) == 1


def _add_attachment(db: Session, proc_id: str, *, storage_path: str) -> None:
    from app.models.attachment import Attachment

    db.add(
        Attachment(
            entity_type="procedure",
            entity_id=proc_id,
            file_name="规程.pdf",
            storage_path=storage_path,
            mime_type="application/pdf",
            size_bytes=10,
        )
    )
    db.commit()


def test_upgrade_copies_attachment_metadata(db: Session, factory: Factory) -> None:
    from app.services import attachment_service

    factory.settings()
    folder = _leaf(factory)
    proc = _published(factory, folder, version=1)
    _add_attachment(db, proc.id, storage_path="attachment/ab/orig.pdf")

    new = version_flow_service.upgrade_version(db, proc.id, META)
    db.commit()
    rows = attachment_service.list_for(db, None, "procedure", new.id)
    assert len(rows) == 1
    assert rows[0].storage_path == "attachment/ab/orig.pdf"  # 复用 storage_path


def test_rollback_inherits_target_attachments(db: Session, factory: Factory) -> None:
    from app.services import attachment_service

    factory.settings()
    folder = _leaf(factory)
    gid = "g-roll"
    v1 = factory.procedure(
        folder.id,
        code="QC-1",
        procedure_group_id=gid,
        version=1,
        status="ARCHIVED",
        is_current=False,
    )
    _add_attachment(db, v1.id, storage_path="attachment/v1/file.pdf")
    v2 = factory.procedure(
        folder.id,
        code="QC-1",
        procedure_group_id=gid,
        version=2,
        status="PUBLISHED",
    )
    _add_attachment(db, v2.id, storage_path="attachment/v2/file.pdf")

    new = version_flow_service.rollback(db, v2.id, 1, "回退原因", META)
    db.commit()
    rows = attachment_service.list_for(db, None, "procedure", new.id)
    # 继承 target(v1) 的附件，而非 current(v2) 的（Q117）
    assert [r.storage_path for r in rows] == ["attachment/v1/file.pdf"]


def test_upgrade_rejects_non_published(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    proc = factory.procedure(folder.id, status="DRAFT")
    with pytest.raises(HTTPException) as exc:
        version_flow_service.upgrade_version(db, proc.id, META)
    assert exc.value.detail["code"] == "PROCEDURE_STATUS_INVALID"


def test_upgrade_rejects_when_draft_exists(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    gid = "g-draftcase"
    proc = _published(factory, folder, version=1, procedure_group_id=gid, is_current=True)
    factory.procedure(
        folder.id, status="DRAFT", version=2, procedure_group_id=gid, is_current=False
    )
    with pytest.raises(HTTPException) as exc:
        version_flow_service.upgrade_version(db, proc.id, META)
    assert exc.value.detail["code"] == "PROCEDURE_DRAFT_EXISTS"


def test_upgrade_rejects_at_version_max(db: Session, factory: Factory) -> None:
    factory.settings(max_version_number=1)
    folder = _leaf(factory)
    proc = _published(factory, folder, version=1)
    with pytest.raises(HTTPException) as exc:
        version_flow_service.upgrade_version(db, proc.id, META)
    assert exc.value.detail["code"] == "PROCEDURE_VERSION_MAX"


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #
def test_rollback_forks_from_target(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    gid = "g-rb"
    factory.procedure(
        folder.id, name="v1", status="ARCHIVED", version=1, procedure_group_id=gid, is_current=False
    )
    cur = _published(factory, folder, name="v2", version=2, procedure_group_id=gid, is_current=True)
    new = version_flow_service.rollback(db, cur.id, 1, "回退原因", META)
    assert new.version == 3
    assert new.status == "DRAFT"
    assert new.name == "v1"  # 元字段取目标版本
    assert "回退自 v1" in new.version_update_notes
    db.refresh(cur)
    assert cur.status == "ARCHIVED"
    assert cur.is_current is False


def test_rollback_requires_reason(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    gid = "g-rb2"
    factory.procedure(
        folder.id, status="ARCHIVED", version=1, procedure_group_id=gid, is_current=False
    )
    cur = _published(factory, folder, version=2, procedure_group_id=gid, is_current=True)
    with pytest.raises(HTTPException) as exc:
        version_flow_service.rollback(db, cur.id, 1, "   ", META)
    assert exc.value.detail["code"] == "ROLLBACK_REASON_REQUIRED"


def test_rollback_target_invalid(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    cur = _published(factory, folder, version=2)
    with pytest.raises(HTTPException) as exc:
        version_flow_service.rollback(db, cur.id, 99, "reason", META)
    assert exc.value.detail["code"] == "ROLLBACK_TARGET_INVALID"


# --------------------------------------------------------------------------- #
# deprecate / restore
# --------------------------------------------------------------------------- #
def test_deprecate_moves_group_to_deprecated_folder(db: Session, factory: Factory) -> None:
    dep = _deprecated_folder(factory)
    folder = _leaf(factory)
    proc = _published(factory, folder, version=1)
    version_flow_service.deprecate(db, proc.id, "废弃原因", META)
    db.refresh(proc)
    assert proc.folder_id == dep.id
    assert proc.deprecated_from_folder_id == folder.id
    assert proc.deprecated_at is not None
    assert proc.status == "ARCHIVED"


def test_deprecate_twice_rejected(db: Session, factory: Factory) -> None:
    _deprecated_folder(factory)
    folder = _leaf(factory)
    proc = _published(factory, folder)
    version_flow_service.deprecate(db, proc.id, "r", META)
    with pytest.raises(HTTPException) as exc:
        version_flow_service.deprecate(db, proc.id, "r2", META)
    assert exc.value.detail["code"] == "PROCEDURE_DEPRECATED"


def test_restore_preview_and_restore_to_origin(db: Session, factory: Factory) -> None:
    factory.settings()
    _deprecated_folder(factory)
    folder = _leaf(factory)
    proc = _published(factory, folder, version=1)
    version_flow_service.deprecate(db, proc.id, "r", META)

    preview = version_flow_service.restore_preview(db, proc.id)
    assert preview["folder_exists"] is True
    assert preview["version_count"] == 1

    new = version_flow_service.restore(db, proc.id, "恢复原因", None, META)
    assert new.status == "DRAFT"
    assert new.version == 2
    assert new.folder_id == folder.id
    assert new.deprecated_at is None
    db.refresh(proc)
    assert proc.deprecated_at is None
    assert proc.folder_id == folder.id


def test_restore_missing_folder_requires_target(db: Session, factory: Factory) -> None:
    factory.settings()
    _deprecated_folder(factory)
    folder = _leaf(factory)
    proc = _published(factory, folder)
    version_flow_service.deprecate(db, proc.id, "r", META)
    # 软删原文件夹
    folder.is_active = False
    db.flush()
    with pytest.raises(HTTPException) as exc:
        version_flow_service.restore(db, proc.id, "恢复", None, META)
    assert exc.value.detail["code"] == "RESTORE_FOLDER_MISSING"


# --------------------------------------------------------------------------- #
# copy
# --------------------------------------------------------------------------- #
def test_copy_creates_new_group(db: Session, factory: Factory) -> None:
    src_folder = _leaf(factory, name="源", prefix="SRC")
    dst_folder = _leaf(factory, name="目标", prefix="DST")
    src = _published(factory, src_folder, name="原程序", version=3)
    factory.node(src.id, body="<p>章</p>", heading_level=1, sort_order=1000)
    new = version_flow_service.copy_procedure(db, src.id, dst_folder.id, None, META)
    assert new.procedure_group_id != src.procedure_group_id
    assert new.version == 1
    assert new.status == "DRAFT"
    assert new.name == "原程序 (副本)"
    assert new.code.startswith("DST-")


# --------------------------------------------------------------------------- #
# discard draft（procedure_service.delete_procedure 特殊路径）
# --------------------------------------------------------------------------- #
def test_discard_draft_promotes_previous_archived(db: Session, factory: Factory) -> None:
    folder = _leaf(factory)
    gid = "g-dd"
    v1 = factory.procedure(
        folder.id, version=1, status="ARCHIVED", procedure_group_id=gid, is_current=False
    )
    v2 = factory.procedure(
        folder.id, version=2, status="DRAFT", procedure_group_id=gid, is_current=True
    )
    result = procedure_service.delete_procedure(db, v2.id, "丢弃原因", META)
    assert result is not None
    assert result.deleted_id == v2.id
    assert result.new_current_id == v1.id
    assert result.new_current_version == 1
    db.refresh(v1)
    db.refresh(v2)
    assert v2.is_active is False
    assert v1.is_current is True


def test_discard_v1_draft_now_allowed(db: Session, factory: Factory) -> None:
    # P1 relaxation：v1 DRAFT is_current 现允许删除（返回 None = 204 路径）
    folder = _leaf(factory)
    proc = factory.procedure(folder.id, version=1, status="DRAFT", is_current=True)
    result = procedure_service.delete_procedure(db, proc.id, "r", META)
    assert result is None
    assert proc.is_active is False


# --------------------------------------------------------------------------- #
# deprecated 守卫
# --------------------------------------------------------------------------- #
def test_update_rejected_when_deprecated(db: Session, factory: Factory) -> None:
    _deprecated_folder(factory)
    folder = _leaf(factory)
    proc = factory.procedure(folder.id, status="DRAFT", is_current=True)
    version_flow_service.deprecate(db, proc.id, "r", META)
    db.refresh(proc)
    with pytest.raises(HTTPException) as exc:
        procedure_service.update_procedure(
            db,
            proc.id,
            ProcedureUpdate(name="x", level_of_use="reference"),
            proc.revision,
            META,
        )
    assert exc.value.detail["code"] == "PROCEDURE_DEPRECATED"


# --------------------------------------------------------------------------- #
# group delete（v1 DRAFT）
# --------------------------------------------------------------------------- #
def test_delete_group_v1_draft(db: Session, factory: Factory) -> None:
    folder = _leaf(factory)
    proc = factory.procedure(folder.id, version=1, status="DRAFT", is_current=True)
    gid = proc.procedure_group_id
    version_flow_service.delete_group(db, gid, "删除原因", META)
    remaining = version_flow_service._group_records(db, gid)
    assert remaining == []


def test_clone_tree_copies_nodes(db: Session, factory: Factory) -> None:
    from app.models.node import ProcedureNode

    folder = _leaf(factory)
    src = factory.procedure(folder.id, code="QC-1")
    dst = factory.procedure(
        folder.id,
        code="QC-1",
        procedure_group_id=src.procedure_group_id,
        version=2,
        is_current=False,
    )
    factory.node(src.id, body="<p>章</p>", heading_level=1, sort_order=1000)
    factory.node(src.id, body="<p>正文</p>", heading_level=None, kind="node", sort_order=2000)

    version_flow_service._clone_tree(db, src.id, dst.id)

    cloned = (
        db.query(ProcedureNode)
        .filter_by(procedure_id=dst.id, is_active=True)
        .order_by(ProcedureNode.sort_order)
        .all()
    )
    assert [(n.heading_level, n.body) for n in cloned] == [(1, "<p>章</p>"), (None, "<p>正文</p>")]


def test_delete_group_removes_nodes(db: Session, factory: Factory) -> None:
    from app.models.node import ProcedureNode

    folder = _leaf(factory)
    proc = factory.procedure(folder.id, version=1, status="DRAFT", is_current=True)
    factory.node(proc.id, body="<p>章</p>", heading_level=1, sort_order=1000)
    factory.node(proc.id, body="<p>正文</p>", sort_order=2000)

    version_flow_service.delete_group(db, proc.procedure_group_id, "删", META)

    assert version_flow_service._group_records(db, proc.procedure_group_id) == []
    assert db.query(ProcedureNode).filter_by(procedure_id=proc.id).count() == 0


# --------------------------------------------------------------------------- #
# 评审 C1/C2：fork 版本号取 group 最大值 + 1（防 active_code_version 撞号）
# --------------------------------------------------------------------------- #
def test_fork_version_uses_group_max_not_source(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    gid = "g-maxver"
    # current 是 v2（PUBLISHED），但 group 内已有更高的 v3（ARCHIVED）——
    # discard/delete 序列可造成此态。fork 须取 max(3)+1=4，而非 source.version+1=3。
    factory.procedure(
        folder.id, version=1, status="ARCHIVED", procedure_group_id=gid, is_current=False
    )
    cur = _published(factory, folder, version=2, procedure_group_id=gid, is_current=True)
    factory.procedure(
        folder.id, version=3, status="ARCHIVED", procedure_group_id=gid, is_current=False
    )
    new = version_flow_service.upgrade_version(db, cur.id, META)
    assert new.version == 4


def test_delete_group_rejects_multi_version(db: Session, factory: Factory) -> None:
    folder = _leaf(factory)
    gid = "g-multi"
    factory.procedure(
        folder.id, version=1, status="ARCHIVED", procedure_group_id=gid, is_current=False
    )
    factory.procedure(folder.id, version=2, status="DRAFT", procedure_group_id=gid, is_current=True)
    with pytest.raises(HTTPException) as exc:
        version_flow_service.delete_group(db, gid, "r", META)
    assert exc.value.detail["code"] == "PROCEDURE_GROUP_DELETE_FORBIDDEN"


def test_upgrade_propagates_signoff_enabled(db: Session, factory: Factory) -> None:
    factory.settings()
    folder = _leaf(factory)
    proc = _published(factory, folder, signoff_enabled=True)
    new = version_flow_service.upgrade_version(db, proc.id, META)

    assert new.signoff_enabled is True


# --------------------------------------------------------------------------- #
# archive_group / restore-from-archive
# --------------------------------------------------------------------------- #
def _archive_folder(factory: Factory) -> Folder:
    return factory.folder(name="归档", system=True, full_path="归档")


def test_archive_group_moves_to_archive_folder(db: Session, factory: Factory) -> None:
    """归档：整 group 转 ARCHIVED + folder_id 改归档 + 记原 folder。"""
    archive_folder = _archive_folder(factory)
    normal_folder = _leaf(factory, name="QC")
    proc = _published(factory, normal_folder)

    version_flow_service.archive_group(db, proc.id, "已过时不再推广", META)

    db.refresh(proc)
    assert proc.status == "ARCHIVED"
    assert proc.folder_id == archive_folder.id
    assert proc.deprecated_from_folder_id == normal_folder.id  # 复用字段记原 folder


def test_archive_group_rejects_system_folder(db: Session, factory: Factory) -> None:
    """禁止归档系统文件夹下的程序。"""
    archive_folder = _archive_folder(factory)
    proc = factory.procedure(archive_folder.id, status="ARCHIVED")

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "再次归档", META)
    assert exc.value.detail["code"] == "PROCEDURE_ARCHIVE_SYSTEM_FOLDER"


def test_archive_group_rejects_already_archived(db: Session, factory: Factory) -> None:
    """禁止归档已 ARCHIVED 的程序（无论 folder）。"""
    _archive_folder(factory)
    normal_folder = _leaf(factory, name="QC2")
    proc = factory.procedure(normal_folder.id, status="ARCHIVED")

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "归档", META)
    assert exc.value.detail["code"] == "PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED"


def test_archive_group_requires_reason(db: Session, factory: Factory) -> None:
    """归档 reason 必填。"""
    _archive_folder(factory)
    normal_folder = _leaf(factory, name="QC3")
    proc = _published(factory, normal_folder)

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "", META)
    assert exc.value.detail["code"] == "REASON_REQUIRED"


def test_restore_from_archive(db: Session, factory: Factory) -> None:
    """restore 通用：从归档恢复路径同从废止恢复（同函数、同字段）。"""
    factory.settings()
    _archive_folder(factory)
    normal_folder = _leaf(factory, name="QC4")
    proc = _published(factory, normal_folder, version=1)
    version_flow_service.archive_group(db, proc.id, "归档", META)

    new_proc = version_flow_service.restore(db, proc.id, "重新启用", None, META)

    assert new_proc.status == "DRAFT"
    assert new_proc.folder_id == normal_folder.id  # 恢复到原 folder
