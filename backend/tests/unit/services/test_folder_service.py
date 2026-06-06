"""folder_service 单测（data-model §3.1 / Q246–Q252 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.schemas.folder import FolderCreate, FolderUpdate
from app.services import folder_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.7", user_agent="pytest", request_id="r-1")


pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _create(db: Session, name: str, *, parent_id: str | None = None, prefix: str = "") -> str:
    folder = folder_service.create_folder(
        db, FolderCreate(name=name, parent_id=parent_id, prefix=prefix), META
    )
    return folder.id


# --------------------------------------------------------------------------- #
# 创建：容器 vs 叶子 / full_path
# --------------------------------------------------------------------------- #
def test_create_container_has_no_prefix_or_sequence(db: Session) -> None:
    folder = folder_service.create_folder(db, FolderCreate(name="质检"), META)
    assert folder.prefix == ""
    assert folder.full_path == "质检"
    assert folder_service._get_active_sequence(db, folder.id) is None


def test_create_leaf_creates_sequence(db: Session) -> None:
    folder = folder_service.create_folder(db, FolderCreate(name="来料", prefix="QC"), META)
    seq = folder_service._get_active_sequence(db, folder.id)
    assert seq is not None
    assert seq.sequence_digits == 5
    assert seq.current_value == 0


def test_create_nested_full_path(db: Session) -> None:
    root = _create(db, "质检")
    child = folder_service.create_folder(db, FolderCreate(name="来料", parent_id=root), META)
    assert child.full_path == "质检 / 来料"


# --------------------------------------------------------------------------- #
# 名称唯一
# --------------------------------------------------------------------------- #
def test_duplicate_name_same_parent_rejected(db: Session) -> None:
    _create(db, "重名")
    with pytest.raises(HTTPException) as exc:
        _create(db, "重名")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "FOLDER_NAME_DUPLICATE"


def test_same_name_different_parent_allowed(db: Session) -> None:
    p1 = _create(db, "p1")
    p2 = _create(db, "p2")
    _create(db, "同名", parent_id=p1)
    _create(db, "同名", parent_id=p2)  # 不应抛异常


# --------------------------------------------------------------------------- #
# 前缀全局唯一 + 历史占用（Q248/Q249）
# --------------------------------------------------------------------------- #
def test_duplicate_prefix_active_folder_rejected(db: Session) -> None:
    _create(db, "leafA", prefix="QC")
    with pytest.raises(HTTPException) as exc:
        _create(db, "leafB", prefix="QC")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "FOLDER_PREFIX_DUPLICATE"


def test_prefix_occupied_by_historical_code_rejected(db: Session, factory: Factory) -> None:
    # 没有任何活跃文件夹用 ZZ，但历史 code 用过 → 永久占用
    leaf = factory.folder(name="leaf", prefix="AA", full_path="leaf")
    factory.sequence(leaf.id)
    factory.procedure(leaf.id, code="ZZ-00099")
    with pytest.raises(HTTPException) as exc:
        _create(db, "新ZZ", prefix="ZZ")
    assert exc.value.detail["code"] == "FOLDER_PREFIX_DUPLICATE"


def test_prefix_lookalike_not_falsely_matched(db: Session, factory: Factory) -> None:
    # QCD-00001 不应让 QC 判为占用（连字符锚定）
    leaf = factory.folder(name="leaf", prefix="AA", full_path="leaf")
    factory.sequence(leaf.id)
    factory.procedure(leaf.id, code="QCD-00001")
    assert folder_service.check_prefix(db, "QC") is True


# --------------------------------------------------------------------------- #
# 容器 xor 叶子（Q247）
# --------------------------------------------------------------------------- #
def test_cannot_add_subfolder_to_folder_with_procedures(db: Session, factory: Factory) -> None:
    parent = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="PP"), META)
    factory.procedure(parent.id, code="PP-00001")
    with pytest.raises(HTTPException) as exc:
        _create(db, "child", parent_id=parent.id)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "FOLDER_HAS_PROCEDURES"


# --------------------------------------------------------------------------- #
# 深度（最大 5）
# --------------------------------------------------------------------------- #
def test_depth_limit_five_levels(db: Session) -> None:
    parent: str | None = None
    for i in range(5):
        parent = _create(db, f"L{i}", parent_id=parent)
    with pytest.raises(HTTPException) as exc:
        _create(db, "L5", parent_id=parent)
    assert exc.value.detail["code"] == "FOLDER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# 移动：循环 / 深度
# --------------------------------------------------------------------------- #
def test_move_into_descendant_rejected(db: Session) -> None:
    a = _create(db, "a")
    b = _create(db, "b", parent_id=a)
    c = _create(db, "c", parent_id=b)
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, a, FolderUpdate(name="a", parent_id=c), META)
    assert exc.value.detail["code"] == "FOLDER_CYCLE_DETECTED"


def test_move_into_self_rejected(db: Session) -> None:
    a = _create(db, "a")
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, a, FolderUpdate(name="a", parent_id=a), META)
    assert exc.value.detail["code"] == "FOLDER_CYCLE_DETECTED"


def test_move_exceeding_depth_rejected(db: Session) -> None:
    # 目标链 p1/p2/p3（p3 深度 3）；被移子树 t1/t2/t3（t1 高度 2）→ 4 + 2 = 6 > 5
    p1 = _create(db, "p1")
    p2 = _create(db, "p2", parent_id=p1)
    p3 = _create(db, "p3", parent_id=p2)
    t1 = _create(db, "t1")
    t2 = _create(db, "t2", parent_id=t1)
    _create(db, "t3", parent_id=t2)
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, t1, FolderUpdate(name="t1", parent_id=p3), META)
    assert exc.value.detail["code"] == "FOLDER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# full_path 重算（改名 / 移动）
# --------------------------------------------------------------------------- #
def test_rename_recomputes_descendant_paths(db: Session) -> None:
    root = folder_service.create_folder(db, FolderCreate(name="质检"), META)
    child = folder_service.create_folder(db, FolderCreate(name="来料", parent_id=root.id), META)
    grand = folder_service.create_folder(db, FolderCreate(name="目检", parent_id=child.id), META)

    folder_service.update_folder(db, root.id, FolderUpdate(name="质检部", parent_id=None), META)

    assert child.full_path == "质检部 / 来料"
    assert grand.full_path == "质检部 / 来料 / 目检"


def test_move_recomputes_descendant_paths(db: Session) -> None:
    src = folder_service.create_folder(db, FolderCreate(name="旧根"), META)
    child = folder_service.create_folder(db, FolderCreate(name="子", parent_id=src.id), META)
    dst = folder_service.create_folder(db, FolderCreate(name="新根"), META)

    folder_service.update_folder(db, src.id, FolderUpdate(name="旧根", parent_id=dst.id), META)

    assert src.full_path == "新根 / 旧根"
    assert child.full_path == "新根 / 旧根 / 子"


# --------------------------------------------------------------------------- #
# 系统文件夹保护
# --------------------------------------------------------------------------- #
def test_system_folder_update_rejected(db: Session, factory: Factory) -> None:
    sys = factory.folder(name="废止", system=True, full_path="废止")
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, sys.id, FolderUpdate(name="改名"), META)
    assert exc.value.detail["code"] == "FOLDER_SYSTEM_PROTECTED"


def test_system_folder_delete_rejected(db: Session, factory: Factory) -> None:
    sys = factory.folder(name="废止", system=True, full_path="废止")
    with pytest.raises(HTTPException) as exc:
        folder_service.delete_folder(db, sys.id, META)
    assert exc.value.detail["code"] == "FOLDER_SYSTEM_PROTECTED"


# --------------------------------------------------------------------------- #
# 删除硬约束
# --------------------------------------------------------------------------- #
def test_delete_folder_with_children_rejected(db: Session) -> None:
    parent = _create(db, "parent")
    _create(db, "child", parent_id=parent)
    with pytest.raises(HTTPException) as exc:
        folder_service.delete_folder(db, parent, META)
    assert exc.value.detail["code"] == "FOLDER_NOT_EMPTY"


def test_delete_folder_with_procedures_rejected(db: Session, factory: Factory) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="LF"), META)
    factory.procedure(leaf.id, code="LF-00001")
    with pytest.raises(HTTPException) as exc:
        folder_service.delete_folder(db, leaf.id, META)
    assert exc.value.detail["code"] == "FOLDER_NOT_EMPTY"


def test_delete_soft_deletes_folder_and_sequence(db: Session) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf2", prefix="L2"), META)
    folder_service.delete_folder(db, leaf.id, META)
    assert leaf.is_active is False
    assert leaf.deleted_at is not None
    assert folder_service._get_active_sequence(db, leaf.id) is None


# --------------------------------------------------------------------------- #
# 批量删除（原子，Q20/Q325）
# --------------------------------------------------------------------------- #
def test_batch_delete_atomic_rolls_back_on_failure(db: Session) -> None:
    a = _create(db, "a")
    parent = _create(db, "parent")
    _create(db, "child", parent_id=parent)  # 使 parent 不可删

    result = folder_service.batch_delete(db, [a, parent], META)

    assert result.deleted_ids == []
    assert len(result.failed) == 1
    assert result.failed[0].id == parent
    assert result.failed[0].code == "FOLDER_NOT_EMPTY"
    # a 未被删除（原子）
    assert folder_service.get_folder(db, a).is_active is True


def test_batch_delete_success(db: Session) -> None:
    a = _create(db, "a")
    b = _create(db, "b")
    result = folder_service.batch_delete(db, [a, b, a], META)  # 含重复 id
    assert set(result.deleted_ids) == {a, b}
    assert result.failed == []


# --------------------------------------------------------------------------- #
# 校验 / 树
# --------------------------------------------------------------------------- #
def test_check_name_and_prefix(db: Session) -> None:
    _create(db, "exists")
    _create(db, "leafX", prefix="XX")
    assert folder_service.check_name(db, None, "exists") is False
    assert folder_service.check_name(db, None, "other") is True
    assert folder_service.check_prefix(db, "XX") is False
    assert folder_service.check_prefix(db, "YY") is True
    assert folder_service.check_prefix(db, "") is True


def test_get_tree_with_procedure_count(db: Session, factory: Factory) -> None:
    root = folder_service.create_folder(db, FolderCreate(name="r"), META)
    leaf = folder_service.create_folder(
        db, FolderCreate(name="leaf", parent_id=root.id, prefix="TR"), META
    )
    # 计数口径与程序库列表一致：仅 is_current 且非 DRAFT 计入。
    factory.procedure(leaf.id, code="TR-00001", status="PUBLISHED")  # 计入
    factory.procedure(leaf.id, code="TR-00002", status="DRAFT")  # 草稿，不计入

    tree = folder_service.get_tree(db)
    root_node = next(n for n in tree if n["id"] == root.id)
    assert root_node["procedure_count"] == 0
    assert len(root_node["children"]) == 1
    assert root_node["children"][0]["procedure_count"] == 1


def test_get_tree_procedure_count_excludes_draft(db: Session, factory: Factory) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="DR"), META)
    factory.procedure(leaf.id, code="DR-00001", status="DRAFT")

    tree = folder_service.get_tree(db)
    leaf_node = next(n for n in tree if n["id"] == leaf.id)
    # 仅有草稿的文件夹徽标计数为 0（草稿只在草稿箱可见）。
    assert leaf_node["procedure_count"] == 0


# --------------------------------------------------------------------------- #
# 更新分支：移入含程序目标 / 改前缀冲突 / 序列维护
# --------------------------------------------------------------------------- #
def test_move_into_folder_with_procedures_rejected(db: Session, factory: Factory) -> None:
    dst = folder_service.create_folder(db, FolderCreate(name="dst", prefix="DS"), META)
    factory.procedure(dst.id, code="DS-00001")
    src = folder_service.create_folder(db, FolderCreate(name="src"), META)
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, src.id, FolderUpdate(name="src", parent_id=dst.id), META)
    assert exc.value.detail["code"] == "FOLDER_HAS_PROCEDURES"


def test_update_change_prefix_to_duplicate_rejected(db: Session) -> None:
    folder_service.create_folder(db, FolderCreate(name="leafA", prefix="QC"), META)
    leaf_b = folder_service.create_folder(db, FolderCreate(name="leafB", prefix="RR"), META)
    with pytest.raises(HTTPException) as exc:
        folder_service.update_folder(db, leaf_b.id, FolderUpdate(name="leafB", prefix="QC"), META)
    assert exc.value.detail["code"] == "FOLDER_PREFIX_DUPLICATE"


def test_update_same_prefix_keeps_sequence_and_passes(db: Session) -> None:
    # 改前缀为自身现值不应触发占用校验（exclude_id 生效）
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="QC"), META)
    folder_service.update_folder(db, leaf.id, FolderUpdate(name="leaf2", prefix="QC"), META)
    assert leaf.name == "leaf2"
    assert leaf.prefix == "QC"


def test_update_container_to_leaf_creates_sequence(db: Session) -> None:
    container = folder_service.create_folder(db, FolderCreate(name="c"), META)
    assert folder_service._get_active_sequence(db, container.id) is None
    folder_service.update_folder(
        db, container.id, FolderUpdate(name="c", prefix="NEW", sequence_digits=6), META
    )
    seq = folder_service._get_active_sequence(db, container.id)
    assert seq is not None
    assert seq.sequence_digits == 6


def test_update_changes_existing_sequence_digits(db: Session) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="QC"), META)
    folder_service.update_folder(
        db, leaf.id, FolderUpdate(name="leaf", prefix="QC", sequence_digits=8), META
    )
    seq = folder_service._get_active_sequence(db, leaf.id)
    assert seq is not None
    assert seq.sequence_digits == 8


def test_leaf_to_container_deactivates_sequence(db: Session) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="QC"), META)
    assert folder_service._get_active_sequence(db, leaf.id) is not None
    folder_service.update_folder(db, leaf.id, FolderUpdate(name="leaf", prefix=""), META)
    assert folder_service._get_active_sequence(db, leaf.id) is None
    # 行仍在（软删），供往返复用
    assert folder_service._get_sequence_any(db, leaf.id) is not None


def test_container_leaf_roundtrip_reuses_sequence_without_unique_clash(db: Session) -> None:
    leaf = folder_service.create_folder(db, FolderCreate(name="leaf", prefix="QC"), META)
    seq = folder_service._get_active_sequence(db, leaf.id)
    assert seq is not None
    seq.current_value = 7
    db.flush()

    folder_service.update_folder(db, leaf.id, FolderUpdate(name="leaf", prefix=""), META)  # →容器
    folder_service.update_folder(
        db, leaf.id, FolderUpdate(name="leaf", prefix="QC2"), META
    )  # →叶子

    seq2 = folder_service._get_active_sequence(db, leaf.id)
    assert seq2 is not None
    assert seq2.current_value == 7  # 只增不重置（Q251）


def test_move_logs_move_action(db: Session) -> None:
    from app.models.audit import FolderAuditLog

    dst = _create(db, "dst")
    src = _create(db, "src")
    folder_service.update_folder(db, src, FolderUpdate(name="src", parent_id=dst), META)
    actions = [r.action for r in db.query(FolderAuditLog).all()]
    assert "move" in actions


def test_batch_delete_logs_batch_action_with_ids_count(db: Session) -> None:
    from app.models.audit import FolderAuditLog

    a = _create(db, "a")
    b = _create(db, "b")
    folder_service.batch_delete(db, [a, b], META)
    rows = db.query(FolderAuditLog).filter_by(action="batch_delete").all()
    assert len(rows) == 2
    assert all(r.new_value == {"ids": [a, b], "count": 2} for r in rows)
