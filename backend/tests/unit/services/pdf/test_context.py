"""pdf.context 单测（Q364）：RenderData 快照装配 + 互斥树 + 封面字段解析 + 404。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.attachment import ProcedureAttachment
from app.models.field import ProcedureField
from app.services import numbering_service
from app.services.pdf import context
from tests.conftest import Factory


def _proc(factory: Factory):
    leaf = factory.folder(name="质检", prefix="QC", full_path="根/质检")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id, code="QC-00001", name="启动 SOP")


def test_not_found_raises_procedure_not_found(db: Session, factory: Factory) -> None:
    with pytest.raises(HTTPException) as exc:
        context.load_render_data(db, "no-such-id")
    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "PROCEDURE_NOT_FOUND"


def test_chapter_tree_with_content_and_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    # L1 章节「目的」含一个 content 子节点
    purpose = factory.chapter(proc.id, title="目的", level=1, sort_order=0)
    factory.chapter(
        proc.id,
        title="",
        parent_id=purpose.id,
        content_type="content",
        level=2,
        sort_order=0,
        rich_content="<p>本程序用于…</p>",
    )
    # L1 章节「操作」含两个 step（与 content 互斥）
    ops = factory.chapter(proc.id, title="操作", level=1, sort_order=1)
    factory.step(proc.id, chapter_id=ops.id, title="启动电源", sort_order=0)
    factory.step(proc.id, chapter_id=ops.id, title="检查阀门", sort_order=1)
    numbering_service.recompute(db, proc.id)
    db.commit()

    data = context.load_render_data(db, proc.id)
    assert data.procedure.code == "QC-00001"
    assert data.procedure.folder_full_path == "根/质检"
    assert len(data.root_chapters) == 2
    purpose_node, ops_node = data.root_chapters
    assert purpose_node.title == "目的"
    assert purpose_node.code == "1"  # 内部 code 递归（render-only .0 在 sections 层）
    assert len(purpose_node.children) == 1
    assert purpose_node.children[0].content_type == "content"
    assert purpose_node.steps == []
    assert ops_node.children == []
    assert [s.title for s in ops_node.steps] == ["启动电源", "检查阀门"]
    assert ops_node.steps[0].code == "2.1"


def test_root_steps_only(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    factory.step(proc.id, chapter_id=None, title="根步骤", sort_order=0)
    numbering_service.recompute(db, proc.id)
    db.commit()
    data = context.load_render_data(db, proc.id)
    assert data.root_chapters == []
    assert [s.title for s in data.root_steps] == ["根步骤"]
    assert data.root_steps[0].code == "1"


def test_attachments_loaded_sorted(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    for i, name in enumerate(["b.pdf", "a.png"]):
        db.add(
            ProcedureAttachment(
                procedure_id=proc.id,
                file_name=name,
                storage_path=f"/x/{name}",
                mime_type="application/octet-stream",
                size_bytes=1024 * (i + 1),
                description="" if i else "首图",
                sort_order=i,
            )
        )
    db.commit()
    data = context.load_render_data(db, proc.id)
    assert [a.file_name for a in data.attachments] == ["b.pdf", "a.png"]
    assert data.attachments[0].size_bytes == 1024


def test_cover_fields_resolved_and_empty_skipped(db: Session, factory: Factory) -> None:
    leaf = factory.folder(name="质检", prefix="QC", full_path="质检")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-00001")
    proc.custom_values = {"dept": "维修部", "grade": "high", "blank": ""}
    db.add(
        ProcedureField(
            name="部门",
            key="dept",
            field_type="text",
            show_on_cover=True,
            sort_order=0,
            status="active",
        )
    )
    db.add(
        ProcedureField(
            name="等级",
            key="grade",
            field_type="select",
            show_on_cover=True,
            sort_order=1,
            status="active",
            options=[{"value": "low", "label": "低"}, {"value": "high", "label": "高"}],
        )
    )
    db.add(  # 空值字段不渲染
        ProcedureField(
            name="空",
            key="blank",
            field_type="text",
            show_on_cover=True,
            sort_order=2,
            status="active",
        )
    )
    db.add(  # 未勾上封面的字段不进
        ProcedureField(
            name="隐藏",
            key="hidden",
            field_type="text",
            show_on_cover=False,
            sort_order=3,
            status="active",
        )
    )
    db.commit()
    data = context.load_render_data(db, proc.id)
    rendered = {(f.name, f.display_value) for f in data.cover_fields}
    assert ("部门", "维修部") in rendered
    assert ("等级", "高") in rendered  # select 映射 label
    assert all(f.key != "blank" for f in data.cover_fields)
    assert all(f.key != "hidden" for f in data.cover_fields)
