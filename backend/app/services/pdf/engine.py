"""PDF 渲染引擎（pdf-rendering §11 / §59.3·Q361 / §59.4·Q362）。

单引擎双产出（download bytes + layout）；迭代收敛多遍构建（TOC 列正文页码 ↔ 正文
分页互依）；ThreadPoolExecutor 硬超时 60s；异常归一 PDF_GENERATION_FAILED。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from io import BytesIO

from fastapi import HTTPException
from reportlab.platypus import Flowable, NextPageTemplate, PageBreak

from app.services.pdf import sections, styles
from app.services.pdf.context import RenderData
from app.services.pdf.document import ProcedureDocTemplate, to_roman
from app.services.pdf.errors import pdf_failed, pdf_timeout
from app.services.pdf.flowables import PageMarker

logger = logging.getLogger("app.services.pdf")

PDF_TIMEOUT_SECONDS = 60
MAX_ITERS = 6


@dataclass
class TocEntryInfo:
    chapter_id: str
    code: str
    title: str
    level: int
    physical_page: int | None
    display_page: str


@dataclass
class LayoutInfo:
    total_pages: int = 0
    cover_pages: int = 0
    front_pages: int = 0
    content_pages: int = 0
    section_starts: dict[str, int] = field(
        default_factory=dict
    )  # cover/toc/revision/content/attachments
    page_labels: list[str] = field(default_factory=list)
    toc_entries: list[TocEntryInfo] = field(default_factory=list)
    chapters: dict[str, int] = field(default_factory=dict)
    steps: dict[str, int] = field(default_factory=dict)
    attachments_page: int | None = None


@dataclass
class RenderResult:
    pdf_bytes: bytes
    layout: LayoutInfo


# --------------------------------------------------------------------------- #
def _assemble_story(data: RenderData, toc_pages: dict[str, str]) -> list[Flowable]:
    story: list[Flowable] = []
    story += sections.build_cover(data)
    story.append(NextPageTemplate("front"))
    story.append(PageBreak())
    story.append(PageMarker(("section", "toc")))
    story += sections.build_toc(data, toc_pages)
    story.append(PageBreak())
    story.append(PageMarker(("section", "revision")))
    story += sections.build_revision(data)
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())
    story.append(PageMarker(("section", "content")))
    content_fl, _has_attach = sections.build_content(data)
    story += content_fl
    return story


def _build_once(
    data: RenderData, totals: dict[str, int], toc_pages: dict[str, str]
) -> tuple[bytes, ProcedureDocTemplate]:
    buf = BytesIO()
    doc = ProcedureDocTemplate(
        buf,
        status=data.procedure.status,
        header_title=data.procedure.name,
        header_code=data.procedure.code,
        header_version=data.procedure.version,
        totals=totals,
    )
    doc.build(_assemble_story(data, toc_pages))
    return buf.getvalue(), doc


def _extract_layout(data: RenderData, doc: ProcedureDocTemplate) -> LayoutInfo:
    secs = doc.page_sections
    total = max(secs) if secs else 1
    cover = sum(1 for v in secs.values() if v == "cover")
    front = sum(1 for v in secs.values() if v == "front")
    content = sum(1 for v in secs.values() if v == "content")
    ep = doc.element_pages

    page_labels: list[str] = []
    for p in range(1, total + 1):
        v = secs.get(p)
        if v == "front":
            page_labels.append(to_roman(p - cover))
        elif v == "content":
            page_labels.append(str(p - cover - front))
        else:  # cover / 未知 → 无页眉页码
            page_labels.append("")

    toc_start = ep.get(("section", "toc"))
    revision_start = ep.get(("section", "revision"))
    content_start = ep.get(("section", "content"))
    attach_page = ep.get(("section", "attachments"))

    starts: dict[str, int] = {"cover": 1}
    if toc_start:
        starts["toc"] = toc_start
    if revision_start:
        starts["revision"] = revision_start
    if content_start:
        starts["content"] = content_start
    if attach_page:
        starts["attachments"] = attach_page

    toc_entries: list[TocEntryInfo] = []
    for ch in sections.toc_chapters(data):
        phys = ep.get(("chapter", ch.id))
        disp = str(phys - cover - front) if phys else ""
        code = sections.display_code(ch.code, ch.level, ch.content_type, ch.skip_numbering)
        toc_entries.append(
            TocEntryInfo(
                chapter_id=ch.id,
                code=code,
                title=ch.title,
                level=ch.level,
                physical_page=phys,
                display_page=disp,
            )
        )

    chapters = {k[1]: v for k, v in ep.items() if k[0] == "chapter"}
    steps = {k[1]: v for k, v in ep.items() if k[0] == "step"}
    return LayoutInfo(
        total_pages=total,
        cover_pages=cover,
        front_pages=front,
        content_pages=content,
        section_starts=starts,
        page_labels=page_labels,
        toc_entries=toc_entries,
        chapters=chapters,
        steps=steps,
        attachments_page=attach_page,
    )


def _totals_from(layout: LayoutInfo) -> dict[str, int]:
    return {
        "cover_pages": layout.cover_pages,
        "front_pages": layout.front_pages,
        "total_pages": layout.total_pages,
    }


def _toc_pages_from(layout: LayoutInfo) -> dict[str, str]:
    return {e.chapter_id: e.display_page for e in layout.toc_entries}


def _render_iterate(data: RenderData) -> RenderResult:
    """迭代直至「全量页归属」稳定；末遍即正式 PDF（§59.3）。"""
    prev: LayoutInfo | None = None
    pdf_bytes = b""
    layout = LayoutInfo()
    for _ in range(MAX_ITERS):
        totals = (
            _totals_from(prev) if prev else {"cover_pages": 1, "front_pages": 0, "total_pages": 0}
        )
        toc_pages = _toc_pages_from(prev) if prev else {}
        pdf_bytes, doc = _build_once(data, totals, toc_pages)
        layout = _extract_layout(data, doc)
        if layout == prev:  # 本遍用的是 prev 的页码，已与本遍一致 → 收敛
            return RenderResult(pdf_bytes, layout)
        prev = layout
    logger.warning(
        "pdf layout not converged after %d iterations proc=%s", MAX_ITERS, data.procedure.id
    )
    return RenderResult(pdf_bytes, layout)


def _run_with_timeout(data: RenderData) -> RenderResult:
    styles.stylesheet()  # 主线程预热字体 + 样式（避免 worker 线程首注册竞态）
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_render_iterate, data)
        try:
            return future.result(timeout=PDF_TIMEOUT_SECONDS)
        except FuturesTimeout as exc:
            logger.warning("pdf generation timeout proc=%s", data.procedure.id)
            raise pdf_timeout() from exc
        except HTTPException:
            raise
        except Exception as exc:  # ReportLab 内部异常归一（§13）
            logger.exception("pdf generation failed proc=%s", data.procedure.id)
            raise pdf_failed() from exc


def render_pdf(data: RenderData) -> RenderResult:
    """生成 PDF 字节 + layout（download 用）。"""
    logger.info(
        "pdf generation started proc=%s version=%s", data.procedure.id, data.procedure.version
    )
    result = _run_with_timeout(data)
    logger.info(
        "pdf generation complete proc=%s pages=%s size=%s",
        data.procedure.id,
        result.layout.total_pages,
        len(result.pdf_bytes),
    )
    return result


def compute_layout(data: RenderData) -> LayoutInfo:
    """仅算 layout（pdf-layout 用）；与 download 同引擎，页码一致（§59.2/§59.3）。"""
    return _run_with_timeout(data).layout
