"""chapter_service 单测（§19 / §47 / Q25 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterCreate, ChapterMoveIn, ChapterUpdate
from app.services import chapter_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.9", user_agent="pytest", request_id="r-c")


def _proc(factory: Factory, *, status: str = "DRAFT", is_current: bool = True) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id, status=status, is_current=is_current)


def _mk(pid: str, **kw: object) -> ChapterCreate:
    return ChapterCreate(procedure_id=pid, **kw)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 创建 + 编号 + 层级
# --------------------------------------------------------------------------- #
def test_create_root_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = chapter_service.create_chapter(db, _mk(proc.id, title="目的"), META)
    assert ch.level == 1
    assert ch.code == "1"
    db.refresh(proc)
    assert proc.revision == 1  # 结构变更 bump


def test_create_child_chapter_level_and_code(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    l1 = chapter_service.create_chapter(db, _mk(proc.id, title="一级"), META)
    l2 = chapter_service.create_chapter(db, _mk(proc.id, title="二级", parent_id=l1.id), META)
    assert l2.level == 2
    assert l2.code == "1.1"


def test_depth_exceeded_at_level_four(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    l1 = chapter_service.create_chapter(db, _mk(proc.id, title="1"), META)
    l2 = chapter_service.create_chapter(db, _mk(proc.id, title="2", parent_id=l1.id), META)
    l3 = chapter_service.create_chapter(db, _mk(proc.id, title="3", parent_id=l2.id), META)
    with pytest.raises(HTTPException) as exc:
        chapter_service.create_chapter(db, _mk(proc.id, title="4", parent_id=l3.id), META)
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# Q25 互斥
# --------------------------------------------------------------------------- #
def test_sibling_conflict_chapter_then_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = chapter_service.create_chapter(db, _mk(proc.id, title="父"), META)
    factory.step(proc.id, chapter_id=ch.id, sort_order=0)  # 先有 step
    with pytest.raises(HTTPException) as exc:
        chapter_service.create_chapter(db, _mk(proc.id, title="子章", parent_id=ch.id), META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_sibling_conflict_content_then_chapter(db: Session, factory: Factory) -> None:
    # 内容块=步骤（kind='content'），同样触发 Q25 互斥
    proc = _proc(factory)
    ch = chapter_service.create_chapter(db, _mk(proc.id, title="父"), META)
    factory.step(proc.id, chapter_id=ch.id, kind="content", content="<p>x</p>", sort_order=0)
    with pytest.raises(HTTPException) as exc:
        chapter_service.create_chapter(db, _mk(proc.id, title="子章", parent_id=ch.id), META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


# --------------------------------------------------------------------------- #
# 更新 / 跳号
# --------------------------------------------------------------------------- #
def test_update_chapter_title(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = chapter_service.create_chapter(db, _mk(proc.id, title="章"), META)
    chapter_service.update_chapter(db, ch.id, ChapterUpdate(title="新标题"), META)
    db.refresh(ch)
    assert ch.title == "新标题"


def test_toggle_skip_recomputes(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = chapter_service.create_chapter(db, _mk(proc.id, title="前言"), META)
    b = chapter_service.create_chapter(db, _mk(proc.id, title="目的"), META)
    chapter_service.toggle_skip_numbering(db, a.id, META)
    db.refresh(a)
    db.refresh(b)
    assert a.skip_numbering is True
    assert a.code == ""
    assert b.code == "1"  # 连续编号，不被 skip 占位


# --------------------------------------------------------------------------- #
# 移动
# --------------------------------------------------------------------------- #
def test_move_up_down(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = chapter_service.create_chapter(db, _mk(proc.id, title="A"), META)
    b = chapter_service.create_chapter(db, _mk(proc.id, title="B"), META)
    chapter_service.move_up(db, b.id, META)
    db.refresh(a)
    db.refresh(b)
    assert b.sort_order < a.sort_order
    assert b.code == "1"
    assert a.code == "2"


def test_move_up_at_top_is_noop(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = chapter_service.create_chapter(db, _mk(proc.id, title="A"), META)
    chapter_service.create_chapter(db, _mk(proc.id, title="B"), META)
    chapter_service.move_up(db, a.id, META)  # 已在顶部
    db.refresh(a)
    assert a.sort_order == 0


def test_move_chapter_cross_parent_recomputes_level(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    p1 = chapter_service.create_chapter(db, _mk(proc.id, title="P1"), META)
    p2 = chapter_service.create_chapter(db, _mk(proc.id, title="P2"), META)
    child = chapter_service.create_chapter(db, _mk(proc.id, title="C", parent_id=p1.id), META)
    chapter_service.move_chapter(
        db, child.id, ChapterMoveIn(target_parent_id=p2.id, target_index=0), META
    )
    db.refresh(child)
    assert child.parent_id == p2.id
    assert child.level == 2
    assert child.code == "2.1"


def test_move_into_own_descendant_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    p = chapter_service.create_chapter(db, _mk(proc.id, title="P"), META)
    c = chapter_service.create_chapter(db, _mk(proc.id, title="C", parent_id=p.id), META)
    with pytest.raises(HTTPException) as exc:
        chapter_service.move_chapter(
            db, p.id, ChapterMoveIn(target_parent_id=c.id, target_index=0), META
        )
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_move_depth_exceeded(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    # 构造 a > b（2 级子树），目标 p2 已是 L2 → 移入后达 L3+1
    a = chapter_service.create_chapter(db, _mk(proc.id, title="A"), META)
    chapter_service.create_chapter(db, _mk(proc.id, title="B", parent_id=a.id), META)
    p1 = chapter_service.create_chapter(db, _mk(proc.id, title="P1"), META)
    p2 = chapter_service.create_chapter(db, _mk(proc.id, title="P2", parent_id=p1.id), META)
    with pytest.raises(HTTPException) as exc:
        chapter_service.move_chapter(
            db, a.id, ChapterMoveIn(target_parent_id=p2.id, target_index=0), META
        )
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# 删除（递归）
# --------------------------------------------------------------------------- #
def test_delete_recursive_soft_deletes_subtree_and_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    p = chapter_service.create_chapter(db, _mk(proc.id, title="P"), META)
    c = chapter_service.create_chapter(db, _mk(proc.id, title="C", parent_id=p.id), META)
    st = factory.step(proc.id, chapter_id=c.id, sort_order=0)
    chapter_service.delete_chapter(db, p.id, META)
    db.refresh(p)
    db.refresh(c)
    db.refresh(st)
    assert p.is_active is False
    assert c.is_active is False
    assert st.is_active is False


def test_delete_renumbers_remaining_siblings(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = chapter_service.create_chapter(db, _mk(proc.id, title="A"), META)
    b = chapter_service.create_chapter(db, _mk(proc.id, title="B"), META)
    chapter_service.delete_chapter(db, a.id, META)
    db.refresh(b)
    assert b.sort_order == 0
    assert b.code == "1"


# --------------------------------------------------------------------------- #
# 只读
# --------------------------------------------------------------------------- #
def test_readonly_procedure_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory, status="PUBLISHED")
    with pytest.raises(HTTPException) as exc:
        chapter_service.create_chapter(db, _mk(proc.id, title="x"), META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"
