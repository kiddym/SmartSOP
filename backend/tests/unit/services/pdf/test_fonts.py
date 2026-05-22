"""pdf.fonts 单测（Q359）：注册幂等 + 逻辑名可用 + CID 回退保证离线渲染。"""

from __future__ import annotations

from io import BytesIO

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.services.pdf import fonts


def test_register_is_idempotent() -> None:
    fonts.register_fonts()
    fonts.register_fonts()  # 第二次不应抛
    registered = set(pdfmetrics.getRegisteredFontNames())
    assert fonts.song() in registered
    assert fonts.hei() in registered
    assert fonts.song_bold() in registered
    assert fonts.hei_bold() in registered
    # mono 用 reportlab 标准 14 字体 Courier，无需显式注册即可 setFont
    assert fonts.mono() == "Courier"


def test_uses_bundled_ttf_not_cid_fallback() -> None:
    """字体资产已内置（H1/Q359）：注册 Noto TTF 而非回退 CID，保证加粗中文=黑体。"""
    fonts.register_fonts()
    assert fonts.song() == "SmartSong"
    assert fonts.hei() == "SmartHei"
    assert fonts.song_bold() == fonts.hei()  # 宋体加粗渲染为黑体


def test_logical_fonts_render_chinese() -> None:
    fonts.register_fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for name in (fonts.song(), fonts.hei(), fonts.mono()):
        c.setFont(name, 12)
        c.drawString(72, 700, "启动 SOP 程序编号 QC-00001 Rev.2 ABC123")
    c.save()
    data = buf.getvalue()
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")


def test_family_registered_for_bold_inline() -> None:
    """正文字体注册了字体家族，<b> 才能在 Paragraph 内联切换为黑体（§8）。"""
    fonts.register_fonts()
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    style = ParagraphStyle("t", fontName=fonts.song(), fontSize=12)
    para = Paragraph("正文 <b>加粗中文</b> 继续", style)
    buf = BytesIO()
    c = canvas.Canvas(buf)
    para.wrap(400, 200)
    para.drawOn(c, 72, 700)
    c.save()
    assert buf.getvalue().startswith(b"%PDF-")
