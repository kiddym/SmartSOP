"""ProcedureDocTemplate（pdf-rendering §2/§6.1 / §59.3·Q361）。

三 PageTemplate：cover（无页眉）/ front（TOC+修订，罗马页码）/ content（阿拉伯页码）。
onPage 绘制水印（内容下层）+ 页眉（左标题 / 右三行 编号·版本·页码）。afterFlowable 据
`_pdf_key` 收 element→物理页；onPage 记 物理页→区段，供引擎算 P/T 与 layout。
"""

from __future__ import annotations

from typing import Any

from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

from app.services.pdf import fonts
from app.services.pdf.constants import (
    HEADER_HEIGHT,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_LEFT,
    PAGE_MARGIN_RIGHT,
    PAGE_MARGIN_TOP,
    PAGE_SIZE,
)
from app.services.pdf.flowables import draw_watermark

_ROMAN = [
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
]


def to_roman(n: int) -> str:
    """小写罗马数字（§6.1 前置页页码）。n<1 返回空串。"""
    if n < 1:
        return ""
    out: list[str] = []
    for value, sym in _ROMAN:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


class ProcedureDocTemplate(BaseDocTemplate):  # type: ignore[misc]  # reportlab 无类型
    def __init__(
        self,
        buf: Any,
        *,
        status: str,
        header_title: str,
        header_code: str,
        header_version: int,
        totals: dict[str, int],
    ) -> None:
        super().__init__(
            buf,
            pagesize=PAGE_SIZE,
            leftMargin=PAGE_MARGIN_LEFT,
            rightMargin=PAGE_MARGIN_RIGHT,
            topMargin=PAGE_MARGIN_TOP,
            bottomMargin=PAGE_MARGIN_BOTTOM,
            title=None,
            allowSplitting=1,
        )
        self._status = status
        self._htitle = header_title
        self._hcode = header_code
        self._hver = header_version
        self._totals = totals
        self.page_sections: dict[int, str] = {}
        self.element_pages: dict[tuple[str, str], int] = {}

        page_w, page_h = PAGE_SIZE
        width = page_w - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT
        full_h = page_h - PAGE_MARGIN_TOP - PAGE_MARGIN_BOTTOM
        body_h = full_h - HEADER_HEIGHT
        full_frame = Frame(PAGE_MARGIN_LEFT, PAGE_MARGIN_BOTTOM, width, full_h, id="full")
        body_frame = Frame(PAGE_MARGIN_LEFT, PAGE_MARGIN_BOTTOM, width, body_h, id="body")
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[full_frame], onPage=self._on_cover),
                PageTemplate(id="front", frames=[body_frame], onPage=self._on_front),
                PageTemplate(id="content", frames=[body_frame], onPage=self._on_content),
            ]
        )

    # 收集 element → 物理页（首次出现 = 标题所在页）
    def afterFlowable(self, flowable: Any) -> None:  # noqa: N802 — 覆盖 reportlab 驼峰 API
        key = getattr(flowable, "_pdf_key", None)
        if key is not None and key not in self.element_pages:
            self.element_pages[key] = self.page

    # --- onPage 回调 -------------------------------------------------------- #
    def _on_cover(self, canvas: Canvas, _doc: Any) -> None:
        self.page_sections[self.page] = "cover"
        self._watermark(canvas)

    def _on_front(self, canvas: Canvas, _doc: Any) -> None:
        self.page_sections[self.page] = "front"
        self._watermark(canvas)
        self._header(canvas, "front")

    def _on_content(self, canvas: Canvas, _doc: Any) -> None:
        self.page_sections[self.page] = "content"
        self._watermark(canvas)
        self._header(canvas, "content")

    def _watermark(self, canvas: Canvas) -> None:
        page_w, page_h = PAGE_SIZE
        draw_watermark(canvas, self._status, page_w, page_h)

    def _page_label(self, section: str) -> str:
        cover = self._totals.get("cover_pages", 1)
        front = self._totals.get("front_pages", 0)
        total = self._totals.get("total_pages", 0)
        if section == "front":
            n = self.page - cover
            p = to_roman(n)
        else:
            n = self.page - cover - front
            p = str(n) if n >= 1 else ""
        if not p or not total:
            return ""
        return f"第 {p} 页 / 共 {total} 页"

    def _header(self, canvas: Canvas, section: str) -> None:
        page_w, page_h = PAGE_SIZE
        top = page_h - PAGE_MARGIN_TOP
        right_x = page_w - PAGE_MARGIN_RIGHT
        left_x = PAGE_MARGIN_LEFT
        canvas.saveState()
        # 左列：程序标题（垂直居中）
        canvas.setFont(fonts.song(), 11)
        canvas.drawString(left_x, top - HEADER_HEIGHT / 2 - 4, _truncate(self._htitle, 28))
        # 右列三行
        canvas.setFont(fonts.song(), 10)
        canvas.drawRightString(right_x, top - 11, f"程序编号: {self._hcode}")
        canvas.drawRightString(right_x, top - 24, f"版本: Rev.{self._hver}")
        label = self._page_label(section)
        if label:
            canvas.drawRightString(right_x, top - 37, label)
        # 分隔线
        sep_y = top - HEADER_HEIGHT + 4
        canvas.setLineWidth(0.6)
        canvas.line(left_x, sep_y, right_x, sep_y)
        canvas.restoreState()


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
