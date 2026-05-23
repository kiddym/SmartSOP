"""正文起点判定单测（M6.1，§25.4 / Q191 取代 Q37）。"""

from __future__ import annotations

from app.parser import body_start, normalizer, synonyms
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import (
    DocxBuilder,
    empty_sop,
    manual_toc_sop,
    styled_sop,
    synonym_sop,
)


def _norm(data: bytes) -> normalizer.NormalizedDoc:
    return normalizer.normalize(
        DocxPackage(data), synonyms=synonyms.load_default_synonyms(), style_overrides={}
    )


def test_first_styled_heading_skips_cover_and_toc() -> None:
    nd = _norm(styled_sop())
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    assert nd.blocks[idx].text.strip() == "目的"


def test_synonym_heading_is_body_start() -> None:
    nd = _norm(synonym_sop())
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    assert nd.blocks[idx].text.strip() == "目的"


def test_toc_field_end_fallback_when_no_styled_heading() -> None:
    # 有 TOC 域、之后是零样式段落（无样式标题）→ 走 toc_field_end
    data = (
        DocxBuilder()
        .para("封面", center=True)
        .toc(["1 目的\t1"])
        .para("1 目的", bold=True)
        .para("正文。")
        .build()
    )
    nd = _norm(data)
    assert nd.toc_field_end_index is not None
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "toc_field_end"
    assert nd.blocks[idx].text.strip() == "1 目的"


def test_heuristic_heading_when_provided() -> None:
    data = DocxBuilder().para("封面").para("1 目的", bold=True).para("正文").build()
    nd = _norm(data)
    target = next(b for b in nd.blocks if b.text.strip() == "1 目的")
    idx, source = body_start.find_body_start(
        nd.blocks, toc_field_end=None, heuristic_heading_indices=[target.source_index]
    )
    assert source == "heuristic_heading"
    assert idx == target.source_index


def test_cover_skip_fallback_for_headingless_doc() -> None:
    nd = _norm(empty_sop())
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=None)
    assert source == "cover_skip"
    assert nd.blocks[idx].text.strip().startswith("这是一段")


def test_method_c_skips_manual_toc_area() -> None:
    """方案C：手动目录区（连续样式标题）被跳过，正文从首个"标题后接内容"的块开始。"""
    nd = _norm(manual_toc_sop())
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    body_block = nd.blocks[idx]
    # 正文起始块本身是"目的"
    assert body_block.text.strip() == "目的"
    # 正文起始块之后、在下一个样式标题之前，存在非标题内容块
    subsequent = [b for b in nd.blocks if b.source_index > body_block.source_index]
    first_content = next((b for b in subsequent if b.style_level is None and b.text.strip()), None)
    assert first_content is not None
    assert first_content.text.strip() == "本程序规定了碘吸附器定期试验要求。"


def test_method_c_fallback_when_all_headings_have_no_content() -> None:
    """方案C兜底：文档全为连续样式标题（无正文段），退回首个样式标题，不崩溃。"""
    data = (
        DocxBuilder()
        .styled_heading("目的", "章节标题")
        .styled_heading("范围", "章节标题")
        .styled_heading("程序", "章节标题")
        .build()
    )
    nd = _norm(data)
    idx, source = body_start.find_body_start(nd.blocks, toc_field_end=nd.toc_field_end_index)
    assert source == "first_styled_heading"
    assert nd.blocks[idx].text.strip() == "目的"
