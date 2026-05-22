"""PDF 分页 layout schema（api-specification §5.2 / §59.2·Q360）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SectionInfo(BaseModel):
    """区段物理页边界。"""

    start_page: int
    page_count: int


class TocEntry(BaseModel):
    """TOC 条目（仅 chapter 且 skip_numbering=false，§4.1）。"""

    chapter_id: str
    code: str
    title: str
    level: int
    physical_page: int | None
    display_page: str  # TOC 列应印的正文阿拉伯页码（Q46）


class PdfLayoutOut(BaseModel):
    """GET /procedures/{id}/pdf-layout 响应（前端预览逐页复刻，与下载版页码一致）。"""

    total_pages: int
    sections: dict[str, SectionInfo] = Field(
        default_factory=dict
    )  # cover/toc/revision/content/attachments
    page_labels: list[str] = Field(default_factory=list)  # 每物理页页眉右列第3行 P
    toc_entries: list[TocEntry] = Field(default_factory=list)
    chapters: dict[str, int] = Field(default_factory=dict)  # chapter_id → 物理页
    steps: dict[str, int] = Field(default_factory=dict)  # step_id → 物理页
    attachments_page: int | None = None
    debug: dict[str, object] | None = None  # ?debug=1 时填 dry-run 诊断
