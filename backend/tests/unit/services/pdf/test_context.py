"""pdf.context 单测（Q364）：RenderData 快照装配 + 互斥树 + 封面字段解析 + 404。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.attachment import ProcedureAttachment
from app.models.field import ProcedureField
from app.services import node_numbering
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


def test_chapter_tree_with_content_step_and_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    # 文档序建 node：L1「目的」+ 内容块；L1「操作」+ 两个 step
    factory.node(proc.id, body="<p>目的</p>", heading_level=1, kind="node", sort_order=1000)
    factory.node(proc.id, body="<p>本程序用于…</p>", heading_level=None, kind="node", sort_order=2000)
    factory.node(proc.id, body="<p>操作</p>", heading_level=1, kind="node", sort_order=3000)
    factory.node(proc.id, body="<p>启动电源</p>", heading_level=None, kind="step", sort_order=4000)
    factory.node(proc.id, body="<p>检查阀门</p>", heading_level=None, kind="step", sort_order=5000)
    node_numbering.recompute(db, proc.id)  # PDF reader 读持久化 node.code
    db.commit()

    data = context.load_render_data(db, proc.id)
    assert data.procedure.code == "QC-00001"
    assert data.procedure.folder_full_path == "根/质检"
    assert len(data.root_chapters) == 2
    purpose_node, ops_node = data.root_chapters
    assert purpose_node.title == "目的"
    assert purpose_node.code == "1"  # 内部 code 递归（render-only .0 在 sections 层）
    assert len(purpose_node.children) == 0
    # 内容块步骤在 steps 里，kind='content'
    assert len(purpose_node.steps) == 1
    assert purpose_node.steps[0].kind == "content"
    assert ops_node.children == []
    assert [s.title for s in ops_node.steps] == ["启动电源", "检查阀门"]
    assert ops_node.steps[0].code == "2.1"


def test_root_steps_only(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>根步骤</p>", heading_level=None, kind="step", sort_order=1000)
    node_numbering.recompute(db, proc.id)  # PDF reader 读持久化 node.code
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


def test_titles_derived_from_node_body(db: Session, factory: Factory) -> None:
    """B2b: load_render_data 从 ProcedureNode 取数，标题由 body 首块派生。"""
    leaf = factory.folder(name="质检", prefix="QC", full_path="质检")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-00009", name="派生标题")
    factory.node(proc.id, body="<p>目的</p>", heading_level=1, kind="node", sort_order=1000)
    factory.node(proc.id, body="<p>检查阀门</p><p>步骤正文</p>", heading_level=None,
                 kind="step", sort_order=2000)
    factory.node(proc.id, body="<p>内容块正文</p>", heading_level=None,
                 kind="node", sort_order=3000)
    node_numbering.recompute(db, proc.id)  # PDF reader 读持久化 node.code
    db.commit()

    data = context.load_render_data(db, proc.id)

    assert len(data.root_chapters) == 1
    chap = data.root_chapters[0]
    assert chap.title == "目的"
    assert chap.code == "1"
    assert chap.level == 1
    titles = [(st.kind, st.title, st.content) for st in chap.steps]
    assert titles == [
        ("step", "检查阀门", "<p>步骤正文</p>"),
        ("content", "", "<p>内容块正文</p>"),
    ]
    assert chap.steps[0].code == "1.1"


def test_nested_chapters_and_skip_numbering_from_nodes(db: Session, factory: Factory) -> None:
    """B2b: L2-under-L1 树由派生 parent_id 正确串接；skip_numbering 透传。"""
    leaf = factory.folder(name="质检", prefix="QC", full_path="质检")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-00010", name="嵌套")
    # 文档序：L1 职责 → L2 质量部 → 其下 step 归口 → L1 附录(skip)
    factory.node(proc.id, body="<p>职责</p>", heading_level=1, kind="node", sort_order=1000)
    factory.node(proc.id, body="<p>质量部</p>", heading_level=2, kind="node", sort_order=2000)
    factory.node(proc.id, body="<p>归口</p><p>x</p>", heading_level=None, kind="step", sort_order=3000)
    factory.node(proc.id, body="<p>附录</p>", heading_level=1, kind="node",
                 skip_numbering=True, sort_order=4000)
    node_numbering.recompute(db, proc.id)  # PDF reader 读持久化 node.code
    db.commit()

    data = context.load_render_data(db, proc.id)

    assert [c.title for c in data.root_chapters] == ["职责", "附录"]
    appendix = data.root_chapters[1]
    assert appendix.skip_numbering is True
    assert appendix.code == ""  # skip → 不编号，透传到快照
    sub = data.root_chapters[0].children
    assert [c.title for c in sub] == ["质量部"]
    assert sub[0].level == 2
    assert sub[0].code == "1.1"
    assert sub[0].steps[0].title == "归口"  # 二级章节下的 step


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
