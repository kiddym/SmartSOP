// 章节 / 内容 / 步骤（节点）类型，与后端 app/schemas/node.py 对齐。
// 编号 code 全自动（§47），不接受手填；编辑器内用 utils/editor.ts 客户端镜像实时预览。

// 标记态：编辑器三态 + Word 智能解析留下的持久 'review' 态（apply-marks 不碰，M1 修复）。
export type MarkStatus = 'unmarked' | 'step' | 'content' | 'review'

// 执行表单 15 型（大写枚举，Q261/§40.1）。
export type FormType =
  | 'COMMON'
  | 'NOTE'
  | 'CAUTION'
  | 'WARNING'
  | 'CHECK'
  | 'YESNO'
  | 'NUMBER'
  | 'METER'
  | 'CHECKBOX'
  | 'RADIO'
  | 'UPLOAD'
  | 'SIGNATURE'
  | 'DATE'
  | 'PHOTO'
  | 'NONE'

export const FORM_TYPES: readonly FormType[] = [
  'COMMON',
  'NOTE',
  'CAUTION',
  'WARNING',
  'CHECK',
  'YESNO',
  'NUMBER',
  'METER',
  'CHECKBOX',
  'RADIO',
  'UPLOAD',
  'SIGNATURE',
  'DATE',
  'PHOTO',
  'NONE',
]

// input_schema：type 必有，其余配置字段随类型动态（NUMBER 的 unit/min/max、CHOICE 的 options 等）。
export interface InputSchema {
  type: FormType
  [key: string]: unknown
}

// 附件标记（Q220）：纯标记，不校验文件已上传。
export interface AttachmentMark {
  filename: string
  kind: string
  note: string
}

// ---- 服务端输出形态 ---- //

// GET /procedures/{id}.chapters 的嵌套树节点。
export interface ChapterTreeNode {
  id: string
  title: string
  code: string
  level: number
  sort_order: number
  skip_numbering: boolean
  mark_status: MarkStatus
  children: ChapterTreeNode[]
}

// GET /procedures/{id}.steps（平铺，前端按 chapter_id 自挂载）。
export interface StepOut {
  id: string
  procedure_id: string
  chapter_id: string | null
  kind: 'step' | 'content'
  title: string
  code: string
  content: string
  sort_order: number
  skip_numbering: boolean
  input_schema: InputSchema
  attachment_marks: AttachmentMark[]
}

// GET/PUT /chapters/{id} 单节点详情（不含 children）。
export interface ChapterOut {
  id: string
  procedure_id: string
  parent_id: string | null
  title: string
  code: string
  level: number
  sort_order: number
  skip_numbering: boolean
  mark_status: MarkStatus
}

// ---- 批量保存入参（PUT /procedures/{id}，§17.2） ---- //

export interface ChapterUpsert {
  id: string
  parent_id: string | null
  title: string
  skip_numbering: boolean
  sort_order: number
}

export interface StepUpsert {
  id: string
  chapter_id: string | null
  kind: 'step' | 'content'
  title: string
  content: string
  input_schema: InputSchema
  attachment_marks: AttachmentMark[]
  skip_numbering: boolean
  sort_order: number
}

// ---- 细粒度 action 入参 ---- //

export interface ChapterCreate {
  procedure_id: string
  parent_id?: string | null
  title?: string
  skip_numbering?: boolean
  sort_order?: number | null
}

export interface ChapterMoveIn {
  target_parent_id: string | null
  target_index: number
}

export interface StepMoveIn {
  target_chapter_id: string | null
  target_index: number
}

// ---- 转换 / 标记结果 ---- //

export interface ConversionResult {
  created: string[]
  deleted: string[]
}

export type ApplyMarksResult = ConversionResult

// ---- 编辑器内部模型（store 持有；data 字段沿用 snake_case 与服务端对齐，降低映射出错） ---- //

export type NodeKind = 'chapter' | 'content' | 'step'

// 章节 / 内容节点（扁平存储，parent_id 在挂载时回填）。
export interface EditorChapter {
  id: string
  parent_id: string | null
  title: string
  skip_numbering: boolean
  mark_status: MarkStatus
  sort_order: number
}

// 步骤节点（扁平存储）。kind 区分：
//   step    = title?（可选） + content（富文本） + 结构化字段（表单 input_schema / 附件 attachment_marks）
//   content = title?（可选） + content（富文本）；无结构化字段
// 升为章节（layer 模式 / convert-to-chapter）对两者都开放——title 作新章节标题、空 title 由后端兜底"未命名章节"。
export interface EditorStep {
  id: string
  chapter_id: string | null
  kind: 'step' | 'content'
  title: string
  content: string
  input_schema: InputSchema
  attachment_marks: AttachmentMark[]
  skip_numbering: boolean
  sort_order: number
}

// 扁平渲染行（树渲染 + 虚拟滚动 + 搜索过滤的统一单元）。
export interface FlatRow {
  id: string
  kind: NodeKind
  depth: number
  parent_id: string | null
  title: string
  code: string // 已应用 .0 / # 渲染规则的显示串
  skip_numbering: boolean
  mark_status: MarkStatus // step 上恒 'unmarked'（后端无此列）；step 行本身可参与标记模式
  form_type: FormType | null // 仅 step
  has_children: boolean
  expanded: boolean
  fallback: string // title 为空时的灰斜体回退文本
}

// 新增按钮（Q25 互斥）三态。
export interface AddButtonState {
  canAddChapter: boolean
  canAddContent: boolean
  canAddStep: boolean
}

// 层级标定批量应用(spec: 2026-05-27-layer-overlay-auto-nest-design)。
export type LayerApplyRoleValue = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'keep'

export interface LayerApplyIn {
  roles: Record<string, LayerApplyRoleValue>
}

export interface LayerApplyResult {
  chapter_map: Record<string, string>
  revision: number
}

export interface LayerApplyConflictDetail {
  code: 'SIBLING_TYPE_CONFLICT'
  message: string
  conflicts: Array<{
    parent_id: string | null
    chapter_children: string[]
    leaf_children: string[]
  }>
}
