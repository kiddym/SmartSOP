// 编辑器纯函数工具：客户端编号镜像（§47）、Q25 新增按钮、回退文案、表单型元数据。
// recomputeCodes 必须与后端 numbering_service.recompute 逐行等价（单测锁定）。

import type {
  AddButtonState,
  EditorChapter,
  EditorStep,
  FormType,
  NodeKind,
} from '@/types/node'

// ---- 临时 id（新建节点；后端按「不在既有集合」判定为新建并返回 id 映射） ---- //

export function genTempId(): string {
  const uuid =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36)
  return `temp-${uuid}`
}

export function isTempId(id: string): boolean {
  return id.startsWith('temp-')
}

// ---- 客户端编号（§47 镜像）：返回内部 code（不含 .0 / #） ---- //

export interface CodeMaps {
  chapterCodes: Map<string, string>
  stepCodes: Map<string, string>
}

function sortByOrderThenId<T extends { sort_order: number; id: string }>(group: T[]): void {
  group.sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
}

export function recomputeCodes(chapters: EditorChapter[], steps: EditorStep[]): CodeMaps {
  const chapterCodes = new Map<string, string>()
  const stepCodes = new Map<string, string>()

  const children = new Map<string | null, EditorChapter[]>()
  for (const ch of chapters) {
    const list = children.get(ch.parent_id) ?? []
    list.push(ch)
    children.set(ch.parent_id, list)
  }
  const stepsByChapter = new Map<string | null, EditorStep[]>()
  for (const st of steps) {
    const list = stepsByChapter.get(st.chapter_id) ?? []
    list.push(st)
    stepsByChapter.set(st.chapter_id, list)
  }
  for (const group of children.values()) sortByOrderThenId(group)
  for (const group of stepsByChapter.values()) sortByOrderThenId(group)

  function numberSteps(chapterId: string | null, prefix: string, silent: boolean): void {
    let seq = 0
    for (const st of stepsByChapter.get(chapterId) ?? []) {
      if (silent || st.skip_numbering) {
        stepCodes.set(st.id, '')
        continue
      }
      seq += 1
      stepCodes.set(st.id, prefix ? `${prefix}.${seq}` : String(seq))
    }
  }

  function numberChapters(parentId: string | null, parentCode: string, silent: boolean): void {
    let seq = 0
    for (const ch of children.get(parentId) ?? []) {
      if (ch.content_type === 'content') {
        chapterCodes.set(ch.id, '')
        numberChapters(ch.id, '', true)
        numberSteps(ch.id, '', true)
        continue
      }
      if (silent || ch.skip_numbering) {
        chapterCodes.set(ch.id, '')
        numberChapters(ch.id, '', true)
        numberSteps(ch.id, '', true)
        continue
      }
      seq += 1
      const code = parentCode ? `${parentCode}.${seq}` : String(seq)
      chapterCodes.set(ch.id, code)
      numberChapters(ch.id, code, false)
      numberSteps(ch.id, code, false)
    }
  }

  numberChapters(null, '', false)
  numberSteps(null, '', false) // 根级 step（与根 chapter 互斥，Q25）
  return { chapterCodes, stepCodes }
}

// 显示串：跳号 → '#'（§47/Q307）；L1 章节 → 'N.0'（render-only，Q305）；content / 静默子树 → ''。
export function formatCode(params: {
  kind: NodeKind
  level: number
  code: string
  skipNumbering: boolean
}): string {
  if (params.skipNumbering) return '#'
  if (params.code === '') return ''
  if (params.kind === 'chapter' && params.level === 1) return `${params.code}.0`
  return params.code
}

// ---- Q25 新增按钮互斥 ---- //

export function getAddButtonState(childKinds: NodeKind[]): AddButtonState {
  const types = new Set(childKinds)
  return {
    canAddChapter: !types.has('step'),
    canAddContent: !types.has('step'),
    canAddStep: !types.has('chapter') && !types.has('content'),
  }
}

// ---- 富文本 → 纯文本 / 首行预览（树节点回退文案） ---- //

const BLOCK_CLOSE = /<\/(p|div|li|tr|h[1-6]|ul|ol|table|blockquote)\s*>/gi
const BR_TAG = /<br\s*\/?>/gi
const ANY_TAG = /<[^>]+>/g
const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&#39;': "'",
  '&nbsp;': ' ',
}

export function htmlToText(html: string): string {
  return html
    .replace(BLOCK_CLOSE, '\n')
    .replace(BR_TAG, '\n')
    .replace(ANY_TAG, '')
    .replace(/&[a-z#0-9]+;/gi, (m) => ENTITIES[m.toLowerCase()] ?? m)
}

export function firstLinePreview(text: string, max = 50): string {
  const line = text
    .split('\n')
    .map((s) => s.trim())
    .find((s) => s.length > 0)
  if (!line) return ''
  return line.length > max ? `${line.slice(0, max)}…` : line
}

// 树节点显示文本：title 优先，空则按类型回退（§2.1/Q42）。
export function computeFallback(kind: NodeKind, body: string): string {
  const preview = firstLinePreview(htmlToText(body))
  if (kind === 'chapter') return '(未命名章节)'
  if (kind === 'content') return preview || '(空内容块)'
  return preview || '(空步骤)'
}

// ---- 执行表单类型元数据（标签 + 色组，§2.1 类型色条） ---- //

export interface FormTypeMeta {
  label: string
  color: 'gray' | 'blue' | 'purple' | 'cyan' | 'orange' | 'red'
}

export const FORM_TYPE_META: Record<FormType, FormTypeMeta> = {
  COMMON: { label: '通用（操作说明）', color: 'gray' },
  NONE: { label: '无执行记录', color: 'gray' },
  CHECK: { label: '通过/不通过', color: 'blue' },
  YESNO: { label: '是/否', color: 'blue' },
  NUMBER: { label: '数值', color: 'purple' },
  METER: { label: '仪表读数', color: 'purple' },
  CHECKBOX: { label: '多选', color: 'cyan' },
  RADIO: { label: '单选', color: 'cyan' },
  UPLOAD: { label: '文件上传', color: 'orange' },
  PHOTO: { label: '拍照', color: 'orange' },
  SIGNATURE: { label: '签名', color: 'orange' },
  DATE: { label: '日期', color: 'orange' },
  NOTE: { label: '注意', color: 'blue' },
  CAUTION: { label: '小心', color: 'orange' },
  WARNING: { label: '警告', color: 'red' },
}

// 警示类型（渲染成彩色提示框）与富文本类型（用富文本编辑、绑定 content）。
export const ALERT_TYPES: readonly FormType[] = ['NOTE', 'CAUTION', 'WARNING']
export const RICH_TEXT_TYPES: readonly FormType[] = ['COMMON', 'NOTE', 'CAUTION', 'WARNING']
export function isAlertType(t: FormType): boolean {
  return ALERT_TYPES.includes(t)
}
export function isRichTextType(t: FormType): boolean {
  return RICH_TEXT_TYPES.includes(t)
}
