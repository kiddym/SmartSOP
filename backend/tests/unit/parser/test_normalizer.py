"""Normalizer 块流单测（M6.1）：顺序保真 + 内联图 + 表格 + 粗体比例。"""

from __future__ import annotations

from app.parser import normalizer, synonyms
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import (
    DocxBuilder,
    styled_sop,
    unstyled_numbered_sop,
)


def _normalize(data: bytes) -> normalizer.NormalizedDoc:
    return normalizer.normalize(
        DocxPackage(data), synonyms=synonyms.load_default_synonyms(), style_overrides={}
    )


def test_block_stream_preserves_order_and_kinds() -> None:
    nd = _normalize(styled_sop())
    kinds = [b.kind for b in nd.blocks]
    assert "paragraph" in kinds
    assert "table" in kinds
    # source_index 单调递增（顺序保真）
    idxs = [b.source_index for b in nd.blocks]
    assert idxs == sorted(idxs)


def test_styled_heading_block_has_level_and_text() -> None:
    nd = _normalize(styled_sop())
    purpose = next(b for b in nd.blocks if b.text.strip() == "目的")
    assert purpose.style_level == 1
    assert purpose.kind == "paragraph"


def test_inline_image_kept_in_single_paragraph_block() -> None:
    # Q206：文字 + 内联图 + 文字 → 一个 content 节点
    nd = _normalize(styled_sop())
    blk = next(b for b in nd.blocks if "流程见图" in b.text)
    assert "所示。" in blk.text  # 同一段
    assert len(blk.images) == 1
    assert "<img" in blk.html
    assert blk.html.startswith("<p")


def test_table_block_serialized_as_html() -> None:
    nd = _normalize(styled_sop())
    tbl = next(b for b in nd.blocks if b.kind == "table")
    assert tbl.html.startswith("<table")
    assert "记录表" in tbl.html
    assert "<td" in tbl.html


def test_total_image_and_table_counts() -> None:
    nd = _normalize(styled_sop())
    assert nd.total_image_count >= 1
    assert nd.total_table_count == 1


def test_bold_ratio_and_text_for_unstyled() -> None:
    nd = _normalize(unstyled_numbered_sop())
    blk = next(b for b in nd.blocks if b.text.strip() == "1 目的")
    assert blk.bold_ratio == 1.0
    body = next(b for b in nd.blocks if b.text.strip() == "规定记录控制。")
    assert body.bold_ratio == 0.0


def test_merged_table_rowspan_colspan_and_cell_image() -> None:
    data = DocxBuilder().merged_table_with_image().build()
    nd = _normalize(data)
    tbl = next(b for b in nd.blocks if b.kind == "table")
    assert 'colspan="2"' in tbl.html
    assert 'rowspan="2"' in tbl.html
    assert "<img" in tbl.html  # 表内嵌图
    assert len(tbl.images) >= 1


def test_html_escapes_special_chars() -> None:
    data = DocxBuilder().para("a < b & c > d").build()
    nd = _normalize(data)
    blk = next(b for b in nd.blocks if b.kind == "paragraph" and b.text)
    assert "&lt;" in blk.html
    assert "&amp;" in blk.html


def test_vml_imagedata_extracted_as_image_ref() -> None:
    """v:imagedata（VML 老格式图）应当被 _emit_images 抽取，不再静默丢失。"""
    data = DocxBuilder().vml_image_para().build()
    nd = _normalize(data)
    img_blocks = [b for b in nd.blocks if b.images]
    assert len(img_blocks) == 1, f"expected 1 paragraph with image, got {len(img_blocks)}"
    img = img_blocks[0].images[0]
    assert img.rid  # rid 不为空
    assert img.data and len(img.data) > 0  # 媒体字节读到了
    assert img.ext in (".png", ".jpg", ".jpeg")
