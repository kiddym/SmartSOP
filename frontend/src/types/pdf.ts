// PDF 分页 layout 类型，与后端 app/schemas/pdf.py（§59.2·Q360）对齐。
// 前端预览层据此把内容切到对应「纸张」容器，与下载版页码一致（Q235）。

export interface PdfSectionInfo {
  start_page: number
  page_count: number
}

export interface PdfTocEntry {
  chapter_id: string
  code: string
  title: string
  level: number
  physical_page: number | null
  display_page: string // TOC 列应印的正文阿拉伯页码（Q46）
}

export interface PdfLayout {
  total_pages: number
  sections: Record<string, PdfSectionInfo> // cover/toc/revision/content/attachments
  page_labels: string[] // 每物理页页眉右列第 3 行 P（封面=''）
  toc_entries: PdfTocEntry[]
  chapters: Record<string, number> // chapter_id → 物理页
  steps: Record<string, number> // step_id → 物理页
  attachments_page: number | null
  debug?: Record<string, unknown> | null
}
