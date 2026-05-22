"""ParagraphStyle 工厂（pdf-rendering §3/§4/§6/§7）。

样式按需构建后缓存复用（§11.4 性能）。所有字号、行距（1.5×）、章节标题层级
（§6.2）、TOC 层级（§4.2）集中此处。
"""

from __future__ import annotations

from functools import lru_cache

from reportlab.lib.colors import Color, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, StyleSheet1

from app.services.pdf import fonts
from app.services.pdf.constants import LINE_HEIGHT


def _leading(size: float) -> float:
    return size * LINE_HEIGHT


@lru_cache(maxsize=1)
def stylesheet() -> StyleSheet1:
    """构建并缓存全部段落样式。"""
    fonts.register_fonts()
    song, hei = fonts.song(), fonts.hei()
    ss = StyleSheet1()

    def add(name: str, **kw: object) -> None:
        size = float(kw.pop("fontSize", 12))  # type: ignore[arg-type]
        ss.add(
            ParagraphStyle(
                name,
                fontName=str(kw.pop("fontName", song)),
                fontSize=size,
                leading=float(kw.pop("leading", _leading(size))),  # type: ignore[arg-type]
                **kw,
            )
        )

    # 正文 / content（§6.4）
    add("body", fontName=song, fontSize=12)
    add("body_center", fontName=song, fontSize=12, alignment=TA_CENTER)
    # content 节点：与正文同格式，上下 1em 内边距（§6.4）
    add("content", fontName=song, fontSize=12, spaceBefore=12, spaceAfter=12)

    # 封面（§3.1）
    add("cover_title", fontName=hei, fontSize=22, alignment=TA_CENTER, leading=30, spaceAfter=18)
    add("cover_sub", fontName=song, fontSize=12, alignment=TA_CENTER, spaceAfter=2)
    add(
        "cover_status_draft",
        fontName=song,
        fontSize=12,
        alignment=TA_CENTER,
        textColor=Color(0.5, 0.5, 0.5),
        spaceBefore=6,
    )
    add(
        "cover_status_archived",
        fontName=hei,
        fontSize=14,
        alignment=TA_CENTER,
        textColor=Color(220 / 255, 38 / 255, 38 / 255),
        spaceBefore=6,
    )

    # 章节标题（§6.2）
    add("h1", fontName=hei, fontSize=16, spaceBefore=24, spaceAfter=8)
    add("h2", fontName=hei, fontSize=14, spaceBefore=18, spaceAfter=6)
    add("h3", fontName=hei, fontSize=12, spaceBefore=14, spaceAfter=4)

    # TOC（§4.2）
    add("toc_title", fontName=hei, fontSize=16, spaceAfter=12)
    add("toc_l1", fontName=hei, fontSize=14, leading=22)
    add("toc_l2", fontName=song, fontSize=12, leading=20, leftIndent=14)
    add("toc_l3", fontName=song, fontSize=12, leading=20, leftIndent=28)

    # 修订记录（§5）
    add("section_title", fontName=hei, fontSize=16, spaceAfter=12)
    add("table_cell", fontName=song, fontSize=10.5, leading=15)
    add("table_head", fontName=hei, fontSize=10.5, leading=15, textColor=black)

    # 步骤（§6.3）
    add("step_title", fontName=hei, fontSize=14, spaceBefore=10, spaceAfter=4)
    add("step_placeholder", fontName=song, fontSize=12, spaceBefore=2)
    add("step_mark", fontName=song, fontSize=11, textColor=Color(0.25, 0.25, 0.25))

    # 警示 / hold-point（§7）
    add("alert_title", fontName=hei, fontSize=12, spaceAfter=2)
    add("alert_body", fontName=song, fontSize=12)
    add(
        "hold_title",
        fontName=hei,
        fontSize=14,
        textColor=Color(220 / 255, 38 / 255, 38 / 255),
        spaceAfter=4,
    )

    # 页眉（§6.1）
    add("header_left", fontName=song, fontSize=11, alignment=TA_LEFT, leading=14)
    add("header_right", fontName=song, fontSize=10, alignment=TA_RIGHT, leading=13)

    # 占位 / 空状态（§12）
    add(
        "placeholder_muted",
        fontName=song,
        fontSize=12,
        alignment=TA_CENTER,
        textColor=Color(0.5, 0.5, 0.5),
        spaceBefore=12,
    )
    return ss


def s(name: str) -> ParagraphStyle:
    """取样式。"""
    return stylesheet()[name]
