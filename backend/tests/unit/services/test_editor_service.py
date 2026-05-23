"""editor_service 整批保存单测（editor-behavior §8/§17.2 / Q154-Q155）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterCreate, ChapterUpsert, StepUpsert
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
            ChapterUpsert(id="t1", content_type="chapter", title="概述", sort_order=0),
            ChapterUpsert(
                id="t2",
                parent_id="t1",
                content_type="content",
                rich_content="<p>x</p>",
                sort_order=0,
            ),
        ],
    )
    assert set(id_map) == {"t1", "t2"}
    root = chapter_service.get_chapter(db, id_map["t1"])
    child = chapter_service.get_chapter(db, id_map["t2"])
    assert root.code == "1"
    assert root.level == 1
    assert child.parent_id == id_map["t1"]  # 临时 parent_id 已映射
    assert child.level == 2
    assert child.content_type == "content"


def test_new_step_under_new_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    _, id_map = _save(
        db,
        proc,
        0,
        chapters=[ChapterUpsert(id="c1", content_type="chapter", title="操作", sort_order=0)],
        steps=[StepUpsert(id="s1", chapter_id="c1", title="启动", sort_order=0)],
    )
    step = step_service.get_step(db, id_map["s1"])
    assert step.chapter_id == id_map["c1"]
    assert step.code == "1.1"


def test_update_existing_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = chapter_service.create_chapter(db, ChapterCreate(procedure_id=proc.id, title="旧"), META)
    db.refresh(proc)
    _save(
        db,
        proc,
        proc.revision,
        chapters=[ChapterUpsert(id=ch.id, content_type="chapter", title="新标题", sort_order=0)],
    )
    db.refresh(ch)
    assert ch.title == "新标题"


def test_delete_chapter_via_save(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = chapter_service.create_chapter(db, ChapterCreate(procedure_id=proc.id, title="A"), META)
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
                ChapterUpsert(id="c1", content_type="chapter", title="父", sort_order=0),
                ChapterUpsert(
                    id="c2", parent_id="c1", content_type="chapter", title="子章", sort_order=0
                ),
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
                ChapterUpsert(id="c1", content_type="chapter", title="1", sort_order=0),
                ChapterUpsert(
                    id="c2", parent_id="c1", content_type="chapter", title="2", sort_order=0
                ),
                ChapterUpsert(
                    id="c3", parent_id="c2", content_type="chapter", title="3", sort_order=0
                ),
                ChapterUpsert(
                    id="c4", parent_id="c3", content_type="chapter", title="4", sort_order=0
                ),
            ],
        )
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


def test_save_chapter_rich_content_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as exc:
        _save(
            db,
            proc,
            0,
            chapters=[
                ChapterUpsert(id="c1", content_type="chapter", title="x", rich_content="<p>y</p>")
            ],
        )
    assert exc.value.detail["code"] == "CHAPTER_RICH_CONTENT_NOT_ALLOWED"


def test_readonly_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory, status="PUBLISHED")
    with pytest.raises(HTTPException) as exc:
        _save(db, proc, 0)
    assert exc.value.detail["code"] == "PROCEDURE_READONLY"


def test_save_procedure_persists_existing_content_type_change(
    db: Session, factory: Factory
) -> None:
    proc = _proc(factory)
    content = chapter_service.create_chapter(
        db,
        ChapterCreate(
            procedure_id=proc.id,
            content_type="content",
            rich_content="<p>系统启动条件</p>",
            sort_order=0,
        ),
        META,
    )
    db.refresh(proc)

    _save(
        db,
        proc,
        proc.revision,
        chapters=[
            ChapterUpsert(
                id=content.id,
                content_type="chapter",
                title="系统启动条件",
                rich_content="",
                skip_numbering=False,
                sort_order=0,
            ),
            ChapterUpsert(
                id="temp-child",
                parent_id=content.id,
                content_type="content",
                title="",
                rich_content="<p>系统启动条件</p>",
                skip_numbering=True,
                sort_order=0,
            ),
        ],
    )

    db.refresh(content)
    children = chapter_service.list_chapters(
        db,
        procedure_id=proc.id,
        parent_id=content.id,
        content_type=None,
        mark_status=None,
    )

    assert content.content_type == "chapter"
    assert content.rich_content == ""
    assert content.skip_numbering is False
    assert len(children) == 1
    assert children[0].content_type == "content"
    assert children[0].parent_id == content.id
    assert children[0].rich_content == "<p>系统启动条件</p>"
