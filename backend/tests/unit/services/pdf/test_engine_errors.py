"""pdf.engine 超时 / 异常归一（§59.4·Q362）+ 水印 / 自定义 flowable。"""

from __future__ import annotations

import time
from io import BytesIO

import pytest
from fastapi import HTTPException
from reportlab.pdfgen import canvas

from app.services.pdf import engine, flowables, fonts
from app.services.pdf.context import ProcedureData, RenderData


def _data() -> RenderData:
    from datetime import UTC, datetime

    proc = ProcedureData(
        id="p1",
        code="QC-1",
        name="x",
        version=1,
        status="DRAFT",
        level_of_use="reference",
        risk_level=1,
        quality_level=1,
        description="",
        custom_values={},
        version_update_notes="",
        version_change_log=[],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        archived_at=None,
        deprecated_at=None,
        folder_full_path="x",
        signoff_enabled=False,
    )
    return RenderData(proc, [], [], [], [], {})


def test_timeout_raises_504(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "PDF_TIMEOUT_SECONDS", 0.05)

    def _slow(_data: RenderData) -> engine.RenderResult:
        time.sleep(1.0)
        return engine.RenderResult(b"", engine.LayoutInfo())

    monkeypatch.setattr(engine, "_render_iterate", _slow)
    with pytest.raises(HTTPException) as exc:
        engine.render_pdf(_data())
    assert exc.value.status_code == 504
    assert exc.value.detail["code"] == "PDF_TIMEOUT"


def test_internal_error_normalized_to_500(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_data: RenderData) -> engine.RenderResult:
        raise RuntimeError("reportlab boom")

    monkeypatch.setattr(engine, "_render_iterate", _boom)
    with pytest.raises(HTTPException) as exc:
        engine.render_pdf(_data())
    assert exc.value.status_code == 500
    assert exc.value.detail["code"] == "PDF_GENERATION_FAILED"


def test_watermark_draws_for_draft_not_published() -> None:
    fonts.register_fonts()

    def _bytes(status: str) -> bytes:
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(595, 842))
        flowables.draw_watermark(c, status, 595, 842)
        c.drawString(72, 72, "x")
        c.save()
        return buf.getvalue()

    draft = _bytes("DRAFT")
    published = _bytes("PUBLISHED")
    archived = _bytes("ARCHIVED")
    # 草稿 / 作废有水印内容 → 体积大于无水印的已发布
    assert len(draft) > len(published)
    assert len(archived) > len(published)


def test_alert_box_and_holdpoint_and_signature_render() -> None:
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    from app.services.pdf.styles import s

    body = [Paragraph("内容", s("alert_body"))]
    items = [
        flowables.alert_box("note", body),
        flowables.alert_box("caution", body),
        flowables.alert_box("warning", body),
        flowables.hold_point(body),
        flowables.signature_bar(),
    ]
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=(595, 842)).build(items)
    assert buf.getvalue().startswith(b"%PDF-")
