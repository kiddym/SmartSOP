"""Normalizer 块流单测（M6.1）：顺序保真 + 内联图 + 表格 + 粗体比例。"""

from __future__ import annotations

import io

from app.parser import normalizer, synonyms
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import (
    DocxBuilder,
    inject_header_part,
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


def test_sdt_inside_txbx_content_is_hoisted() -> None:
    """txbxContent 内的 <w:sdt> 包裹段落应被展开并 hoist 为独立块，与顶层 body 一致。"""
    data = DocxBuilder().textbox_with_sdt_para("SDT 内的注意框").build()
    nd = _normalize(data)
    texts = [b.text for b in nd.blocks if b.kind == "paragraph"]
    assert "SDT 内的注意框" in [t.strip() for t in texts], (
        f"sdt-wrapped textbox paragraph missing from blocks: {texts}"
    )


def test_raw_paragraph_count_populated_in_normalized_doc() -> None:
    """normalize 应填充 raw_paragraph_count = body 内全部 <w:p> 计数（含 sdt 展开 + txbx 内）。"""
    data = (
        DocxBuilder()
        .para("段一")
        .heading("段二", level=1)
        .textbox_para("文本框内段三")  # 计入 raw_paragraph_count（txbx 内的 w:p 也是）
        .para("段四")
        .build()
    )
    nd = _normalize(data)
    # raw 应当 ≥ kept；当前 normalize 1:1 应当相等
    kept = sum(1 for b in nd.blocks if b.kind == "paragraph")
    assert nd.raw_paragraph_count >= kept >= 4
    assert nd.raw_paragraph_count == kept, (
        f"raw={nd.raw_paragraph_count} kept={kept} should be 1:1 with current normalize()"
    )


def test_nested_textbox_image_attributed_only_to_innermost_block() -> None:
    """嵌套 txbx：内层 txbx 内的图只能归最内层 paragraph block，不能被外层 txbx 段落双计。

    场景：outer_p[txbx_A[p(outer), p[txbx_B[p(inner + 图)]]]]。
    预期：image_refs 仅含 1 条记录；总图数 == 1；外层 txbx_A 内的两段都没有图；
          最内层段落（含 inner 文字的那段）拥有该图。
    """
    data = (
        DocxBuilder()
        .nested_textbox_with_image_para(
            outer_text="外层文字", inner_text="内层文字"
        )
        .build()
    )
    nd = _normalize(data)
    para_blocks = [b for b in nd.blocks if b.kind == "paragraph"]
    # 总图数 == 1（防双计）
    assert nd.total_image_count == 1, f"total_image_count={nd.total_image_count}, blocks={[(b.text[:20], len(b.images)) for b in para_blocks]}"
    # 内层段落（含「内层文字」）拥有这张图
    inner = next((b for b in para_blocks if "内层文字" in b.text), None)
    assert inner is not None, "innermost paragraph missing"
    assert len(inner.images) == 1, f"innermost should own the image, got {len(inner.images)}"
    # 外层 txbx_A 内的两段（含「外层文字」段 + 包裹 inner 的空文字段）images 列表均为空
    for b in para_blocks:
        if b is inner:
            continue
        assert len(b.images) == 0, f"block text={b.text!r} should have 0 images, got {len(b.images)}"


def test_discarded_parts_detects_non_empty_header() -> None:
    """DocxPackage.discarded_parts() 应识别注入的非空 header1.xml。"""
    base = DocxBuilder().para("正文段").build()
    no_header = DocxPackage(base)
    assert no_header.discarded_parts() == []

    with_header = DocxPackage(inject_header_part(base, header_text="页眉测试"))
    parts = with_header.discarded_parts()
    assert parts == ["word/header1.xml"], f"unexpected discarded parts: {parts}"


def test_discarded_parts_ignores_empty_header_stub() -> None:
    """空 header（无 <w:p>）不触发——避免噪音 warning。"""
    import zipfile

    base = DocxBuilder().para("正文段").build()
    empty_header = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
    in_buf = io.BytesIO(base)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin, zipfile.ZipFile(
        out_buf, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.namelist():
            zout.writestr(item, zin.read(item))
        zout.writestr("word/header1.xml", empty_header)
    pkg = DocxPackage(out_buf.getvalue())
    assert pkg.discarded_parts() == [], "empty header should not trigger discard warning"


def test_formula_inserts_inline_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().formula_para(before="见公式", after="所示").build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "见公式" in b.text)
    assert '<span class="sop-ph" data-ph="formula">[公式]</span>' in para.html
    assert para.html.index("见公式") < para.html.index("data-ph=\"formula\"") < para.html.index("所示")
    assert para.placeholder_count == 1
    assert para.raw_placeholder_count == 1


def test_formula_independent_raw_count() -> None:
    """独立扫描计数：oMathPara 直接子 + 裸 oMath 各算一处，无双计。"""
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().formula_para().formula_para().build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    total_raw = sum(b.raw_placeholder_count for b in nd.blocks)
    total_inserted = sum(b.placeholder_count for b in nd.blocks)
    assert total_raw == 2 and total_inserted == 2


def test_count_raw_placeholders_nested_omath_counts_outermost_only() -> None:
    from lxml import etree
    from app.parser.normalizer import _count_raw_placeholders
    from app.parser.utils.opc import qn
    # <w:p><m:oMathPara><m:oMath><m:oMath/></m:oMath></m:oMathPara></w:p>
    p = etree.Element(qn("w:p"))
    omathpara = etree.SubElement(p, qn("m:oMathPara"))
    omath = etree.SubElement(omathpara, qn("m:oMath"))
    etree.SubElement(omath, qn("m:oMath"))  # 嵌套子公式
    assert _count_raw_placeholders(p) == 1

    # 裸嵌套：<w:p><m:oMath><m:oMath/></m:oMath></w:p>
    p2 = etree.Element(qn("w:p"))
    o_outer = etree.SubElement(p2, qn("m:oMath"))
    etree.SubElement(o_outer, qn("m:oMath"))
    assert _count_raw_placeholders(p2) == 1


def test_chart_inserts_block_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().chart_para().build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "sop-ph" in b.html)
    assert 'data-ph="chart"' in para.html
    assert "[图表]" in para.html
    assert para.placeholder_count == 1 and para.raw_placeholder_count == 1


def test_multiple_graphics_one_run_insert_per_graphic() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().two_charts_one_run().build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "sop-ph" in b.html)
    assert para.html.count('data-ph="chart"') == 2
    assert para.placeholder_count == 2
    assert para.raw_placeholder_count == 2


def test_smartart_without_fallback_inserts_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().smartart_para(with_fallback=False).build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and "sop-ph" in b.html)
    assert 'data-ph="smartart"' in para.html
    assert para.placeholder_count == 1 and para.raw_placeholder_count == 1


def test_smartart_with_fallback_uses_image_not_placeholder() -> None:
    from tests.unit.parser._docx_builder import DocxBuilder
    from app.parser.normalizer import normalize
    from app.parser.utils.opc import DocxPackage
    data = DocxBuilder().smartart_para(with_fallback=True).build()
    nd = normalize(DocxPackage(data), synonyms={}, style_overrides={})
    para = next(b for b in nd.blocks if b.kind == "paragraph" and (b.images or "sop-ph" in b.html))
    assert para.images, "应抽到 fallback 图"
    assert "sop-ph" not in para.html
    assert para.placeholder_count == 0 and para.raw_placeholder_count == 0
