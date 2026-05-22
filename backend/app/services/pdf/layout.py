"""LayoutInfo → PdfLayoutOut（§59.2·Q360）。"""

from __future__ import annotations

from app.schemas.pdf import PdfLayoutOut, SectionInfo, TocEntry
from app.services.pdf.engine import LayoutInfo


def to_layout_out(info: LayoutInfo, *, debug: dict[str, object] | None = None) -> PdfLayoutOut:
    sections: dict[str, SectionInfo] = {}
    starts = info.section_starts
    total = info.total_pages

    def span(start: int | None, nxt: int | None) -> int:
        if start is None:
            return 0
        end = nxt if nxt is not None else total + 1
        return max(0, end - start)

    cover_start = starts.get("cover", 1)
    toc_start = starts.get("toc")
    revision_start = starts.get("revision")
    content_start = starts.get("content")

    sections["cover"] = SectionInfo(start_page=cover_start, page_count=info.cover_pages or 1)
    if toc_start is not None:
        sections["toc"] = SectionInfo(
            start_page=toc_start, page_count=span(toc_start, revision_start)
        )
    if revision_start is not None:
        sections["revision"] = SectionInfo(
            start_page=revision_start, page_count=span(revision_start, content_start)
        )
    if content_start is not None:
        sections["content"] = SectionInfo(start_page=content_start, page_count=info.content_pages)

    toc_entries = [
        TocEntry(
            chapter_id=e.chapter_id,
            code=e.code,
            title=e.title,
            level=e.level,
            physical_page=e.physical_page,
            display_page=e.display_page,
        )
        for e in info.toc_entries
    ]
    return PdfLayoutOut(
        total_pages=total,
        sections=sections,
        page_labels=info.page_labels,
        toc_entries=toc_entries,
        chapters=info.chapters,
        steps=info.steps,
        attachments_page=info.attachments_page,
        debug=debug,
    )
