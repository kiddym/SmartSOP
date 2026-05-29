"""procedure_service 单测（api-specification §5.2 / data-model §3.3 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.field import ProcedureField
from app.models.folder import Folder
from app.schemas.procedure import (
    BatchMoveIn,
    ProcedureCreate,
    ProcedureUpdate,
    TransitionIn,
)
from app.services import procedure_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.7", user_agent="pytest", request_id="r-1")


def _leaf(factory: Factory, *, prefix: str = "QC", name: str = "叶子") -> Folder:
    folder = factory.folder(name=name, prefix=prefix, full_path=name)
    factory.sequence(folder.id)
    return folder


def _create(db: Session, folder_id: str, *, name: str = "启动 SOP", level: str = "continuous"):
    return procedure_service.create_procedure(
        db,
        ProcedureCreate(folder_id=folder_id, name=name, level_of_use=level),
        META,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# 创建 + 编码生成
# --------------------------------------------------------------------------- #
def test_create_generates_code_and_skeleton(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    proc = _create(db, leaf.id)
    assert proc.code == "QC-00001"
    assert proc.version == 1
    assert proc.is_current is True
    assert proc.status == "DRAFT"
    assert proc.revision == 0
    assert proc.procedure_group_id
    assert proc.version_change_log[0]["change_type"] == "create"


def test_create_increments_sequence(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    p1 = _create(db, leaf.id, name="一")
    p2 = _create(db, leaf.id, name="二")
    assert p1.code == "QC-00001"
    assert p2.code == "QC-00002"
    assert p1.procedure_group_id != p2.procedure_group_id


def test_create_in_container_rejected(db: Session, factory: Factory) -> None:
    parent = factory.folder(name="容器", prefix="", full_path="容器")
    factory.folder(name="子", parent_id=parent.id, full_path="容器 / 子")  # 使 parent 成容器
    with pytest.raises(HTTPException) as exc:
        _create(db, parent.id)
    assert exc.value.detail["code"] == "PROCEDURE_FOLDER_REQUIRED"


def test_create_in_system_folder_rejected(db: Session, factory: Factory) -> None:
    sysf = factory.folder(name="废止", prefix="", system=True, full_path="废止")
    factory.sequence(sysf.id)
    with pytest.raises(HTTPException) as exc:
        _create(db, sysf.id)
    assert exc.value.detail["code"] == "PROCEDURE_FOLDER_REQUIRED"


def test_create_in_folder_without_prefix_rejected(db: Session, factory: Factory) -> None:
    folder = factory.folder(name="无前缀", prefix="", full_path="无前缀")
    with pytest.raises(HTTPException) as exc:
        _create(db, folder.id)
    assert exc.value.detail["code"] == "PROCEDURE_FOLDER_REQUIRED"


def test_create_in_missing_folder_rejected(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        _create(db, "nonexistent")
    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# 更新 + 乐观锁
# --------------------------------------------------------------------------- #
def test_update_applies_fields_and_bumps_revision(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    updated = procedure_service.update_procedure(
        db,
        proc.id,
        ProcedureUpdate(name="新名", level_of_use="reference", risk_level=3),
        expected_revision=0,
        meta=META,
    )
    assert updated.name == "新名"
    assert updated.risk_level == 3
    assert updated.revision == 1


def test_update_revision_mismatch_conflicts(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.update_procedure(
            db,
            proc.id,
            ProcedureUpdate(name="x", level_of_use="reference"),
            expected_revision=99,
            meta=META,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "VERSION_CONFLICT"


def test_update_published_is_readonly(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    procedure_service.transition(db, proc.id, TransitionIn(status="PUBLISHED"), 0, META)
    with pytest.raises(HTTPException) as exc:
        procedure_service.update_procedure(
            db, proc.id, ProcedureUpdate(name="x", level_of_use="reference"), 1, META
        )
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_update_non_current_is_readonly(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    old = factory.procedure(leaf.id, is_current=False, status="ARCHIVED", code="QC-00099")
    with pytest.raises(HTTPException) as exc:
        procedure_service.update_procedure(
            db, old.id, ProcedureUpdate(name="x", level_of_use="reference"), 0, META
        )
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


# --------------------------------------------------------------------------- #
# 状态机
# --------------------------------------------------------------------------- #
def test_transition_publish_then_archive(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    published = procedure_service.transition(db, proc.id, TransitionIn(status="PUBLISHED"), 0, META)
    assert published.status == "PUBLISHED"
    assert published.revision == 1
    assert any(e["change_type"] == "publish" for e in published.version_change_log)

    archived = procedure_service.transition(db, proc.id, TransitionIn(status="ARCHIVED"), 1, META)
    assert archived.status == "ARCHIVED"
    assert archived.archived_at is not None


def test_transition_illegal_rejected(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(db, proc.id, TransitionIn(status="ARCHIVED"), 0, META)
    assert exc.value.detail["code"] == "PROCEDURE_STATUS_INVALID"


def test_transition_v2_publish_requires_notes(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    v2 = factory.procedure(leaf.id, version=2, status="DRAFT", is_current=True, code="QC-00002")
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(db, v2.id, TransitionIn(status="PUBLISHED"), 0, META)
    assert exc.value.detail["code"] == "VERSION_UPDATE_NOTES_REQUIRED"


def test_transition_revision_mismatch_conflicts(db: Session, factory: Factory) -> None:
    proc = _create(db, _leaf(factory).id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(db, proc.id, TransitionIn(status="PUBLISHED"), 99, META)
    assert exc.value.detail["code"] == "VERSION_CONFLICT"


# --------------------------------------------------------------------------- #
# 删除
# --------------------------------------------------------------------------- #
def test_delete_v1_draft_current_succeeds(db: Session, factory: Factory) -> None:
    # 纯草稿（v1 DRAFT is_current）：P1 relaxation 允许删除（返回 None = 204 路径）
    proc = _create(db, _leaf(factory).id)
    result = procedure_service.delete_procedure(db, proc.id, "原因", META)
    assert result is None
    assert proc.is_active is False


def test_delete_non_current_soft_deletes(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    old = factory.procedure(leaf.id, is_current=False, status="ARCHIVED", code="QC-00033")
    procedure_service.delete_procedure(db, old.id, "清理历史版本", META)
    assert old.is_active is False
    assert old.deleted_at is not None


# --------------------------------------------------------------------------- #
# 批量删除 / 批量移动（原子）
# --------------------------------------------------------------------------- #
def test_batch_delete_atomic_on_failure(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    old = factory.procedure(leaf.id, is_current=False, code="QC-00050")
    cur = _create(db, leaf.id)  # is_current → 不可删
    result = procedure_service.batch_delete(db, [old.id, cur.id], "r", META)
    assert result.deleted_ids == []
    assert result.failed[0].code == "PROCEDURE_IS_CURRENT"
    assert procedure_service._get(db, old.id).is_active is True


def test_batch_delete_success(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    a = factory.procedure(leaf.id, is_current=False, code="QC-a")
    b = factory.procedure(leaf.id, is_current=False, code="QC-b")
    result = procedure_service.batch_delete(db, [a.id, b.id], "r", META)
    assert set(result.deleted_ids) == {a.id, b.id}
    assert result.failed == []


def test_batch_move_changes_folder_keeps_code(db: Session, factory: Factory) -> None:
    src = _leaf(factory, prefix="SR", name="src")
    dst = _leaf(factory, prefix="DS", name="dst")
    proc = _create(db, src.id)
    assert proc.code == "SR-00001"
    result = procedure_service.batch_move(
        db, BatchMoveIn(ids=[proc.id], target_folder_id=dst.id), META
    )
    assert result.moved_ids == [proc.id]
    assert proc.folder_id == dst.id
    assert proc.code == "SR-00001"  # code 不变（Q22）


def test_batch_move_to_container_rejected(db: Session, factory: Factory) -> None:
    parent = factory.folder(name="容器", prefix="", full_path="容器")
    factory.folder(name="子", parent_id=parent.id, full_path="容器 / 子")
    proc = _create(db, _leaf(factory).id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.batch_move(
            db, BatchMoveIn(ids=[proc.id], target_folder_id=parent.id), META
        )
    assert exc.value.detail["code"] == "PROCEDURE_FOLDER_REQUIRED"


def test_batch_move_atomic_on_missing_id(db: Session, factory: Factory) -> None:
    dst = _leaf(factory, prefix="DS", name="dst")
    src = _leaf(factory, prefix="SR", name="src")
    proc = _create(db, src.id)
    result = procedure_service.batch_move(
        db, BatchMoveIn(ids=[proc.id, "missing"], target_folder_id=dst.id), META
    )
    assert result.moved_ids == []
    assert result.failed[0].id == "missing"
    assert proc.folder_id == src.id  # 原子：未移动


# --------------------------------------------------------------------------- #
# 列表 / 库 / 详情
# --------------------------------------------------------------------------- #
def test_list_filters_and_derived_fields(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    _create(db, leaf.id, name="alpha")
    items, total = procedure_service.list_procedures(
        db, page=1, page_size=20, sort="-updated_at", search=None, folder_id=leaf.id, status=None
    )
    assert total == 1
    assert items[0].folder_full_path == leaf.full_path
    assert items[0].version_count_in_group == 1


def test_list_search_ignores_folder_id_and_covers_name(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    _create(db, leaf.id, name="温度控制")
    _create(db, leaf.id, name="压力测试")
    items, total = procedure_service.list_procedures(
        db,
        page=1,
        page_size=20,
        sort="-updated_at",
        search="温度",
        folder_id="other-folder-id",  # search 时应被忽略
        status=None,
    )
    assert total == 1
    assert "温度" in items[0].name


def test_list_search_still_applies_status(db: Session, factory: Factory) -> None:
    # search 仅忽略 folder_id（Q278），status 过滤仍生效
    leaf = _leaf(factory)
    _create(db, leaf.id, name="温度草稿")  # DRAFT
    pub = _create(db, leaf.id, name="温度发布")
    procedure_service.transition(db, pub.id, TransitionIn(status="PUBLISHED"), 0, META)
    items, total = procedure_service.list_procedures(
        db,
        page=1,
        page_size=20,
        sort="-updated_at",
        search="温度",
        folder_id=None,
        status="PUBLISHED",
    )
    assert total == 1
    assert items[0].status == "PUBLISHED"


def test_library_search_covers_code(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory, prefix="QC")
    pub = _create(db, leaf.id, name="已发布")
    procedure_service.transition(db, pub.id, TransitionIn(status="PUBLISHED"), 0, META)
    items, total = procedure_service.list_library(
        db, page=1, page_size=20, sort="-updated_at", search="QC-00001", folder_id=None
    )
    assert total == 1
    assert items[0].code == "QC-00001"


def test_get_detail_missing_raises_not_found(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        procedure_service.get_detail(db, "missing")
    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "NOT_FOUND"


def test_library_only_published_current(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    _create(db, leaf.id, name="草稿")
    pub = _create(db, leaf.id, name="已发布")
    procedure_service.transition(db, pub.id, TransitionIn(status="PUBLISHED"), 0, META)
    items, total = procedure_service.list_library(
        db, page=1, page_size=20, sort="-updated_at", search=None, folder_id=None
    )
    assert total == 1
    assert items[0].status == "PUBLISHED"


def test_get_detail_returns_meta_fields_empty_nested(db: Session, factory: Factory) -> None:
    leaf = _leaf(factory)
    proc = _create(db, leaf.id)
    db.add(ProcedureField(name="风险类别", key="risk_cat", field_type="select", status="active"))
    db.flush()

    detail = procedure_service.get_detail(db, proc.id)
    assert detail.procedure.id == proc.id
    assert detail.procedure.folder_full_path == leaf.full_path
    assert any(f.key == "risk_cat" for f in detail.fields)


def test_publish_blocked_by_review_node(db: Session, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", version=1, is_current=True)
    factory.node(proc.id, body="<p>x</p>", heading_level=1, mark_status="review", sort_order=1000)
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(
            db, proc.id, TransitionIn(status="PUBLISHED"), proc.revision, META
        )
    assert exc.value.detail["code"] == "REVIEW_PENDING"


def test_update_procedure_persists_signoff_enabled(db: Session, factory: Factory) -> None:
    from app.schemas.procedure import ProcedureUpdate

    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", is_current=True)
    procedure_service.update_procedure(
        db,
        proc.id,
        ProcedureUpdate(name="N", level_of_use="reference", signoff_enabled=True),
        proc.revision,
        META,
    )
    db.refresh(proc)
    assert proc.signoff_enabled is True
