// PDF 预览渲染模型（§34/§59）：把 ProcedureDetail + PdfLayout 组装为逐页「纸张」块。
// 纯函数，便于单测。页号一律取后端 layout（与下载版对齐，Q235）；编号 L1 渲染追加 .0（Q305）。

import { ALERT_TYPES } from '@/utils/editor'
import type { ChapterTreeNode, StepOut } from '@/types/node'
import type { ProcedureDetail, ProcedureFieldView } from '@/types/procedure'
import type { PdfLayout, PdfTocEntry } from '@/types/pdf'

export const LEVEL_OF_USE_LABELS: Record<string, [string, string]> = {
  reference: ['参考使用', 'Reference Use'],
  continuous: ['连续使用', 'Continuous Use'],
  information: ['信息使用', 'Information Use'],
}

export const RISK_LABELS: Record<number, string> = { 1: '低', 2: '中-低', 3: '中', 4: '中-高', 5: '高' }
export const RISK_COLORS: Record<number, string> = {
  1: '#10B981', 2: '#84CC16', 3: '#EAB308', 4: '#F97316', 5: '#DC2626',
}

const CHANGE_TYPE_LABELS: Record<string, string> = {
  publish: '发布', rollback: '回退', deprecate: '废弃', restore: '恢复',
}
const ATTACH_KIND_LABELS: Record<string, string> = {
  video: '视频', image: '图片', document: '文档', doc: '文档', audio: '音频', other: '其他',
}
// 与后端 constants.ATTACHMENT_CHAPTER_NAMES / ATTACHMENT_CHAPTER_TITLE 对齐（§6.6）
const ATTACHMENT_CHAPTER_NAMES = ['附件', 'Attachments']
const ATTACHMENT_CHAPTER_TITLE = '附件 / Attachments'

export type BlockKind = 'chapter' | 'content' | 'step'

export interface PreviewBlock {
  key: string
  kind: BlockKind
  page: number
  level?: number
  code?: string
  title?: string
  html?: string
  step?: StepOut
}

export interface ContentPage {
  page: number
  label: string
  blocks: PreviewBlock[]
}

export interface RevisionRow {
  version: string
  changeType: string
  changedAt: string
  desc: string
}

export interface PreviewModel {
  layout: PdfLayout
  toc: PdfTocEntry[]
  revision: RevisionRow[]
  contentPages: ContentPage[]
  coverFields: CoverFieldRow[]
  attachments: AttachmentRow[]
  attachmentsPage: number | null
  // 附件区段标题：用户自建「附件」章节时为 null（标题已在正文章节渲染），否则为虚拟章节标题
  attachmentChapterTitle: string | null
}

export interface AttachmentRow {
  index: number
  fileName: string
  size: string
  mime: string
  date: string
  description: string
}

export interface CoverFieldRow {
  name: string
  value: string
}

export function displayCode(code: string, level: number, contentType: string, skip: boolean): string {
  if (skip || contentType === 'content' || !code) return ''
  return level === 1 ? `${code}.0` : code
}

export function fmtDate(iso: string | null | undefined): string {
  return iso ? String(iso).slice(0, 10) : ''
}

export function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(2)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

export function changeTypeLabel(entry: Record<string, unknown>): string {
  const ct = String(entry.change_type ?? '')
  let label = CHANGE_TYPE_LABELS[ct] ?? ct
  if (ct === 'rollback' && entry.rollback_from_version) {
    label += `（源 v${entry.rollback_from_version}）`
  }
  return label
}

