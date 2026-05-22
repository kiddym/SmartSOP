"""PDF 生成子包（pdf-rendering.md / §59）。

对外入口：
- `generate_pdf(db, proc_id)` → (bytes, layout_out, filename)：下载用。
- `get_layout(db, proc_id)` → PdfLayoutOut：pdf-layout 用。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.pdf import PdfLayoutOut
from app.services.pdf import engine, layout
from app.services.pdf.context import load_render_data


def _filename(code: str, version: int) -> str:
    return f"{code}_Rev{version}.pdf"


def generate_pdf(
    db: Session, proc_id: str, *, debug: bool = False
) -> tuple[bytes, PdfLayoutOut, str]:
    """生成下载 PDF：返回 (bytes, layout, filename)。debug=1 时 layout.debug 填诊断。"""
    data = load_render_data(db, proc_id)
    result = engine.render_pdf(data)
    dbg = _debug_payload(result.layout) if debug else None
    out = layout.to_layout_out(result.layout, debug=dbg)
    return result.pdf_bytes, out, _filename(data.procedure.code, data.procedure.version)


def get_layout(db: Session, proc_id: str) -> PdfLayoutOut:
    """仅算分页 layout（pdf-layout 端点）。"""
    data = load_render_data(db, proc_id)
    info = engine.compute_layout(data)
    return layout.to_layout_out(info)


def _debug_payload(info: engine.LayoutInfo) -> dict[str, object]:
    return {
        "cover_pages": info.cover_pages,
        "front_pages": info.front_pages,
        "content_pages": info.content_pages,
        "chapters": info.chapters,
        "steps": info.steps,
    }
