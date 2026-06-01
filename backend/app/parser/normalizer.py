"""Stage 1 — DocxNormalizer：按 XML child order 把 body 摊平为 IR 块流。

修复 DPMS 真实丢失点（移植蓝本 §三）：段内多图收集为 list（非首图即 return）、
区分 inline/anchor、表内嵌图、嵌套表递归、vMerge 真实纵向跨度（双 pass）、
SDT 递归展开。**不读 header*/footer***（确认无需页眉页脚，§9.2）。
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from lxml import etree

from app.parser import styles as styles_mod
from app.parser.ir import Block, ImageRef, NormalizedDoc
from app.parser.utils.opc import DocxPackage, local, qn

_OFF_VALUES = {"0", "false", "off", "none"}
_BLOCK_TAGS = {"p", "tbl"}


@dataclass
class _Ctx:
    pkg: DocxPackage
    style_index: styles_mod.StyleIndex
    synonyms: dict[str, int]
    style_overrides: dict[str, int]


class _FieldTracker:
    """跨段落跟踪 fldChar 字段嵌套，识别 TOC 域范围与闭合位置。"""

    def __init__(self) -> None:
        self._open: list[bool] = []  # 每层开放字段：是否为 TOC
        self.toc_end_index: int | None = None

    def scan(self, para: etree._Element, block_index: int) -> bool:
        """扫描段落内 fldChar/instrText，返回该段是否处于 TOC 域内。"""
        was_in_toc = any(self._open)
        toc_here = was_in_toc
        for el in para.iter():
            tag = local(el.tag)
            if tag == "fldChar":
                ftype = el.get(qn("w:fldCharType"))
                if ftype == "begin":
                    self._open.append(False)
                elif ftype == "end" and self._open:
                    was_toc = self._open.pop()
                    if was_toc:
                        self.toc_end_index = block_index
                        toc_here = True
            elif tag == "instrText":
                if (el.text or "").upper().find("TOC") >= 0 and self._open:
                    self._open[-1] = True
                    toc_here = True
        return toc_here or any(self._open)


# --------------------------------------------------------------------------- #
# run / 段落序列化
# --------------------------------------------------------------------------- #
def _toggle_on(rpr: etree._Element | None, tag: str) -> bool:
    if rpr is None:
        return False
    el = rpr.find(qn(tag))
    if el is None:
        return False
    val = el.get(qn("w:val"))
    return val is None or val.lower() not in _OFF_VALUES


def _font_pt(rpr: etree._Element | None) -> float | None:
    if rpr is None:
        return None
    sz = rpr.find(qn("w:sz"))
    if sz is None:
        return None
    val = sz.get(qn("w:val"))
    try:
        return int(val) / 2 if val is not None else None
    except ValueError:
        return None


def _belongs_to(child: etree._Element, ancestor: etree._Element) -> bool:
    """child 是否属于 ancestor 的子树，且中间无 w:txbxContent 阻断。

    这是 _emit_images / _count_raw_images 的统一归属判定：
    blip/imagedata 与当前 emit 容器（run 或段落根）之间若隔着 txbxContent，
    说明它属于嵌套 textbox 的内层 paragraph，应由那一层的 emit 独立持有，
    外层不应越界把它收入囊中。这一形式天然处理多层嵌套（任何深度的 txbx
    边界都阻断归属），取代了原 _is_inside_txbx 的"近端"双调用启发式。
    """
    cur = child.getparent()
    while cur is not None and cur is not ancestor:
        if local(cur.tag) == "txbxContent":
            return False
        cur = cur.getparent()
    return cur is ancestor


def _count_raw_images(el: etree._Element) -> int:
    """与 _emit_images 同口径的原始图源计数：a:blip + v:imagedata，按归属判定（_belongs_to）。

    供 emit_paragraph / emit_table 写入 Block.raw_image_count，让 C001 完整性校验
    的分母覆盖 VML 老格式图。归属规则：blip/vimg 与 el 之间不能隔 txbxContent
    边界——隔了就归更深的内层 paragraph 自行计数，外层不重复。这一形式同时
    覆盖多层嵌套文本框（每层 txbx 都构成归属边界）。
    """
    n = 0
    for blip in el.iter(qn("a:blip")):
        if _belongs_to(blip, el):
            n += 1
    for vimg in el.iter(qn("v:imagedata")):
        if _belongs_to(vimg, el):
            n += 1
    return n


def _has_math_ancestor(el: etree._Element, stop: etree._Element) -> bool:
    cur = el.getparent()
    while cur is not None and cur is not stop:
        if local(cur.tag) in ("oMath", "oMathPara"):
            return True
        cur = cur.getparent()
    return False


def _count_raw_placeholders(el: etree._Element) -> int:
    """独立统计 el 内应占位的源元素数（供 C007，与插入路径独立）。

    = 最外层 math 容器数（oMathPara + 父非 oMathPara 的 oMath）
      + 无可用位图的 diagram/chart graphic 数（其所属 <w:r> 内无 a:blip/v:imagedata）。
    """
    n = 0
    for _m in el.iter(qn("m:oMathPara")):
        n += 1
    for m in el.iter(qn("m:oMath")):
        if not _has_math_ancestor(m, el):
            n += 1
    for gd in el.iter(qn("a:graphicData")):
        uri = gd.get("uri") or ""
        if not _is_diagram_or_chart(uri):
            continue
        run = _ancestor_run(gd)
        if run is not None and not _run_has_image(run):
            n += 1
    return n


def _is_diagram_or_chart(uri: str) -> bool:
    return "/diagram" in uri or "/chart" in uri


def _ancestor_run(el: etree._Element) -> etree._Element | None:
    cur = el.getparent()
    while cur is not None:
        if local(cur.tag) == "r":
            return cur
        cur = cur.getparent()
    return None


def _run_has_image(run: etree._Element) -> bool:
    return run.find(".//" + qn("a:blip")) is not None or run.find(".//" + qn("v:imagedata")) is not None


def _emit_images(run: etree._Element, ctx: _Ctx) -> list[ImageRef]:
    """收集一个 run 内全部图片（a:blip inline/anchor + v:imagedata VML），按 XML 顺序。

    归属规则：仅当 blip/imagedata 通过纯父链能上溯到 run（中间无任何 w:txbxContent
    边界）时才纳入。落在更深 txbx 内的图由那一层 emit_paragraph(sub) 单独抽取，
    外层不重复。这一形式同时覆盖多层嵌套文本框，与 _count_raw_images 的分母对齐。
    """
    refs: list[ImageRef] = []
    # a:blip — 现代 DrawingML 图（含 inline / anchor）
    for blip in run.iter(qn("a:blip")):
        if not _belongs_to(blip, run):
            continue
        rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
        if not rid:
            continue
        data = ctx.pkg.read_media(rid)
        if data is None:
            continue
        part = ctx.pkg.media_part_for_rid(rid) or ""
        ext = ("." + part.rsplit(".", 1)[1].lower()) if "." in part else ".png"
        anchor = run.find(".//" + qn("wp:anchor")) is not None
        refs.append(
            ImageRef(
                rid=rid,
                part_name=part,
                data=data,
                ext=ext,
                anchor=anchor,
                placeholder=f"media:{rid}",
            )
        )
    # v:imagedata — Word 97-2003 / VML 兼容路径（剪贴画、转存图等）
    for vimg in run.iter(qn("v:imagedata")):
        if not _belongs_to(vimg, run):
            continue
        # VML 标准用 r:id 引关系；部分转存工具沿用 DrawingML 的 r:embed —— 双取兼容
        rid = vimg.get(qn("r:id")) or vimg.get(qn("r:embed"))
        if not rid:
            continue
        data = ctx.pkg.read_media(rid)
        if data is None:
            continue
        part = ctx.pkg.media_part_for_rid(rid) or ""
        ext = ("." + part.rsplit(".", 1)[1].lower()) if "." in part else ".png"
        refs.append(
            ImageRef(
                rid=rid,
                part_name=part,
                data=data,
                ext=ext,
                anchor=False,
                placeholder=f"media:{rid}",
            )
        )
    return refs


@dataclass
class _RunOut:
    html: str
    text: str
    images: list[ImageRef]
    bold_chars: int
    total_chars: int
    max_font: float | None
    placeholder_count: int


def _serialize_runs(container: etree._Element, ctx: _Ctx) -> _RunOut:
    """序列化段落 / 单元格内的 run 容器为内联 HTML（保留粗体/斜体/内联图）。"""
    parts: list[str] = []
    text_parts: list[str] = []
    images: list[ImageRef] = []
    bold_chars = 0
    total_chars = 0
    max_font: float | None = None
    placeholder_count = 0

    for child in container:
        tag = local(child.tag)
        if tag in ("oMathPara", "oMath"):
            parts.append('<span class="sop-ph" data-ph="formula">[公式]</span>')
            placeholder_count += 1
            continue
        if tag in ("hyperlink", "ins", "smartTag"):  # 递归内部 runs（修订 ins 视为正文）
            sub = _serialize_runs(child, ctx)
            inner = sub.html
            href = ctx.pkg.document_rels().get(child.get(qn("r:id")) or "")
            if tag == "hyperlink" and href:
                parts.append(f'<a href="{html.escape(href, quote=True)}">{inner}</a>')
            else:
                parts.append(inner)
            text_parts.append(sub.text)
            images.extend(sub.images)
            placeholder_count += sub.placeholder_count
            bold_chars += sub.bold_chars
            total_chars += sub.total_chars
            if sub.max_font is not None:
                max_font = sub.max_font if max_font is None else max(max_font, sub.max_font)
            continue
        if tag != "r":
            continue
        rpr = child.find(qn("w:rPr"))
        bold = _toggle_on(rpr, "w:b")
        italic = _toggle_on(rpr, "w:i")
        font = _font_pt(rpr)
        if font is not None:
            max_font = font if max_font is None else max(max_font, font)
        run_text = "".join(t.text or "" for t in child.findall(qn("w:t")))
        if run_text:
            total_chars += len(run_text)
            if bold:
                bold_chars += len(run_text)
            esc = html.escape(run_text)
            if bold:
                esc = f"<strong>{esc}</strong>"
            if italic:
                esc = f"<em>{esc}</em>"
            parts.append(esc)
            text_parts.append(run_text)
        for ref in _emit_images(child, ctx):
            images.append(ref)
            parts.append(f'<img src="{ref.placeholder}"/>')

        # SmartArt/chart：本 run 无位图时，遍历 run 内每个 diagram/chart graphicData
        # 各插一个块状占位（与 _count_raw_placeholders 同基数）。
        if not _run_has_image(child):
            for g in child.iter(qn("a:graphicData")):
                uri = g.get("uri") or ""
                if not _is_diagram_or_chart(uri):
                    continue
                kind = "chart" if "/chart" in uri else "smartart"
                label = "[图表]" if kind == "chart" else "[SmartArt 图示]"
                parts.append(f'<div class="sop-ph" data-ph="{kind}">{label}</div>')
                placeholder_count += 1

    return _RunOut(
        html="".join(parts),
        text="".join(text_parts),
        images=images,
        bold_chars=bold_chars,
        total_chars=total_chars,
        max_font=max_font,
        placeholder_count=placeholder_count,
    )


def _read_alignment(ppr: etree._Element | None) -> str | None:
    if ppr is None:
        return None
    jc = ppr.find(qn("w:jc"))
    if jc is None:
        return None
    val = jc.get(qn("w:val"))
    if val in ("center", "right"):
        return str(val)
    return None


def emit_paragraph(para: etree._Element, ctx: _Ctx, index: int) -> Block:
    ppr = para.find(qn("w:pPr"))
    style_id = None
    outline_lvl = None
    numbered = False
    num_id: str | None = None
    num_ilvl: int | None = None
    if ppr is not None:
        pstyle = ppr.find(qn("w:pStyle"))
        if pstyle is not None:
            style_id = pstyle.get(qn("w:val"))
        ol = ppr.find(qn("w:outlineLvl"))
        if ol is not None:
            val = ol.get(qn("w:val"))
            outline_lvl = int(val) if val and val.isdigit() else None
        numpr = ppr.find(qn("w:numPr"))
        numbered = numpr is not None
        if numpr is not None:
            ilvl_el = numpr.find(qn("w:ilvl"))
            if ilvl_el is not None:
                iv = ilvl_el.get(qn("w:val"))
                num_ilvl = int(iv) if iv and iv.isdigit() else None
            numid_el = numpr.find(qn("w:numId"))
            if numid_el is not None:
                num_id = numid_el.get(qn("w:val"))

    out = _serialize_runs(para, ctx)
    raw_blips = _count_raw_images(para)
    raw_placeholders = _count_raw_placeholders(para)
    alignment = _read_alignment(ppr)
    style_level = styles_mod.classify_heading_style(
        style_id, ctx.style_index, synonyms=ctx.synonyms, style_overrides=ctx.style_overrides
    )
    inner = out.html
    if inner or out.images:
        attr = (
            ' style="text-align:center"'
            if alignment == "center"
            else (' style="text-align:right"' if alignment == "right" else "")
        )
        block_html = f"<p{attr}>{inner}</p>"
    else:
        block_html = ""
    bold_ratio = (out.bold_chars / out.total_chars) if out.total_chars else 0.0
    has_sect = ppr is not None and ppr.find(qn("w:sectPr")) is not None

    return Block(
        kind="paragraph",
        source_index=index,
        html=block_html,
        text=out.text,
        style_id=style_id,
        style_level=style_level,
        outline_lvl=outline_lvl,
        bold_ratio=bold_ratio,
        max_font_pt=out.max_font,
        alignment=alignment,
        has_section_break=has_sect,
        numbered=numbered,
        num_id=num_id,
        num_ilvl=num_ilvl,
        images=out.images,
        raw_image_count=raw_blips,
        raw_placeholder_count=raw_placeholders,
        placeholder_count=out.placeholder_count,
    )


# --------------------------------------------------------------------------- #
# 表格（双 pass vMerge + gridSpan + 单元格递归 + 表内图）
# --------------------------------------------------------------------------- #
@dataclass
class _Cell:
    grid_col: int
    colspan: int
    vmerge: str | None  # "restart" | "continue" | None
    html: str
    images: list[ImageRef]


def _cell_inner(tc: etree._Element, ctx: _Ctx) -> tuple[str, list[ImageRef]]:
    parts: list[str] = []
    images: list[ImageRef] = []
    for child in tc:
        tag = local(child.tag)
        if tag == "p":
            blk = emit_paragraph(child, ctx, -1)
            if blk.html:
                parts.append(blk.html)
            images.extend(blk.images)
        elif tag == "tbl":
            t_html, t_imgs = _table_html(child, ctx)
            parts.append(t_html)
            images.extend(t_imgs)
    return "".join(parts), images


def _table_html(tbl: etree._Element, ctx: _Ctx) -> tuple[str, list[ImageRef]]:
    rows_el = tbl.findall(qn("w:tr"))
    grid: list[list[_Cell]] = []
    images: list[ImageRef] = []

    for tr in rows_el:
        col = 0
        row_cells: list[_Cell] = []
        for tc in tr.findall(qn("w:tc")):
            tcpr = tc.find(qn("w:tcPr"))
            colspan = 1
            vmerge: str | None = None
            if tcpr is not None:
                gs = tcpr.find(qn("w:gridSpan"))
                if gs is not None:
                    val = gs.get(qn("w:val"))
                    colspan = int(val) if val and val.isdigit() else 1
                vm = tcpr.find(qn("w:vMerge"))
                if vm is not None:
                    vmerge = vm.get(qn("w:val")) or "continue"
            inner, cell_imgs = _cell_inner(tc, ctx)
            images.extend(cell_imgs)
            row_cells.append(
                _Cell(grid_col=col, colspan=colspan, vmerge=vmerge, html=inner, images=cell_imgs)
            )
            col += colspan
        grid.append(row_cells)

    # 双 pass：计算每个 restart/普通单元格的真实 rowspan
    html_rows: list[str] = []
    for r, row_cells in enumerate(grid):
        tds: list[str] = []
        for cell in row_cells:
            if cell.vmerge == "continue":
                continue  # 被上方 restart 覆盖，不渲染
            rowspan = 1
            if cell.vmerge == "restart":
                for rr in range(r + 1, len(grid)):
                    match = next(
                        (
                            c
                            for c in grid[rr]
                            if c.grid_col == cell.grid_col and c.vmerge == "continue"
                        ),
                        None,
                    )
                    if match is None:
                        break
                    rowspan += 1
            attrs = ""
            if cell.colspan > 1:
                attrs += f' colspan="{cell.colspan}"'
            if rowspan > 1:
                attrs += f' rowspan="{rowspan}"'
            tds.append(f"<td{attrs}>{cell.html}</td>")
        html_rows.append(f"<tr>{''.join(tds)}</tr>")
    return f"<table>{''.join(html_rows)}</table>", images


def emit_table(tbl: etree._Element, ctx: _Ctx, index: int) -> Block:
    table_html, images = _table_html(tbl, ctx)
    raw_blips = _count_raw_images(tbl)
    raw_tables = sum(1 for _ in tbl.iter(qn("w:tbl")))
    return Block(
        kind="table",
        source_index=index,
        html=table_html,
        images=images,
        raw_image_count=raw_blips,
        raw_table_count=raw_tables,
    )


# --------------------------------------------------------------------------- #
# body 顶层迭代（SDT 递归 + 字段跟踪）
# --------------------------------------------------------------------------- #
def _counts_as_block_paragraph(p: etree._Element) -> bool:
    """该 <w:p> 是否会被 normalize 产出为独立 paragraph block（C003 分母口径）。

    顶层段落、文本框内段落（_emit_txbx_descendants hoist 成块）计入；表格单元格
    直属段落被折叠进 table 块 HTML、不单独成块，故不计入——否则含表文档（连参考
    模板自身）会因分母虚高而误报「段落可能遗漏」。从段落上溯，先遇 txbxContent
    则计入（文本框内，即便其外层在单元格内也会被 hoist），先遇 tc 则不计入。
    """
    cur = p.getparent()
    while cur is not None:
        tag = local(cur.tag)
        if tag == "txbxContent":
            return True
        if tag == "tc":
            return False
        cur = cur.getparent()
    return True


def _iter_body_children(container: etree._Element) -> list[etree._Element]:
    """展开 SDT，返回顶层 p/tbl 元素（顺序保真）。"""
    result: list[etree._Element] = []
    for child in container:
        tag = local(child.tag)
        if tag in _BLOCK_TAGS:
            result.append(child)
        elif tag == "sdt":
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                result.extend(_iter_body_children(content))
    return result


def normalize(
    pkg: DocxPackage,
    *,
    synonyms: dict[str, int],
    style_overrides: dict[str, int],
) -> NormalizedDoc:
    body = pkg.body
    if body is None:
        return NormalizedDoc(blocks=[])
    ctx = _Ctx(
        pkg=pkg,
        style_index=styles_mod.build_style_index(pkg.styles),
        synonyms=synonyms,
        style_overrides=style_overrides,
    )
    tracker = _FieldTracker()
    blocks: list[Block] = []
    table_count = 0
    image_count = 0

    def _append(blk: Block) -> None:
        nonlocal image_count
        blocks.append(blk)
        image_count += len(blk.images)

    def _emit_txbx_descendants(
        el: etree._Element, source_index: int, *, is_toc: bool = False
    ) -> None:
        """下钻 el 内所有 w:txbxContent，把内嵌段落/表作为附加 IR Block 追加。

        共享父级 source_index，确保在 structurer 排序中紧邻外层块。
        若外层 paragraph 处于 TOC 域内，传 is_toc=True 让 hoisted 子块继承该标记，
        否则 TOC 域内的文本框内容会漏过 body_blocks 过滤。
        对表格调用时，el.iter() 会下钻到所有 cell，故 cell 内 txbx 同样被抽取
        为独立块（与表平级，不内联回 cell HTML——见 plan 的 Known limitation）。
        txbx 内若有 <w:sdt> 包裹，复用 _iter_body_children 同款 SDT 展开，
        与顶层 body 行为一致。
        """
        nonlocal table_count
        for txbx in el.iter(qn("w:txbxContent")):
            for sub in _iter_body_children(txbx):
                sub_tag = local(sub.tag)
                if sub_tag == "p":
                    blk = emit_paragraph(sub, ctx, source_index)
                    if is_toc:
                        blk.is_toc_field = True
                    _append(blk)
                elif sub_tag == "tbl":
                    blk = emit_table(sub, ctx, source_index)
                    if is_toc:
                        blk.is_toc_field = True
                    _append(blk)
                    table_count += 1

    for i, el in enumerate(_iter_body_children(body)):
        tag = local(el.tag)
        if tag == "p":
            block = emit_paragraph(el, ctx, i)
            block.is_toc_field = tracker.scan(el, i)
            _append(block)
            _emit_txbx_descendants(el, i, is_toc=block.is_toc_field)
        else:  # tbl
            block = emit_table(el, ctx, i)
            table_count += 1
            _append(block)
            _emit_txbx_descendants(el, i)

    raw_paragraph_count = sum(
        1 for p in body.iter(qn("w:p")) if _counts_as_block_paragraph(p)
    )
    return NormalizedDoc(
        blocks=blocks,
        total_image_count=image_count,
        total_table_count=table_count,
        toc_field_end_index=tracker.toc_end_index,
        style_index=ctx.style_index,
        raw_paragraph_count=raw_paragraph_count,
    )