// 15 型执行占位符文案（与后端 sections._form_placeholder 对齐，§6.3）。
export function execText(step: StepOut): string {
  const s = step.input_schema as Record<string, unknown>
  const t = String(s.type ?? 'COMMON').toUpperCase()
  if ((ALERT_TYPES as readonly string[]).includes(t)) return ''
  const opts = Array.isArray(s.options)
    ? (s.options as unknown[]).map((o) =>
        typeof o === 'object' && o ? String((o as Record<string, unknown>).label ?? '') : String(o),
      )
    : []
  switch (t) {
    case 'NONE':
      return ''
    case 'COMMON':
      return '□ 已完成'
    case 'CHECK':
      return `执行结果:  □ ${s.pass_label ?? '通过'}    □ ${s.fail_label ?? '不通过'}`
    case 'YESNO':
      return '□ 是    □ 否'
    case 'NUMBER': {
      const rng = s.min != null || s.max != null ? `  (合格范围 ${s.min}~${s.max})` : ''
      return `${s.label ?? '数值'}: __________ ${s.unit ?? ''}${rng}`
    }
    case 'METER':
      return `${s.label ?? '读数'}: __________ ${s.unit ?? ''}`
    case 'CHECKBOX':
      return (opts.length ? opts : ['选项1', '选项2']).map((o) => `□ ${o}`).join('   ')
    case 'RADIO':
      return (opts.length ? opts : ['选项1', '选项2']).map((o) => `○ ${o}`).join('   ')
    case 'UPLOAD':
      return '附件: ____________（见附页 / 粘贴）'
    case 'SIGNATURE':
      return '签名: ________________'
    case 'DATE':
      return '日期: ______ 年 ___ 月 ___ 日'
    case 'PHOTO':
      return '［照片粘贴区］'
    default:
      return '□ 已完成'
  }
}

export function attachmentMarkText(mark: { filename?: string; name?: string; kind?: string; note?: string }): string {
  const name = mark.filename || mark.name || ''
  const kind = ATTACH_KIND_LABELS[mark.kind ?? 'other'] ?? '其他'
  let text = `▶ 附件: ${name}（${kind}）`
  if (mark.note) text += ` — ${mark.note}`
  return text
}

// 修订记录（仅里程碑 publish/rollback/deprecate/restore，§5.1）
export function buildRevision(detail: ProcedureDetail): RevisionRow[] {
  const log = (detail.procedure.version_change_log ?? []) as Array<Record<string, unknown>>
  const notes = detail.procedure.version_update_notes ?? ''
  const ver = detail.procedure.version
  return log
    .filter((e) => ['publish', 'rollback', 'deprecate', 'restore'].includes(String(e.change_type)))
    .map((e) => {
      const parts: string[] = []
      if (e.description) parts.push(String(e.description))
      if (e.reason) parts.push(String(e.reason))
      if (e.version === ver && notes.trim()) parts.push(notes.trim())
      return {
        version: String(e.version ?? ''),
        changeType: changeTypeLabel(e),
        changedAt: String(e.changed_at ?? '').slice(0, 10),
        desc: parts.length ? parts.join('\n') : '—',
      }
    })
}

// 内容区块按 backend 顺序遍历并据 layout 映射页号（chapter/step 取映射，content 继承当前页）。
function walkContent(detail: ProcedureDetail, layout: PdfLayout): PreviewBlock[] {
  const blocks: PreviewBlock[] = []
  const stepsByChapter = new Map<string | null, StepOut[]>()
  for (const st of detail.steps) {
    const list = stepsByChapter.get(st.chapter_id) ?? []
    list.push(st)
    stepsByChapter.set(st.chapter_id, list)
  }
  for (const list of stepsByChapter.values()) list.sort((a, b) => a.sort_order - b.sort_order)

  const contentStart = layout.sections.content?.start_page ?? 1
  let current = contentStart

  const renderChapter = (ch: ChapterTreeNode): void => {
    if (ch.content_type === 'content') {
      blocks.push({ key: `c-${ch.id}`, kind: 'content', page: current, html: ch.rich_content })
      return
    }
    current = layout.chapters[ch.id] ?? current
    blocks.push({
      key: `ch-${ch.id}`,
      kind: 'chapter',
      page: current,
      level: ch.level,
      code: displayCode(ch.code, ch.level, ch.content_type, ch.skip_numbering),
      title: ch.title,
    })
    for (const child of ch.children) renderChapter(child)
    for (const st of stepsByChapter.get(ch.id) ?? []) renderStep(st)
  }

  const renderStep = (st: StepOut): void => {
    current = layout.steps[st.id] ?? current
    blocks.push({
      key: `st-${st.id}`,
      kind: 'step',
      page: current,
      code: st.skip_numbering ? '' : st.code,
      title: st.title,
      step: st,
    })
  }

  for (const ch of detail.chapters) renderChapter(ch)
  for (const st of stepsByChapter.get(null) ?? []) renderStep(st)
  return blocks
}

