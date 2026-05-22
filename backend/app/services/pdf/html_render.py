"""富文本 HTML → reportlab flowable（pdf-rendering §6.4/§7/§9 / §59.5·Q363）。

stdlib `html.parser`，渲染层零第三方依赖。识别：
- 特殊块 `<div class="note-block|caution-block|warning-block|hold-point|signature-bar">`（§7）；
- `<table>`（嵌套表 → 缩进列表 + warning，§9.2）；
- 独立 `<img src=".../assets/{id}">`（等比缩放页宽、独占居中，§9.1）；
- `<p>/<h1-6>/<ul>/<ol>/<li>` 块级、`<b>/<strong>/<i>/<em>/<u>/<br>/<a>` 内联（未知标签降级文本）。
"""

from __future__ import annotations

import logging
from html import escape
from html.parser import HTMLParser
from io import BytesIO

from reportlab.lib.colors import black
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Image, Paragraph, Table, TableStyle

from app.services import asset_service
from app.services.pdf.constants import BLOCK_CLASS_TO_ALERT, CONTENT_WIDTH
from app.services.pdf.flowables import alert_box, hold_point, signature_bar
from app.services.pdf.styles import s

logger = logging.getLogger("app.services.pdf")

MAX_IMG_HEIGHT = 24 * 28.35  # ~24cm 单页可用高度上限（§9.1）
_INLINE_MAP = {"strong": "b", "em": "i", "b": "b", "i": "i", "u": "u"}
_HEADING_STYLE = {"h1": "h1", "h2": "h2", "h3": "h3", "h4": "h3", "h5": "h3", "h6": "h3"}
_SPECIAL_DIV = set(BLOCK_CLASS_TO_ALERT) | {"hold-point", "signature-bar"}


class _Collector:
    """一个 flowable 收集层（特殊块用 special_type 在闭合时包裹自身产出）。"""

    def __init__(self, style_name: str, special_type: str | None = None) -> None:
        self.flowables: list[Flowable] = []
        self.inline: list[str] = []
        self.style_name = style_name
        self.special_type = special_type  # note/caution/warning/hold/signature
        self.is_special = special_type is not None

    def flush(self, style_name: str | None = None) -> None:
        text = "".join(self.inline).strip()
        self.inline = []
        if text:
            self.flowables.append(Paragraph(text, s(style_name or self.style_name)))


