"""editor_service 整批保存单测（editor-behavior §8/§17.2 / Q154-Q155）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterUpsert, StepUpsert
from app.schemas.procedure import ProcedureSaveIn
from app.services import chapter_service, editor_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.13", user_agent="pytest", request_id="r-ed")


def _proc(factory: Factory, *, status: str = "DRAFT") -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id, status=status, level_of_use="continuous")


def _save(db: Session, proc: Procedure, rev: int, **kw: object) -> tuple[Procedure, dict[str, str]]:
    payload = ProcedureSaveIn(name=proc.name, level_of_use="continuous", **kw)  # type: ignore[arg-type]
    return editor_service.save_procedure(db, proc.id, payload, rev, META)


def test_meta_only_save_bumps_revision(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    payload = ProcedureSaveIn(name="新名", level_of_use="reference", description="描述")
    saved, id_map = editor_service.save_procedure(db, proc.id, payload, 0, META)
    assert saved.name == "新名"
    assert saved.revision == 1
    assert id_map == {}


def test_wrong_revision_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        _save(db, proc, 99)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "VERSION_CONFLICT"


def test_create_new_chapters_with_temp_ids(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    _, id_map = _save(
        db,
        proc,
        0,
        chapters=[
            ChapterUpsert(id="t1", title="概述", sort_order=0),
            ChapterUpsert(id="t2", parent_id="t1", title="子章节", sort_order=0),
        ],
    )
    assert set(id_map) == {"t1", "t2"}
    root = chapter_service.get_chapter(db, id_map["t1"])
    child = chapter_service.get_chapter(db, id_map["t2"])
    assert root.code == "1"
    assert root.level == 1
    assert child.parent_id == id_map["t1"]  # 临时 parent_id 已映射
    assert child.level == 2


def test_new_step_under_new_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    _, id_map = _save(
        db,
        proc,
        0,
        chapters=[ChapterUpsert(id="c1", title="操作", sort_order=0)],
        steps=[StepUpsert(id="s1", chapter_id="c1", title="启动", sort_order=0)],
    )
    step = step_service.get_step(db, id_map["s1"])
    assert step.chapter_id == id_map["c1"]
    assert step.code == "1.1"


def test_update_existing_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="旧")
    db.refresh(proc)
    _save(
        db,
        proc,
        proc.revision,
        chapters=[ChapterUpsert(id=ch.id, title="新标题", sort_order=0)],
    )
    db.refresh(ch)
    assert ch.title == "新标题"


def test_delete_chapter_via_save(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A")
    db.refresh(proc)
    _save(db, proc, proc.revision, deleted_chapter_ids=[a.id])
    db.refresh(a)
    assert a.is_active is False


def test_save_q25_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        _save(
            db,
            proc,
            0,
            chapters=[
                ChapterUpsert(id="c1", title="父", sort_order=0),
                ChapterUpsert(id="c2", parent_id="c1", title="子章", sort_order=0),
            ],
            steps=[StepUpsert(id="s1", chapter_id="c1", title="步骤", sort_order=0)],
        )
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_save_depth_exceeded(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        _save(
            db,
            proc,
            0,
            chapters=[
                ChapterUpsert(id="c1", title="1", sort_order=0),
                ChapterUpsert(id="c2", parent_id="c1", title="2", sort_order=0),
                ChapterUpsert(id="c3", parent_id="c2", title="3", sort_order=0),
                ChapterUpsert(id="c4", parent_id="c3", title="4", sort_order=0),
            ],
        )
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


def test_content_block_step_saved_correctly(db: Session, factory: Factory) -> None:
    """内容块（kind='content'）作为步骤保存，title/input_schema/attachment_marks 清空。"""
    proc = _proc(factory)
    _, id_map = _save(
        db,
        proc,
        0,
        chapters=[ChapterUpsert(id="c1", title="操作", sort_order=0)],
        steps=[
            StepUpsert(
                id="cb1",
                chapter_id="c1",
                kind="content",
                content="<p>系统启动条件</p>",
                sort_order=0,
            )
        ],
    )
    assert "cb1" in id_map
    st = step_service.get_step(db, id_map["cb1"])
    assert st.kind == "content"
    assert st.content == "<p>系统启动条件</p>"
    assert st.title == ""
    assert st.input_schema == {}
    assert st.attachment_marks == []


def test_readonly_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory, status="PUBLISHED")
    with pytest.raises(HTTPException) as exc:
        _save(db, proc, 0)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_save_procedure_persists_chapter_and_content_step(
    db: Session, factory: Factory
) -> None:
    """章节 + 内容块步骤保存后可正确读取。"""
    proc = _proc(factory)

    _, id_map = _save(
        db,
        proc,
        0,
        chapters=[
            ChapterUpsert(
                id="c-root",
                title="系统启动条件",
                skip_numbering=False,
                sort_order=0,
            ),
        ],
        steps=[
            StepUpsert(
                id="cb-child",
                chapter_id="c-root",
                kind="content",
                content="<p>系统启动条件</p>",
                skip_numbering=True,
                sort_order=0,
            ),
        ],
    )

    db.refresh(proc)
    root = chapter_service.get_chapter(db, id_map["c-root"])
    content_step = step_service.get_step(db, id_map["cb-child"])

    assert root.title == "系统启动条件"
    assert root.skip_numbering is False
    assert content_step.chapter_id == id_map["c-root"]
    assert content_step.kind == "content"
    assert content_step.content == "<p>系统启动条件</p>"
    assert content_step.skip_numbering is True


def test_step_and_content_coexist_under_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    _, id_map = _save(
        db, proc, 0,
        chapters=[ChapterUpsert(id="c1", title="操作", sort_order=0)],
        steps=[
            StepUpsert(id="s1", chapter_id="c1", title="做X", kind="step", sort_order=0),
            StepUpsert(id="c2", chapter_id="c1", content="<p>注</p>", kind="content", sort_order=1),
            StepUpsert(id="s2", chapter_id="c1", title="做Y", kind="step", sort_order=2),
        ],
    )
    assert set(id_map) == {"c1", "s1", "c2", "s2"}


def test_chapter_with_subchapter_cannot_hold_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException):  # SIBLING_TYPE_CONFLICT
        _save(
            db, proc, 0,
            chapters=[
                ChapterUpsert(id="c1", title="父", sort_order=0),
                ChapterUpsert(id="c2", parent_id="c1", title="子", sort_order=0),
            ],
            steps=[StepUpsert(id="s1", chapter_id="c1", title="混入", kind="step", sort_order=1)],
        )