function buildAttachments(detail: ProcedureDetail): AttachmentRow[] {
  const list = (detail.attachments ?? []) as Array<Record<string, unknown>>
  return list.map((a, i) => ({
    index: i + 1,
    fileName: String(a.file_name ?? ''),
    size: humanSize(Number(a.size_bytes ?? 0)),
    mime: String(a.mime_type ?? ''),
    date: fmtDate(String(a.created_at ?? '')),
    description: String(a.description ?? '') || '—',
  }))
}

// 自定义字段值解析（与后端 context._resolve_field_value 对齐，§3.1/Q257）。
export function resolveFieldValue(field: ProcedureFieldView, raw: unknown): string {
  if (raw == null || raw === '' || (Array.isArray(raw) && raw.length === 0)) return ''
  const opts = new Map<string, string>()
  for (const o of field.options ?? []) {
    opts.set(o.value, o.label)
  }
  if (field.field_type === 'select') return opts.get(String(raw)) ?? String(raw)
  if (field.field_type === 'multi_select' || field.field_type === 'checkbox') {
    return Array.isArray(raw)
      ? raw.map((v) => opts.get(String(v)) ?? String(v)).join('、')
      : (opts.get(String(raw)) ?? String(raw))
  }
  return String(raw)
}

// 封面自定义字段：仅 show_on_cover 且有值（与后端 cover_fields 同口径，§3.1）。
export function coverFieldRows(detail: ProcedureDetail): CoverFieldRow[] {
  const cv = detail.procedure.custom_values ?? {}
  return detail.fields
    .filter((f) => f.show_on_cover)
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((f) => ({ name: f.name, value: resolveFieldValue(f, cv[f.key]) }))
    .filter((r) => r.value !== '')
}

// 附件区段标题：用户自建「附件」章节 → null（标题在正文章节已渲染）；否则虚拟章节 {n}.0（§6.6）。
function attachmentChapterTitle(detail: ProcedureDetail): string | null {
  const top = detail.chapters ?? []
  const hasUserChapter = top.some(
    (c) => c.content_type === 'chapter' && ATTACHMENT_CHAPTER_NAMES.includes(c.title.trim()),
  )
  if (hasUserChapter) return null
  let maxSeq = 0
  for (const c of top) {
    if (c.content_type === 'chapter' && !c.skip_numbering && /^\d+$/.test(c.code)) {
      maxSeq = Math.max(maxSeq, Number(c.code))
    }
  }
  return `${maxSeq + 1}.0 ${ATTACHMENT_CHAPTER_TITLE}`
}

export function buildModel(detail: ProcedureDetail, layout: PdfLayout): PreviewModel {
  const blocks = walkContent(detail, layout)
  const contentSection = layout.sections.content
  const contentStart = contentSection?.start_page ?? 1
  const contentCount = contentSection?.page_count ?? 1
  const pages: ContentPage[] = []
  for (let i = 0; i < contentCount; i++) {
    const page = contentStart + i
    pages.push({
      page,
      label: layout.page_labels[page - 1] ?? String(page - contentStart + 1),
      blocks: blocks.filter((b) => b.page === page),
    })
  }
  // 兜底：未落入任何页的块（页号超界）并入末页，保证不丢内容
  const placed = new Set(pages.flatMap((p) => p.blocks.map((b) => b.key)))
  const orphan = blocks.filter((b) => !placed.has(b.key))
  if (orphan.length && pages.length) pages[pages.length - 1].blocks.push(...orphan)
  else if (orphan.length) pages.push({ page: contentStart, label: '1', blocks: orphan })

  const attachments = buildAttachments(detail)
  return {
    layout,
    toc: layout.toc_entries,
    revision: buildRevision(detail),
    contentPages: pages,
    coverFields: coverFieldRows(detail),
    attachments,
    attachmentsPage: layout.attachments_page,
    attachmentChapterTitle: attachments.length ? attachmentChapterTitle(detail) : null,
  }
}
