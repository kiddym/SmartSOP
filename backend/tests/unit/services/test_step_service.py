"""step_service 单测（§40 / §47 / Q25 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterCreate, StepCreate, StepMoveIn, StepUpdate
from app.services import chapter_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.10", user_agent="pytest", request_id="r-s")


def _proc(factory: Factory, *, status: str = "DRAFT") -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id, status=status)


def _chapter(db: Session, pid: str, title: str = "操作", parent_id: str | None = None):
    return chapter_service.create_chapter(
        db, ChapterCreate(procedure_id=pid, title=title, parent_id=parent_id), META
    )


def _sc(pid: str, **kw: object) -> StepCreate:
    return StepCreate(procedure_id=pid, **kw)  # type: ignore[arg-type]


def test_create_step_under_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    st = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="启动"), META)
    assert st.code == "1.1"
    assert st.input_schema["type"] == "COMMON"
    db.refresh(proc)
    assert proc.revision >= 2  # 章节 + 步骤各 bump


def test_create_root_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    st = step_service.create_step(db, _sc(proc.id, chapter_id=None, title="根步骤"), META)
    assert st.code == "1"


def test_step_sibling_conflict_with_chapter_children(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id)
    _chapter(db, proc.id, title="子章", parent_id=parent.id)  # parent 已有 chapter 子节点
    with pytest.raises(HTTPException) as exc:
        step_service.create_step(db, _sc(proc.id, chapter_id=parent.id), META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_step_and_content_coexist_in_chapter(db: Session, factory: Factory) -> None:
    # 新模型 Q25：步骤与内容块（kind='content'）可在同一章节下共存交替
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    s1 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="步骤一"), META)
    c1 = step_service.create_step(
        db, _sc(proc.id, chapter_id=ch.id, kind="content", content="<p>说明</p>"), META
    )
    s2 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="步骤二"), META)
    db.refresh(s1)
    db.refresh(c1)
    db.refresh(s2)
    assert c1.kind == "content"
    # 内容块不参与编号；步骤连续编号
    assert s1.code == "1.1"
    assert c1.code == ""
    assert s2.code == "1.2"


def test_invalid_input_schema_type(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    with pytest.raises(HTTPException) as exc:
        step_service.create_step(
            db, _sc(proc.id, chapter_id=ch.id, input_schema={"type": "BOGUS"}), META
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "VALIDATION_FAILED"


def test_update_step_fields(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    st = step_service.create_step(
        db,
        _sc(proc.id, chapter_id=ch.id, content="<p>高压</p>", input_schema={"type": "WARNING"}),
        META,
    )
    step_service.update_step(
        db,
        st.id,
        StepUpdate(
            title="改名",
            content="<p>高温</p>",
            input_schema={"type": "CHECK", "pass_label": "通过"},
        ),
        META,
    )
    db.refresh(st)
    assert st.title == "改名"
    assert st.input_schema["type"] == "CHECK"
    assert st.content == "<p>高温</p>"


def test_step_move_up_down(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    s1 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="一"), META)
    s2 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="二"), META)
    step_service.move_up(db, s2.id, META)
    db.refresh(s1)
    db.refresh(s2)
    assert s2.code == "1.1"
    assert s1.code == "1.2"


def test_step_move_cross_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    c1 = _chapter(db, proc.id, title="A")
    c2 = _chapter(db, proc.id, title="B")
    st = step_service.create_step(db, _sc(proc.id, chapter_id=c1.id), META)
    step_service.move_step(db, st.id, StepMoveIn(target_chapter_id=c2.id, target_index=0), META)
    db.refresh(st)
    assert st.chapter_id == c2.id
    assert st.code == "2.1"


def test_step_toggle_skip(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    s1 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id), META)
    s2 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id), META)
    step_service.toggle_skip_numbering(db, s1.id, META)
    db.refresh(s1)
    db.refresh(s2)
    assert s1.code == ""
    assert s2.code == "1.1"  # skip 不占位


def test_delete_step_renumbers(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    s1 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id), META)
    s2 = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id), META)
    step_service.delete_step(db, s1.id, META)
    db.refresh(s2)
    assert s2.is_active is True
    assert s2.sort_order == 0
    assert s2.code == "1.1"


def test_readonly_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory, status="PUBLISHED")
    with pytest.raises(HTTPException) as exc:
        step_service.create_step(db, _sc(proc.id, chapter_id=None), META)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_create_step_accepts_warning_type(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    st = step_service.create_step(
        db,
        _sc(proc.id, chapter_id=ch.id, content="<p>高温危险</p>", input_schema={"type": "WARNING"}),
        META,
    )
    assert st.input_schema["type"] == "WARNING"


def test_create_content_step_skips_input_schema_validation(db: Session, factory: Factory) -> None:
    """kind='content' 时 input_schema={} 合法（内容块无表单），不应触发校验。"""
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    st = step_service.create_step(
        db,
        _sc(proc.id, chapter_id=ch.id, kind="content", content="<p>说明</p>", input_schema={}),
        META,
    )
    assert st.kind == "content"
    assert st.input_schema == {}


def test_update_step_to_content_skips_input_schema_validation(db: Session, factory: Factory) -> None:
    """step→content 的字段切换：input_schema={} 应被接受。"""
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    st = step_service.create_step(db, _sc(proc.id, chapter_id=ch.id, title="原步骤"), META)
    step_service.update_step(
        db,
        st.id,
        StepUpdate(kind="content", title="", content="<p>内容</p>", input_schema={}),
        META,
    )
    db.refresh(st)
    assert st.kind == "content"
    assert st.input_schema == {}
