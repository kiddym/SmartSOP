"""自定义 flowable 与水印（pdf-rendering §3.3/§3.4/§7）。

警示框 / 签名栏 / hold-point 用单元格 Table 实现（reportlab 原生处理换行 + 边框 +
背景 + 内边距）；水印由页面回调 `draw_watermark` 在 onPage 绘制于内容下层。
"""

from __future__ import annotations

import math
from typing import Any

from reportlab.lib.colors import Color, black, white
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, KeepTogether, Paragraph, Table, TableStyle

from app.services.pdf import fonts
from app.services.pdf.constants import ALERT_SPECS, CONTENT_WIDTH, HOLD_BORDER, WATERMARK
from app.services.pdf.styles import s


class PageMarker(Flowable):  # type: ignore[misc]  # reportlab 无类型
    """零尺寸定位标记：afterFlowable 据 `_pdf_key` 记录所在物理页（§59.3）。"""

    def __init__(self, key: tuple[str, str]) -> None:
        super().__init__()
        self._pdf_key = key
        self.width = 0.0
        self.height = 0.0

    def wrap(self, _aw: float, _ah: float) -> tuple[float, float]:
        return (0.0, 0.0)

    def draw(self) -> None:  # pragma: no cover - 不绘制任何内容
        pass


def _cell_table(
    inner: list[Flowable],
    *,
    bg: Color,
    border: Color,
    border_w: float = 1.0,
    pad: float = 8.0,
    lr_pad: float = 12.0,
    width: float = CONTENT_WIDTH,
) -> Table:
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("BOX", (0, 0), (-1, -1), border_w, border),
                ("LEFTPADDING", (0, 0), (-1, -1), lr_pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), lr_pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def alert_box(kind: str, body: list[Flowable], *, width: float = CONTENT_WIDTH) -> Flowable:
    """note/caution/warning 三色框（§7.1-7.3）。kind ∈ note|caution|warning。"""
    spec = ALERT_SPECS[kind]
    title_style = s("alert_title").clone("alert_title_x", textColor=spec["title_color"])
    inner: list[Flowable] = [Paragraph(str(spec["title"]), title_style), *body]
    return _cell_table(inner, bg=spec["bg"], border=spec["border"], width=width)


def signature_bar(width: float = CONTENT_WIDTH) -> Flowable:
    """三栏签名区（编制/审核/批准 + 签名 + 日期），封面与 inline 共用（§3.3/§7.5）。"""
    col = width / 3.0
    head = s("table_head")
    cell = s("table_cell")
    data = [
        [Paragraph("编制", head), Paragraph("审核", head), Paragraph("批准", head)],
        [Paragraph("签名:", cell), Paragraph("签名:", cell), Paragraph("签名:", cell)],
        [Paragraph("日期:", cell), Paragraph("日期:", cell), Paragraph("日期:", cell)],
    ]
    t = Table(data, colWidths=[col, col, col])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, black),
                ("BACKGROUND", (0, 0), (-1, 0), Color(0.93, 0.93, 0.93)),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def hold_point(body: list[Flowable], *, width: float = CONTENT_WIDTH) -> Flowable:
    """hold-point：红双圈边框 + 标题 + 内容 + 自动追加签名/日期行（§7.4）。"""
    inner: list[Flowable] = [Paragraph("◆ HOLD POINT 检查点", s("hold_title")), *body]
    inner.append(Paragraph("签名: __________   日期: __________", s("alert_body")))
    box = _cell_table(inner, bg=white, border=HOLD_BORDER, border_w=2.0, width=width)
    # 外圈细线模拟双圈
    outer = Table([[box]], colWidths=[width])
    outer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, HOLD_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return KeepTogether([outer])


# --------------------------------------------------------------------------- #
# 水印（§3.4 / Q225）：onPage 绘制于内容下层
# --------------------------------------------------------------------------- #
def draw_watermark(canvas: Canvas, status: str, page_w: float, page_h: float) -> None:
    """按 status 绘制 45° 斜纹平铺水印（DRAFT/ARCHIVED；PUBLISHED 无）。"""
    spec: dict[str, Any] | None = WATERMARK.get(status)
    if spec is None:
        return
    canvas.saveState()
    try:
        canvas.setFillColor(spec["color"])
        canvas.setFillAlpha(float(spec["alpha"]))
        canvas.setFont(fonts.hei(), 30)
        text = str(spec["text"])
        canvas.translate(page_w / 2.0, page_h / 2.0)
        canvas.rotate(45)
        diag = math.hypot(page_w, page_h)
        step_x = 260.0
        step_y = 150.0
        y = -diag / 2.0
        while y < diag / 2.0:
            x = -diag / 2.0
            while x < diag / 2.0:
                canvas.drawString(x, y, text)
                x += step_x
            y += step_y
    finally:
        canvas.restoreState()