class _HtmlRenderer(HTMLParser):
    def __init__(self, assets: dict[str, tuple[bytes, str]], width: float, base_style: str) -> None:
        super().__init__(convert_charrefs=True)
        self._assets = assets
        self._width = width
        self._root = _Collector(base_style, None)
        self._stack: list[_Collector] = [self._root]
        self._block_style: list[str] = []  # 当前块级样式（h*/p/li）
        # 表格状态
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._table_depth = 0

    @property
    def _cur(self) -> _Collector:
        return self._stack[-1]

    def _para_style(self) -> str:
        return self._block_style[-1] if self._block_style else self._cur.style_name

    # ---- 文本 -------------------------------------------------------------- #
    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self._cell is not None:
            self._cell.append(escape(data))
        else:
            self._cur.inline.append(escape(data))

    # ---- 开标签 ------------------------------------------------------------ #
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}

        # 表格模式下的子结构
        if self._rows is not None:
            self._table_start(tag, ad)
            return

        cls = ad.get("class", "").split()
        if tag == "div" and any(c in _SPECIAL_DIV for c in cls):
            self._open_special(cls)
            return
        if tag == "table":
            self._open_table()
            return
        if tag == "img":
            self._handle_img(ad)
            return
        if tag in _INLINE_MAP:
            self._cur.inline.append(f"<{_INLINE_MAP[tag]}>")
            return
        if tag == "br":
            self._cur.inline.append("<br/>")
            return
        if tag in ("a", "span", "font"):
            return  # 透明：保留文本
        if tag in _HEADING_STYLE:
            self._cur.flush(self._para_style())
            self._block_style.append(_HEADING_STYLE[tag])
            return
        if tag in ("p", "li"):
            self._cur.flush(self._para_style())
            self._block_style.append("body")
            if tag == "li":
                self._cur.inline.append("• ")
            return
        if tag in ("ul", "ol", "div"):
            self._cur.flush(self._para_style())

    # ---- 闭标签 ------------------------------------------------------------ #
    def handle_endtag(self, tag: str) -> None:
        if self._rows is not None:
            self._table_end(tag)
            return
        if tag in _INLINE_MAP:
            self._cur.inline.append(f"</{_INLINE_MAP[tag]}>")
            return
        if tag in ("a", "span", "font", "br"):
            return
        if tag in _HEADING_STYLE or tag in ("p", "li"):
            self._cur.flush(self._para_style())
            if self._block_style:
                self._block_style.pop()
            return
        if tag == "div":
            if self._cur.is_special:
                self._close_special()
            else:
                self._cur.flush(self._para_style())

    # ---- 特殊块 ------------------------------------------------------------ #
    def _open_special(self, classes: list[str]) -> None:
        self._cur.flush(self._para_style())
        kind = next((BLOCK_CLASS_TO_ALERT[c] for c in classes if c in BLOCK_CLASS_TO_ALERT), None)
        special_type = kind or ("hold" if "hold-point" in classes else "signature")
        self._stack.append(_Collector("alert_body", special_type))

    def _close_special(self) -> None:
        col = self._stack.pop()
        col.flush()
        produced = self._wrap_special(col.special_type, col.flowables)
        self._cur.flowables.extend(produced)

    def _wrap_special(self, special_type: str | None, body: list[Flowable]) -> list[Flowable]:
        if special_type is None:
            return body
        if special_type in BLOCK_CLASS_TO_ALERT.values():
            return [alert_box(special_type, body, width=self._width)]
        if special_type == "hold":
            return [hold_point(body, width=self._width)]
        if special_type == "signature":
            return [signature_bar(self._width)]
        return body

    # ---- 表格 -------------------------------------------------------------- #
    def _open_table(self) -> None:
        self._cur.flush(self._para_style())
        self._table_depth = 1
        self._rows = []

    def _table_start(self, tag: str, _ad: dict[str, str]) -> None:
        if tag == "table":  # 嵌套表 → 降级缩进列表（§9.2）
            self._table_depth += 1
            logger.warning("检测到嵌套表格，已降级为缩进列表")
            if self._cell is not None:
                self._cell.append("<br/>")
            return
        if self._table_depth > 1:  # 嵌套表内部：结构降级为项目符号
            if tag == "tr" and self._cell is not None:
                self._cell.append("<br/>")
            elif tag in ("td", "th") and self._cell is not None:
                self._cell.append("• ")
            return
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag in _INLINE_MAP and self._cell is not None:
            self._cell.append(f"<{_INLINE_MAP[tag]}>")
        elif tag == "br" and self._cell is not None:
            self._cell.append("<br/>")
        elif tag == "img" and self._cell is not None:
            self._cell.append("[图片]")

    def _table_end(self, tag: str) -> None:
        if tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._close_table()
            return
        if self._table_depth > 1:
            return
        if tag in ("td", "th"):
            if self._cell is not None and self._row is not None:
                self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr":
            if self._row is not None and self._rows is not None:
                self._rows.append(self._row)
            self._row = None
        elif tag in _INLINE_MAP and self._cell is not None:
            self._cell.append(f"</{_INLINE_MAP[tag]}>")

    def _close_table(self) -> None:
        rows = self._rows or []
        self._rows = None
        self._row = None
        self._cell = None
        flow = _build_table(rows, self._width)
        if flow is not None:
            self._cur.flowables.append(flow)

    # ---- 图片 -------------------------------------------------------------- #
    def _handle_img(self, ad: dict[str, str]) -> None:
        self._cur.flush(self._para_style())
        src = ad.get("src", "")
        ids = asset_service.extract_asset_ids(src)
        if not ids:
            self._cur.flowables.append(Paragraph("[图片缺失]", s("body")))
            return
        self._cur.flowables.append(_image_flowable(next(iter(ids)), self._assets, self._width))

    def result(self) -> list[Flowable]:
        for col in self._stack:
            col.flush()
        return self._root.flowables


def _build_table(rows: list[list[str]], width: float) -> Flowable | None:
    if not rows:
        return None
    ncols = max(len(r) for r in rows)
    norm = [[*r, *([""] * (ncols - len(r)))] for r in rows]
    cell_style = s("table_cell")
    data = [[Paragraph(c or "", cell_style) for c in r] for r in norm]
    t = Table(data, colWidths=[width / ncols] * ncols, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _image_flowable(asset_id: str, assets: dict[str, tuple[bytes, str]], width: float) -> Flowable:
    data = assets.get(asset_id)
    if data is None:
        return Paragraph("[图片缺失]", s("body"))
    raw, _mime = data
    try:
        iw, ih = ImageReader(BytesIO(raw)).getSize()
        if not iw or not ih:
            raise ValueError("zero size")
        scale = min(1.0, width / iw)
        w, h = iw * scale, ih * scale
        if h > MAX_IMG_HEIGHT:
            w *= MAX_IMG_HEIGHT / h
            h = MAX_IMG_HEIGHT
        img = Image(BytesIO(raw), width=w, height=h)
        img.hAlign = "CENTER"
        return img
    except Exception as exc:  # 不支持格式 → 占位（§9.1）
        logger.warning("pdf image render failed asset=%s err=%s", asset_id, exc)
        return Paragraph("[不支持的图片格式]", s("body"))


def render_html(
    html: str,
    assets: dict[str, tuple[bytes, str]],
    *,
    width: float = CONTENT_WIDTH,
    base_style: str = "body",
) -> list[Flowable]:
    """把一段富文本 HTML 转为 flowable 列表。空 → []。"""
    if not html or not html.strip():
        return []
    parser = _HtmlRenderer(assets, width, base_style)
    parser.feed(html)
    parser.close()
    return parser.result()
