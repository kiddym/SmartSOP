// PDF 预览渲染模型（§34/§59）：把 ProcedureDetail + PdfLayout 组装为逐页「纸张」块。
// 纯函数，便于单测。页号一律取后端 layout（与下载版对齐，Q235）；编号 L1 渲染追加 .0（Q305）。

import { ALERT_TYPES } from '@/utils/editor'
import type { Node } from '@/types/node'
import { nodeTitle } from '@/utils/nodeTree'
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
  // step 块：node 携带 input_schema/attachment_marks（execText/标记/警示渲染）；
  // 标题在 block.title，正文（body 去掉首块标题后的余 HTML）在 stepContent。
  step?: Node
  stepContent?: string
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
  signoffEnabled: boolean
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

// 渲染编号（与后端 sections.display_code 对齐）：skip / 空 code → ''；L1 章节追加 .0（§47/Q305）。
export function displayCode(code: string, level: number, skip: boolean): string {
  if (skip || !code) return ''
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
export function execText(step: Node): string {
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

// body → (首块纯文本=标题, 其余块 HTML=正文)，镜像后端 _split_first_block（pdf/context.py）。
// 用浏览器 DOMParser；标题取首块 textContent（nodeTitle 同口径但带占位回退，这里 step 标题不需要占位）。
// 解析失败 / 无块级子元素：整段当标题，正文为空。
function splitBody(body: string): { title: string; content: string } {
  if (!body || !body.trim()) return { title: '', content: '' }
  const doc = new DOMParser().parseFromString(body, 'text/html')
  const children = Array.from(doc.body.children)
  if (children.length === 0) {
    // 裸文本（无块级子元素）：整段当标题
    return { title: (doc.body.textContent ?? '').trim(), content: '' }
  }
  const first = children[0]
  const title = (first.textContent ?? '').trim()
  const content = children.slice(1).map((c) => c.outerHTML).join('')
  return { title, content }
}

// 内容区块按 backend 顺序遍历并据 layout 映射页号（与 sections._render_chapter/_render_step 对齐）。
// 数据源为扁平 ProcedureNode 列表（按 sort_order 升序）；按 parent_id 分组重建树（镜像 pdf/context.py
// load_render_data）。heading 节点=章节（只出标题）；其下非 heading 节点按文档序：
//   kind==='step'  → 步骤渲染（body 切首块标题 + 余正文，取 layout.steps 映射）
//   其余（content） → 内联富文本（PDF 不出编号、不出 title，继承当前页）
// 遍历序：章节 → 其子章节 → 其子内容/步骤（与后端 tree walk 一致）；layout 已按 node id 键化（B2b）。
function walkContent(nodes: Node[], layout: PdfLayout): PreviewBlock[] {
  const blocks: PreviewBlock[] = []
  // 按 parent_id 分组（nodes 已按 sort_order 升序 → 同父保持文档序）。
  const childrenByParent = new Map<string | null, Node[]>() // heading 节点
  const itemsByParent = new Map<string | null, Node[]>() // 非 heading 节点（content/step）
  for (const n of nodes) {
    const bucket = n.heading_level !== null ? childrenByParent : itemsByParent
    const list = bucket.get(n.parent_id) ?? []
    list.push(n)
    bucket.set(n.parent_id, list)
  }

  const contentStart = layout.sections.content?.start_page ?? 1
  let current = contentStart

  const renderChapter = (ch: Node): void => {
    current = layout.chapters[ch.id] ?? current
    const level = ch.heading_level ?? 1
    blocks.push({
      key: `ch-${ch.id}`,
      kind: 'chapter',
      page: current,
      level,
      code: displayCode(ch.code, level, ch.skip_numbering),
      title: nodeTitle(ch),
    })
    for (const child of childrenByParent.get(ch.id) ?? []) renderChapter(child)
    for (const item of itemsByParent.get(ch.id) ?? []) renderItem(item)
  }

  const renderItem = (node: Node): void => {
    if (node.kind !== 'step') {
      // 内容块在 PDF 渲染时不出编号、不出 title；继承当前页，不取 layout.steps 映射。
      blocks.push({ key: `c-${node.id}`, kind: 'content', page: current, html: node.body })
      return
    }
    current = layout.steps[node.id] ?? current
    const { title, content } = splitBody(node.body)
    blocks.push({
      key: `st-${node.id}`,
      kind: 'step',
      page: current,
      code: node.skip_numbering ? '' : node.code,
      title,
      step: node,
      stepContent: content,
    })
  }

  for (const ch of childrenByParent.get(null) ?? []) renderChapter(ch)
  for (const item of itemsByParent.get(null) ?? []) renderItem(item)
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
// 顶层章节 = parent_id===null 的 heading 节点（heading_level 非空）。
function attachmentChapterTitle(nodes: Node[]): string | null {
  const top = nodes.filter((n) => n.parent_id === null && n.heading_level !== null)
  const hasUserChapter = top.some((c) => ATTACHMENT_CHAPTER_NAMES.includes(nodeTitle(c).trim()))
  if (hasUserChapter) return null
  let maxSeq = 0
  for (const c of top) {
    if (!c.skip_numbering && /^\d+$/.test(c.code)) {
      maxSeq = Math.max(maxSeq, Number(c.code))
    }
  }
  return `${maxSeq + 1}.0 ${ATTACHMENT_CHAPTER_TITLE}`
}

export function buildModel(detail: ProcedureDetail, nodes: Node[], layout: PdfLayout): PreviewModel {
  const blocks = walkContent(nodes, layout)
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
    attachmentChapterTitle: attachments.length ? attachmentChapterTitle(nodes) : null,
    signoffEnabled: detail.procedure.signoff_enabled,
  }
}
