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


def test_textbox_content_extracted_as_block() -> None:
    """文本框（v:textbox > w:txbxContent）内的段落应作为独立 IR Block 抽出。"""
    data = (
        DocxBuilder()
        .para("外层段落 A")
        .textbox_para("注意：高压电气设备")
        .para("外层段落 B")
        .build()
    )
    nd = _normalize(data)
    texts = [b.text.strip() for b in nd.blocks if b.kind == "paragraph"]
    assert "外层段落 A" in texts
    assert "外层段落 B" in texts
    assert "注意：高压电气设备" in texts, f"textbox text missing from blocks: {texts}"


def test_textbox_image_attributed_to_inner_block_not_outer() -> None:
    """txbx 内的图应归属内层 block，外层段落 images 列表为空（防双计）。"""
    data = DocxBuilder().textbox_with_image_para("内图测试").build()
    nd = _normalize(data)
    para_blocks = [b for b in nd.blocks if b.kind == "paragraph"]
    # 应该有 2 个段落 block：外层（无图无字）+ 内层（含字含图）
    inner = next((b for b in para_blocks if "内图测试" in b.text), None)
    assert inner is not None, "inner textbox paragraph missing"
    assert len(inner.images) == 1, f"inner block should own the image, got {len(inner.images)}"
    # 外层段落不应再持有同一张图
    outer = next((b for b in para_blocks if b is not inner and not b.text.strip()), None)
    if outer is not None:
        assert len(outer.images) == 0, "outer paragraph must not double-count txbx image"
    # 全文图总数 == 1
    assert nd.total_image_count == 1


def test_raw_image_count_includes_vml_imagedata() -> None:
    """raw_image_count 应将 v:imagedata 计入分母，与 _emit_images 的抽取范围对齐。"""
    data = DocxBuilder().vml_image_para().build()
    nd = _normalize(data)
    blk = next(b for b in nd.blocks if b.images)
    assert blk.raw_image_count == 1
    assert len(blk.images) == blk.raw_image_count  # 分母分子一致 → C001 pass


def test_raw_image_count_excludes_txbx_blips_on_outer_paragraph() -> None:
    """外层段落的 raw_image_count 不应包含 txbx 内部图（避免与内层 block 重复计数）。"""
    data = DocxBuilder().textbox_with_image_para("内图测试").build()
    nd = _normalize(data)
    para_blocks = [b for b in nd.blocks if b.kind == "paragraph"]
    outer = next(b for b in para_blocks if not b.text.strip())
    inner = next(b for b in para_blocks if "内图测试" in b.text)
    assert outer.raw_image_count == 0
    assert inner.raw_image_count == 1
    assert len(inner.images) == 1


def test_textbox_inside_toc_field_inherits_is_toc_field() -> None:
    """文本框出现在 TOC 字段域内时，hoisted 子块也应被标 is_toc_field=True，
    防止 TOC 内的文本框内容漏过 body_blocks 过滤。"""
    from lxml import etree as _et

    _W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _V_NS = "urn:schemas-microsoft-com:vml"

    builder = DocxBuilder()

    # --- 段落 1: TOC 域 begin + instrText(TOC) + separate ---
    p_begin = builder.doc.add_paragraph()
    r1 = p_begin.add_run()
    fb = _et.SubElement(r1._r, "{%s}fldChar" % _W_NS)
    fb.set("{%s}fldCharType" % _W_NS, "begin")
    r2 = p_begin.add_run()
    instr = _et.SubElement(r2._r, "{%s}instrText" % _W_NS)
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = ' TOC \\o "1-3" '
    r3 = p_begin.add_run()
    sep = _et.SubElement(r3._r, "{%s}fldChar" % _W_NS)
    sep.set("{%s}fldCharType" % _W_NS, "separate")

    # --- 段落 2: 处于 TOC 域内的 textbox 段落（用 lxml 直接构造，避免 python-docx 重置）---
    p_txbx = builder.doc.add_paragraph()
    run_txbx = p_txbx.add_run()
    pict = _et.SubElement(run_txbx._r, "{%s}pict" % _W_NS)
    shape = _et.SubElement(pict, "{%s}shape" % _V_NS, attrib={"style": "width:120pt;height:30pt"})
    tbx = _et.SubElement(shape, "{%s}textbox" % _V_NS)
    tcontent = _et.SubElement(tbx, "{%s}txbxContent" % _W_NS)
    inner_p = _et.SubElement(tcontent, "{%s}p" % _W_NS)
    inner_r = _et.SubElement(inner_p, "{%s}r" % _W_NS)
    inner_t = _et.SubElement(inner_r, "{%s}t" % _W_NS)
    inner_t.text = "TOC 内的注意框"

    # --- 段落 3: TOC 域 end ---
    p_end = builder.doc.add_paragraph()
    re = p_end.add_run()
    fe = _et.SubElement(re._r, "{%s}fldChar" % _W_NS)
    fe.set("{%s}fldCharType" % _W_NS, "end")

    nd = _normalize(builder.build())

    # hoisted 子块应继承 is_toc_field=True
    inner_blocks = [b for b in nd.blocks if "TOC 内的注意框" in b.text]
    assert len(inner_blocks) == 1, f"expected 1 hoisted textbox block, got {len(inner_blocks)}"
    assert inner_blocks[0].is_toc_field is True, (
        "hoisted textbox block inside TOC field domain should inherit is_toc_field=True"
    )
