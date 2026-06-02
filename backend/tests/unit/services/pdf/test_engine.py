"""pdf.engine 端到端单测（Q360/Q361/Q362）：四区段 + 页码体系 + 收敛 + layout 契约。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.services import node_numbering, pdf
from app.services.pdf import context
from app.services.pdf.document import to_roman
from app.services.pdf.engine import compute_layout, render_pdf
from tests.conftest import Factory


def _rich_proc(db: Session, factory: Factory):
    leaf = factory.folder(name="质检", prefix="QC", full_path="根/质检")
    factory.sequence(leaf.id)
    proc = factory.procedure(
        leaf.id, code="QC-00001", name="启动 SOP", status="PUBLISHED", version=2
    )
    proc.version_change_log = [
        {
            "version": 2,
            "change_type": "publish",
            "changed_at": "2026-05-20T10:00:00Z",
            "description": "发布 v2",
        },
        {
            "version": 1,
            "change_type": "create",
            "changed_at": "2026-05-19T10:00:00Z",
            "description": "创建",
        },
    ]
    proc.version_update_notes = "本次新增启动前检查"
    # 文档序建 node：L1「目的」+ 内容块；L1「操作」+ 两个 step（透传 input_schema）
    factory.node(proc.id, body="<p>目的</p>", heading_level=1, kind="node", sort_order=1000)
    factory.node(
        proc.id,
        body="<p>本程序用于规范启动流程。</p>",
        heading_level=None,
        kind="node",
        sort_order=2000,
    )
    factory.node(proc.id, body="<p>操作</p>", heading_level=1, kind="node", sort_order=3000)
    factory.node(
        proc.id,
        body="<p>启动电源</p>",
        heading_level=None,
        kind="step",
        input_schema={"type": "CHECK"},
        sort_order=4000,
    )
    factory.node(
        proc.id,
        body="<p>检查阀门</p>",
        heading_level=None,
        kind="step",
        input_schema={"type": "NUMBER", "unit": "MPa", "min": 0, "max": 10},
        sort_order=5000,
    )
    db.add(
        Attachment(
            entity_type="procedure",
            entity_id=proc.id,
            file_name="图纸.pdf",
            storage_path="/x/a",
            mime_type="application/pdf",
            size_bytes=2048,
            sort_order=0,
        )
    )
    node_numbering.recompute(db, proc.id)  # PDF reader 读持久化 node.code
    db.commit()
    return proc


def test_to_roman() -> None:
    assert to_roman(1) == "i"
    assert to_roman(4) == "iv"
    assert to_roman(13) == "xiii"
    assert to_roman(0) == ""


def test_full_document_layout(db: Session, factory: Factory) -> None:
    proc = _rich_proc(db, factory)
    data = context.load_render_data(db, proc.id)
    result = render_pdf(data)

    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.pdf_bytes.rstrip().endswith(b"%%EOF")
    lo = result.layout
    assert lo.total_pages >= 4  # 封面 + TOC + 修订 + 正文 ≥ 4
    assert lo.cover_pages == 1
    assert lo.front_pages >= 2  # TOC + 修订
    assert lo.content_pages >= 1
    # 区段起页
    assert lo.section_starts["cover"] == 1
    assert lo.section_starts["toc"] == 2
    assert "revision" in lo.section_starts
    assert "content" in lo.section_starts
    # TOC 仅 2 个 L1 chapter（content 不进），display_page 为正文阿拉伯
    assert len(lo.toc_entries) == 2
    codes = {e.code for e in lo.toc_entries}
    assert codes == {"1.0", "2.0"}  # L1 渲染 .0（Q305）
    assert all(e.display_page.isdigit() for e in lo.toc_entries)
    # 元素 → 物理页
    assert len(lo.chapters) == 2
    assert len(lo.steps) == 2
    # 附件区段（虚拟章节，无用户「附件」章 → attachments_page 落在正文）
    assert lo.attachments_page is not None
    # 页码体系（§6.1）：封面无页码、前置罗马、正文阿拉伯
    assert len(lo.page_labels) == lo.total_pages
    assert lo.page_labels[0] == ""  # 封面
    assert lo.page_labels[1] == "i"  # 第一张前置页
    content_start = lo.section_starts["content"]
    assert lo.page_labels[content_start - 1] == "1"  # 正文首页阿拉伯 1


def test_layout_is_deterministic_and_converged(db: Session, factory: Factory) -> None:
    proc = _rich_proc(db, factory)
    data = context.load_render_data(db, proc.id)
    a = compute_layout(data)
    b = compute_layout(data)
    assert a == b  # 收敛 + 确定性
    # download 与 layout 同引擎：页码一致
    dl = render_pdf(data)
    assert dl.layout == a


def test_empty_procedure(db: Session, factory: Factory) -> None:
    leaf = factory.folder(name="空", prefix="QC", full_path="空")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id, code="QC-00002", name="空程序")
    db.commit()
    data = context.load_render_data(db, proc.id)
    result = render_pdf(data)
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.layout.toc_entries == []
    assert result.layout.attachments_page is None


def test_generate_pdf_filename(db: Session, factory: Factory) -> None:
    proc = _rich_proc(db, factory)
    _bytes, _layout, filename = pdf.generate_pdf(db, proc.id)
    assert filename == "QC-00001_Rev2.pdf"


def test_debug_payload(db: Session, factory: Factory) -> None:
    proc = _rich_proc(db, factory)
    _bytes, layout_out, _fn = pdf.generate_pdf(db, proc.id, debug=True)
    assert layout_out.debug is not None
    assert "chapters" in layout_out.debug
