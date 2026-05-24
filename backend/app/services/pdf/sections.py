"""各区段 flowable 构建（pdf-rendering §3/§4/§5/§6 / §59.6·Q364）。

封面 / TOC / 修订记录 / 正文（章节·content·步骤·12 型占位符）/ 附件区段。编号 L1
渲染追加 `.0`（render-only，§47/Q305）；元素前置 `_pdf_key` 供 afterFlowable 收页号。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from reportlab.lib.colors import Color
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from app.services.pdf import flowables as fl
from app.services.pdf.constants import (
    ATTACHMENT_CHAPTER_NAMES,
    ATTACHMENT_CHAPTER_TITLE,
    ATTACHMENT_KIND_LABELS,
    ATTACHMENT_MARK_PREFIX,
    CHANGE_TYPE_LABELS,
    CHECKBOX_GLYPH,
    CONTENT_WIDTH,
    DEFAULT_FAIL_LABEL,
    DEFAULT_PASS_LABEL,
    LEVEL_OF_USE_LABELS,
    RADIO_GLYPH,
    REVISION_CHANGE_TYPES,
    RISK_COLORS,
    RISK_LABELS,
)
from app.services.pdf.context import (
    AttachmentData,
    ChapterData,
    ProcedureData,
    RenderData,
    StepData,
)
from app.services.pdf.html_render import render_html
from app.services.pdf.styles import s

FULL_SPACE = "　"  # 全角空格（编号与标题间，§6.2）


# --------------------------------------------------------------------------- #
# 公共
# --------------------------------------------------------------------------- #
def _keyed(para: Paragraph, key: tuple[str, str]) -> Paragraph:
    para._pdf_key = key
    para.keepWithNext = 1
    return para


def display_code(code: str, level: int, content_type: str, skip: bool) -> str:
    """渲染编号：skip / content / 空 code → ''；L1 chapter 追加 .0（§47/Q305）。"""
    if skip or content_type == "content" or not code:
        return ""
    return f"{code}.0" if level == 1 else code


def _fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt is not None else ""


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_multiline(text: str) -> str:
    """转义并把换行转为 <br/>（修订说明等多行文本，§5.2）。"""
    return _esc(text).replace("\n", "<br/>")


# --------------------------------------------------------------------------- #
# 封面（§3.1-3.4）
# --------------------------------------------------------------------------- #
def build_cover(data: RenderData) -> list[Flowable]:
    p = data.procedure
    out: list[Flowable] = [Spacer(1, 36), Paragraph(_esc(p.name), s("cover_title")), Spacer(1, 18)]

    out.append(Paragraph(f"程序编号: {_esc(p.code)}", s("cover_sub")))
    out.append(Paragraph(f"版本: Rev.{p.version}", s("cover_sub")))
    cn, en = LEVEL_OF_USE_LABELS.get(p.level_of_use, (p.level_of_use, ""))
    out.append(Paragraph(f"用途级别: {cn} ({en})", s("cover_sub")))
    if p.folder_full_path:
        out.append(Paragraph(f"所属文件夹: {_esc(p.folder_full_path)}", s("cover_sub")))

    # 风险 / 质量等级 + 色块（§3.2）
    out.append(_level_line("风险等级", p.risk_level))
    out.append(_level_line("质量等级", p.quality_level))

    # 自定义字段（§3.1/Q257）
    for f in data.cover_fields:
        out.append(Paragraph(f"{_esc(f.name)}: {_esc(f.display_value)}", s("cover_sub")))

    out.append(Paragraph(f"创建日期: {_fmt_date(p.created_at)}", s("cover_sub")))
    out.append(Paragraph(f"更新日期: {_fmt_date(p.updated_at)}", s("cover_sub")))

    # 版本状态标识（§3.4）
    if p.status == "DRAFT":
        out.append(Paragraph("状态: 草稿 DRAFT", s("cover_status_draft")))
    elif p.status == "ARCHIVED":
        txt = "已作废 SUPERSEDED"
        if p.archived_at is not None:
            txt += f" · 作废日期 {_fmt_date(p.archived_at)}"
        out.append(Paragraph(txt, s("cover_status_archived")))

    # 签名栏（§3.3）
    out.append(Spacer(1, 28))
    out.append(fl.signature_bar())
    return out


def _level_line(label: str, level: int) -> Flowable:
    name = RISK_LABELS.get(level, str(level))
    color = RISK_COLORS.get(level, Color(0, 0, 0))
    r, g, b = int(color.red * 255), int(color.green * 255), int(color.blue * 255)
    hexc = f"#{r:02X}{g:02X}{b:02X}"
    text = f'{label}: {name}（{level}）<font color="{hexc}">■</font>'
    return Paragraph(text, s("cover_sub"))


# --------------------------------------------------------------------------- #
# TOC（§4）
# --------------------------------------------------------------------------- #
def toc_chapters(data: RenderData) -> list[ChapterData]:
    """TOC 范围：chapter 且 skip_numbering=false（§4.1/Q46），递归全 3 级。"""
    result: list[ChapterData] = []

    def walk(nodes: list[ChapterData]) -> None:
        for n in nodes:
            if n.content_type == "chapter" and not n.skip_numbering:
                result.append(n)
            walk(n.children)

    walk(data.root_chapters)
    return result


_TOC_STYLE = {1: "toc_l1", 2: "toc_l2", 3: "toc_l3"}


def build_toc(data: RenderData, toc_pages: dict[str, str]) -> list[Flowable]:
    out: list[Flowable] = [Paragraph("目录", s("toc_title"))]
    chapters = toc_chapters(data)
    if not chapters:
        out.append(Paragraph("（无章节）", s("placeholder_muted")))
        return out
    for ch in chapters:
        code = display_code(ch.code, ch.level, ch.content_type, ch.skip_numbering)
        page = toc_pages.get(ch.id, "")
        dots = " " + "." * 3 + " "
        text = f"{_esc(code)} {_esc(ch.title)}{dots}{page}"
        out.append(Paragraph(text, s(_TOC_STYLE.get(ch.level, "toc_l3"))))
    return out


# --------------------------------------------------------------------------- #
# 修订记录（§5）
# --------------------------------------------------------------------------- #
def build_revision(data: RenderData) -> list[Flowable]:
    p = data.procedure
    out: list[Flowable] = [Paragraph("修订记录", s("section_title"))]
    entries = [e for e in p.version_change_log if e.get("change_type") in REVISION_CHANGE_TYPES]
    if not entries:
        out.append(Paragraph("（无修订记录）", s("placeholder_muted")))
        return out

    head = s("table_head")
    cell = s("table_cell")
    rows: list[list[Any]] = [
        [
            Paragraph("版本号", head),
            Paragraph("变更类型", head),
            Paragraph("变更日期", head),
            Paragraph("说明", head),
        ]
    ]
    for e in entries:
        ver = e.get("version", "")
        ctype = CHANGE_TYPE_LABELS.get(str(e.get("change_type")), str(e.get("change_type")))
        if e.get("change_type") == "rollback" and e.get("rollback_from_version"):
            ctype += f"（源 v{e['rollback_from_version']}）"
        changed = str(e.get("changed_at", ""))[:10]
        desc = _revision_desc(e, p)
        rows.append(
            [
                Paragraph(_esc(str(ver)), cell),
                Paragraph(_esc(ctype), cell),
                Paragraph(_esc(changed), cell),
                Paragraph(desc, cell),
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.10, 0.14, 0.16, 0.60)]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(_grid_style())
    out.append(t)
    return out


def _revision_desc(entry: dict[str, Any], p: ProcedureData) -> str:
    """说明列拼接：description + reason + （本版本对应的）version_update_notes（§5.2）。"""
    parts: list[str] = []
    for k in ("description", "reason"):
        v = entry.get(k)
        if v:
            parts.append(_esc_multiline(str(v)))
    if entry.get("version") == p.version and p.version_update_notes.strip():
        parts.append(_esc_multiline(p.version_update_notes.strip()))
    return "<br/>".join(parts) if parts else "—"


def _grid_style() -> TableStyle:
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, Color(0, 0, 0)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), Color(0.93, 0.93, 0.93)),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
    )


# --------------------------------------------------------------------------- #
# 正文（§6）
# --------------------------------------------------------------------------- #
def build_content(data: RenderData) -> tuple[list[Flowable], bool]:
    """返回 (正文 flowables, 是否含附件区段)。"""
    out: list[Flowable] = []
    if not data.root_chapters and not data.root_steps:
        out.append(Paragraph("（程序无内容）", s("placeholder_muted")))
        return out, False

    attach_chapter = _find_attachment_chapter(data) if data.attachments else None
    for ch in data.root_chapters:
        _render_chapter(ch, data, out, attach_into=attach_chapter)
    for st in data.root_steps:
        _render_step(st, data, out)

    has_attach = False
    if data.attachments and attach_chapter is None:
        out.append(fl.PageMarker(("section", "attachments")))
        out.extend(_virtual_attachment_chapter(data))
        has_attach = True
    elif data.attachments:
        has_attach = True
    return out, has_attach


def _find_attachment_chapter(data: RenderData) -> ChapterData | None:
    for ch in data.root_chapters:
        if ch.content_type == "chapter" and ch.title.strip() in ATTACHMENT_CHAPTER_NAMES:
            return ch
    return None


def _render_chapter(
    ch: ChapterData, data: RenderData, out: list[Flowable], *, attach_into: ChapterData | None
) -> None:
    if ch.content_type == "content":
        out.extend(render_html(ch.rich_content, data.assets, base_style="content"))
        return
    code = display_code(ch.code, ch.level, ch.content_type, ch.skip_numbering)
    style = {1: "h1", 2: "h2", 3: "h3"}.get(ch.level, "h3")
    title = f"{_esc(code)}{FULL_SPACE}{_esc(ch.title)}" if code else _esc(ch.title)
    out.append(_keyed(Paragraph(title, s(style)), ("chapter", ch.id)))
    for child in ch.children:
        _render_chapter(child, data, out, attach_into=attach_into)
    for st in ch.steps:
        _render_step(st, data, out)
    # 用户自建「附件」章节：在其后追加附件表（§6.6.2 第一分支）
    if attach_into is not None and ch.id == attach_into.id:
        out.append(fl.PageMarker(("section", "attachments")))
        out.append(_attachment_table(data.attachments))


def _render_step(st: StepData, data: RenderData, out: list[Flowable]) -> None:
    code = "" if st.skip_numbering or not st.code else st.code
    title = f"{_esc(code)}{FULL_SPACE}{_esc(st.title)}" if code else _esc(st.title)
    out.append(_keyed(Paragraph(title or "（步骤）", s("step_title")), ("step", st.id)))
    # 按 input_schema.type 分发渲染路径（§6.3 / Q261/§40.1）
    ftype = str((st.input_schema or {}).get("type", "COMMON")).upper()
    if ftype in ("NOTE", "CAUTION", "WARNING"):
        body = render_html(st.content, data.assets, base_style="alert_body")
        if body:
            out.append(fl.alert_box(ftype.lower(), body))
    elif ftype == "COMMON":
        out.extend(render_html(st.content, data.assets))
    # 数据型 / NONE：正文隐藏，不渲染 content
    # 附件标记（§6.3/Q203）
    for mark in st.attachment_marks:
        out.append(Paragraph(_attachment_mark_text(mark), s("step_mark")))
    # 执行记录区（15 型占位符）；警示型不渲染占位符
    if ftype not in ("NOTE", "CAUTION", "WARNING"):
        placeholder = _form_placeholder(st.input_schema)
        if placeholder:
            out.append(placeholder)
    # 确认行
    if st.require_confirmation:
        out.append(
            Paragraph(
                f"{CHECKBOX_GLYPH} 已确认完成    签名: __________  日期: __________",
                s("step_placeholder"),
            )
        )


def _attachment_mark_text(mark: dict[str, Any]) -> str:
    # 编辑器存 filename（StepDetailPanel），兼容文档/规范的 name
    raw_name = mark.get("filename") or mark.get("name") or ""
    name = _esc(str(raw_name))
    kind = ATTACHMENT_KIND_LABELS.get(str(mark.get("kind", "other")), "其他")
    text = f"{ATTACHMENT_MARK_PREFIX} {name}（{kind}）"
    if mark.get("note"):
        text += f" — {_esc(str(mark['note']))}"
    return text


def _form_placeholder(schema: dict[str, Any]) -> Flowable | None:
    """执行表单 12 型 → 纸质占位符（§6.3/Q262）。"""
    t = str(schema.get("type", "COMMON")).upper()
    st = s("step_placeholder")
    if t == "NONE":
        return None
    if t == "COMMON":
        return Paragraph(f"{CHECKBOX_GLYPH} 已完成", st)
    if t == "CHECK":
        pl = schema.get("pass_label") or DEFAULT_PASS_LABEL
        fa = schema.get("fail_label") or DEFAULT_FAIL_LABEL
        return Paragraph(
            f"执行结果:  {CHECKBOX_GLYPH} {_esc(str(pl))}    {CHECKBOX_GLYPH} {_esc(str(fa))}", st
        )
    if t == "YESNO":
        return Paragraph(f"{CHECKBOX_GLYPH} 是    {CHECKBOX_GLYPH} 否", st)
    if t == "NUMBER":
        label = _esc(str(schema.get("label", "数值")))
        unit = _esc(str(schema.get("unit", "")))
        lo, hi = schema.get("min"), schema.get("max")
        rng = f"　(合格范围 {lo}~{hi})" if lo is not None or hi is not None else ""
        return Paragraph(f"{label}: __________ {unit}{rng}", st)
    if t == "METER":
        label = _esc(str(schema.get("label", "读数")))
        unit = _esc(str(schema.get("unit", "")))
        return Paragraph(f"{label}: __________ {unit}", st)
    if t in ("CHECKBOX", "RADIO"):
        mark = CHECKBOX_GLYPH if t == "CHECKBOX" else RADIO_GLYPH
        opts = _schema_options(schema)
        cells = (
            "   ".join(f"{mark} {_esc(o)}" for o in opts)
            if opts
            else f"{mark} 选项1   {mark} 选项2"
        )
        return Paragraph(cells, st)
    if t == "UPLOAD":
        return Paragraph("附件: ____________（见附页 / 粘贴）", st)
    if t == "SIGNATURE":
        return Paragraph("签名: ________________", st)
    if t == "DATE":
        return Paragraph("日期: ______ 年 ___ 月 ___ 日", st)
    if t == "PHOTO":
        return _photo_box()
    return Paragraph(f"{CHECKBOX_GLYPH} 已完成", st)  # 未知型兜底


def _schema_options(schema: dict[str, Any]) -> list[str]:
    raw = schema.get("options") or []
    out: list[str] = []
    for o in raw:
        if isinstance(o, dict):
            out.append(str(o.get("label", o.get("value", ""))))
        else:
            out.append(str(o))
    return [x for x in out if x]


def _photo_box() -> Flowable:
    t = Table(
        [[Paragraph("照片粘贴区", s("placeholder_muted"))]],
        colWidths=[CONTENT_WIDTH * 0.5],
        rowHeights=[60],
    )
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, Color(0.4, 0.4, 0.4)),
                ("LINESTYLE", (0, 0), (-1, -1), "Dashed"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("DASH", (0, 0), (-1, -1), (2, 2)),
            ]
        )
    )
    return t


# --------------------------------------------------------------------------- #
# 附件区段（§6.6）
# --------------------------------------------------------------------------- #
def _virtual_attachment_chapter(data: RenderData) -> list[Flowable]:
    n = _next_attachment_number(data)
    title = f"{n}.0{FULL_SPACE}{ATTACHMENT_CHAPTER_TITLE}"
    out: list[Flowable] = [Paragraph(title, s("h1"))]
    out.append(_attachment_table(data.attachments))
    return out


def _next_attachment_number(data: RenderData) -> int:
    max_seq = 0
    for ch in data.root_chapters:
        if ch.content_type == "chapter" and not ch.skip_numbering and ch.code.isdigit():
            max_seq = max(max_seq, int(ch.code))
    return max_seq + 1


def _attachment_table(attachments: list[AttachmentData]) -> Flowable:
    head = s("table_head")
    cell = s("table_cell")
    rows: list[list[Any]] = [
        [Paragraph(c, head) for c in ("序号", "文件名", "大小", "类型", "上传日期", "描述")]
    ]
    for i, a in enumerate(attachments, start=1):
        rows.append(
            [
                Paragraph(str(i), cell),
                Paragraph(_esc(a.file_name), cell),
                Paragraph(_human_size(a.size_bytes), cell),
                Paragraph(_esc(a.mime_type), cell),
                Paragraph(_fmt_date(a.created_at), cell),
                Paragraph(_esc(a.description) if a.description else "—", cell),
            ]
        )
    widths = [CONTENT_WIDTH * w for w in (0.06, 0.30, 0.10, 0.12, 0.14, 0.28)]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(_grid_style())
    return t


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.2f} KB"
    return f"{n / (1024 * 1024):.2f} MB"
