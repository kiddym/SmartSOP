"""mark_service 单测（决策 §五 Q2/Q3/Q9 / editor-behavior §3）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.services import mark_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.12", user_agent="pytest", request_id="r-mk")


def _proc(factory: Factory) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


def _chapter(
    factory: Factory,
    proc_id: str,
    title: str = "章",
    parent_id: str | None = None,
    sort_order: int = 0,
) -> ProcedureChapter:
    """建一个纯标题容器章节（新模型：无 content_type / rich_content）。"""
    return factory.chapter(
        procedure_id=proc_id,
        title=title,
        parent_id=parent_id,
        sort_order=sort_order,
    )


def test_set_mark_status(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(factory, proc.id)
    mark_service.set_mark_status(db, ch.id, "step", META)
    db.refresh(ch)
    assert ch.mark_status == "step"


def test_apply_marks_chapter_to_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(factory, proc.id, title="动作")
    mark_service.set_mark_status(db, ch.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    db.refresh(ch)
    assert ch.is_active is False


def test_apply_marks_both_siblings_to_step_ok(db: Session, factory: Factory) -> None:
    """同 parent 的两个章节同批转 step 不应误判互斥（Q9 最终态校验）。"""
    proc = _proc(factory)
    parent = _chapter(factory, proc.id, title="父")
    x1 = _chapter(factory, proc.id, title="子A", parent_id=parent.id, sort_order=0)
    x2 = _chapter(factory, proc.id, title="子B", parent_id=parent.id, sort_order=1)
    mark_service.set_mark_status(db, x1.id, "step", META)
    mark_service.set_mark_status(db, x2.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 2
    steps = step_service.list_steps(db, procedure_id=proc.id, chapter_id=parent.id)
    assert [s.code for s in steps] == ["1.1", "1.2"]


def test_apply_marks_partial_sibling_conflict(db: Session, factory: Factory) -> None:
    """只标记两兄弟之一 → 应用后 parent 同时含 step 与 chapter → 拒绝。"""
    proc = _proc(factory)
    parent = _chapter(factory, proc.id, title="父")
    x1 = _chapter(factory, proc.id, title="子A", parent_id=parent.id, sort_order=0)
    _chapter(factory, proc.id, title="子B", parent_id=parent.id, sort_order=1)
    mark_service.set_mark_status(db, x1.id, "step", META)
    with pytest.raises(HTTPException) as exc:
        mark_service.apply_marks(db, proc.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_apply_marks_chapter_content_is_noop_when_no_targets(db: Session, factory: Factory) -> None:
    """当所有标记章节都已转换时，apply 返回空结果。"""
    proc = _proc(factory)
    result = mark_service.apply_marks(db, proc.id, META)
    assert result.created == []
    assert result.deleted == []


def test_apply_marks_chapter_step_with_children_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(factory, proc.id, title="父")
    _chapter(factory, proc.id, title="子", parent_id=parent.id)
    mark_service.set_mark_status(db, parent.id, "step", META)
    with pytest.raises(HTTPException) as exc:
        mark_service.apply_marks(db, proc.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_apply_marks_preserves_review_marks(db: Session, factory: Factory) -> None:
    # 评审 M1：apply-marks 不得清除 Word 智能解析留下的 'review' 标记
    proc = _proc(factory)
    # review 章节在根级；被转换的步骤在另一个父章节下（二者非同级，互斥校验不牵连）。
    review = factory.chapter(proc.id, title="待核实", sort_order=0, mark_status="review")
    parent = _chapter(factory, proc.id, title="父", sort_order=1)
    ch = _chapter(factory, proc.id, title="动作", parent_id=parent.id)
    mark_service.set_mark_status(db, ch.id, "step", META)
    mark_service.apply_marks(db, proc.id, META)
    db.refresh(review)
    assert review.is_active is True
    assert review.mark_status == "review"


def test_apply_marks_content_mark_creates_step_and_deletes_chapter(
    db: Session, factory: Factory
) -> None:
    """章节标 content → 建 kind='content' 步骤，章节软删除。"""
    proc = _proc(factory)
    a = _chapter(factory, proc.id, title="A")
    mark_service.set_mark_status(db, a.id, "content", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 1
    assert result.deleted == [a.id]
    db.refresh(a)
    assert a.is_active is False


def test_mark_chapter_as_step_creates_step_kind(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(factory, proc.id, title="其实是步骤")
    mark_service.set_mark_status(db, ch.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 1
    st = db.query(ProcedureStep).filter_by(id=result.created[0]).one()
    assert st.kind == "step" and st.title == "其实是步骤"


def test_mark_chapter_as_content_creates_content_kind(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(factory, proc.id, title="其实是正文")
    mark_service.set_mark_status(db, ch.id, "content", META)
    result = mark_service.apply_marks(db, proc.id, META)
    st = db.query(ProcedureStep).filter_by(id=result.created[0]).one()
    assert st.kind == "content" and "其实是正文" in st.content
