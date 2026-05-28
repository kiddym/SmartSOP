"""端到端管线单测（M6.2）：parse_docx 串联 normalize→structure。"""

from __future__ import annotations

from app.parser import parse_docx
from tests.unit.parser._docx_builder import DocxBuilder, inject_header_part, styled_sop, unstyled_numbered_sop


def test_parse_docx_standard_styled() -> None:
    res = parse_docx(styled_sop(), "standard")
    assert res.parse_method == "standard"
    assert res.metadata.total_chapters >= 3
    assert res.metadata.body_start_detected_by == "first_styled_heading"
    assert any("media:" in r.placeholder for r in res.image_refs)


def test_parse_docx_smart_unstyled_produces_review() -> None:
    res = parse_docx(unstyled_numbered_sop(), "smart")
    assert res.parse_method == "smart"
    assert res.review_required >= 2
    assert len(res.detected_patterns) >= 1


def test_parse_docx_handles_vml_and_textbox_without_completeness_warnings() -> None:
    """端到端 parse_docx：含 VML 图 + 文本框 + 普通段落的合成 SOP，
    解析后 warnings 中不应出现「图片可能遗漏 / 表格可能遗漏」，
    且 image_refs 含 VML 图、章节树含文本框内文字。"""
    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("本程序适用于全公司。")
        .textbox_para("注意：操作前务必断电")
        .heading("范围", level=1)
        .vml_image_para()
        .build()
    )
    res = parse_docx(data, "standard")
    # 完整性校验：分母分子一致 → 无 completeness warning
    completeness_warns = [w for w in res.warnings if w.stage == "completeness"]
    assert completeness_warns == [], f"unexpected completeness warnings: {completeness_warns}"
    # VML 图作为 image_ref 出现（asset 阶段会落盘）
    assert any(r.placeholder.startswith("media:") for r in res.image_refs)
    # 文本框文字进入 rich_content（被挂在某个 chapter 的 content 子节点下）
    def _all_rich(nodes):  # type: ignore[no-untyped-def]
        for n in nodes:
            yield n.rich_content
            yield from _all_rich(n.children)
    all_rich = " ".join(_all_rich(res.chapters))
    assert "断电" in all_rich, f"textbox content missing from chapters: {all_rich[:200]}"


def test_parse_docx_emits_discarded_by_design_warning_for_header() -> None:
    """端到端：含 header 的 docx 应在 warnings 中出现 stage='discarded_by_design'。"""
    base = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("本程序适用于全公司。")
        .build()
    )
    data = inject_header_part(base, header_text="机密文件页眉")
    res = parse_docx(data, "standard")
    discarded = [w for w in res.warnings if w.stage == "discarded_by_design"]
    assert len(discarded) == 1, (
        f"expected 1 discarded_by_design warning, got {len(discarded)}: {res.warnings}"
    )
    assert "header1.xml" in discarded[0].message


def test_parse_docx_no_discard_warning_when_no_header() -> None:
    """没有 header/footer 的纯 body docx 不应出现 discarded_by_design warning。"""
    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("纯净文档无页眉页脚。")
        .build()
    )
    res = parse_docx(data, "standard")
    discarded = [w for w in res.warnings if w.stage == "discarded_by_design"]
    assert discarded == [], f"clean docx should have no discarded warning, got {discarded}"
