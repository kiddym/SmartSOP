"""pdf.html_render 单测（Q363）：特殊块 / 表格 / 嵌套表降级 / 图片占位 / 内联。"""

from __future__ import annotations

import logging
from io import BytesIO

from reportlab.platypus import Image, SimpleDocTemplate, Table

from app.services.pdf import fonts
from app.services.pdf.html_render import render_html


def _render_to_pdf(flowables: list) -> bytes:
    fonts.register_fonts()
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=(595, 842)).build(list(flowables))
    return buf.getvalue()


def test_plain_paragraphs() -> None:
    fl = render_html("<p>第一段</p><p>第二段 <b>加粗</b></p>", {})
    assert len(fl) == 2
    assert _render_to_pdf(fl).startswith(b"%PDF-")


def test_special_blocks_produce_boxes() -> None:
    html = (
        '<div class="note-block">提示内容</div>'
        '<div class="caution-block">设备风险</div>'
        '<div class="warning-block">人身风险</div>'
        '<div class="hold-point">需签名</div>'
        '<div class="signature-bar" data-columns="3"></div>'
    )
    fl = render_html(html, {})
    # note/caution/warning/signature → Table；hold-point → KeepTogether
    assert len(fl) == 5
    assert _render_to_pdf(fl).startswith(b"%PDF-")


def test_table_rendered() -> None:
    html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
    fl = render_html(html, {})
    assert any(isinstance(f, Table) for f in fl)
    assert _render_to_pdf(fl).startswith(b"%PDF-")


def test_nested_table_degrades_with_warning(caplog) -> None:
    html = "<table><tr><td>外<table><tr><td>内1</td></tr></table></td></tr></table>"
    with caplog.at_level(logging.WARNING, logger="app.services.pdf"):
        fl = render_html(html, {})
    assert any("嵌套表格" in r.message for r in caplog.records)
    # 仍只产出一个外层表格（内层降级进单元格文本）
    assert sum(isinstance(f, Table) for f in fl) == 1


def test_missing_image_placeholder() -> None:
    fl = render_html(
        '<img src="/api/v1/procedures/p1/assets/00000000-0000-0000-0000-000000000000">', {}
    )
    assert len(fl) == 1
    # 资产字典为空 → 占位段落（非 Image）
    assert not isinstance(fl[0], Image)


def test_real_image_renders(tmp_path) -> None:
    from PIL import Image as PILImage

    bio = BytesIO()
    PILImage.new("RGB", (40, 20), (10, 20, 30)).save(bio, format="PNG")
    aid = "11111111-1111-1111-1111-111111111111"
    assets = {aid: (bio.getvalue(), "image/png")}
    fl = render_html(f'<img src="/api/v1/procedures/p1/assets/{aid}">', assets)
    assert any(isinstance(f, Image) for f in fl)


def test_unknown_tags_degrade_to_text() -> None:
    fl = render_html("<section><custom>文字</custom></section>", {})
    assert _render_to_pdf(fl).startswith(b"%PDF-")
