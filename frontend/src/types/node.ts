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

// ---- 统一节点模型（B3）：单 ProcedureNode 取代 chapter/content/step 三分 ----
// 对齐后端 NodeOut（app/schemas/node.py）。parent_id/depth/code 为服务端派生。
export interface Node {
  id: string
  procedure_id: string
  sort_order: number
  heading_level: number | null // null=正文；1..N=章节层级
  kind: 'node' | 'step' // 'node'=无表单（章节/正文）；'step'=带表单
  body: string // rich HTML；heading 标题=body 第一个块级元素文本
  code: string // 服务端编号
  skip_numbering: boolean
  input_schema: InputSchema | Record<string, never>
  attachment_marks: AttachmentMark[]
  mark_status: MarkStatus // 统一模型只用 'unmarked' | 'review'
  revision: number // 乐观锁（仅 PATCH /nodes/{id} 用）
  parent_id: string | null // 派生
  depth: number // 派生
}

// PATCH /nodes/{id} body（NodePatchIn）。改 heading_level 必须带 set_heading_level:true。
export interface NodePatch {
  heading_level?: number | null
  set_heading_level?: boolean
  kind?: 'node' | 'step'
  body?: string
  input_schema?: InputSchema
  attachment_marks?: AttachmentMark[]
  skip_numbering?: boolean
}

// POST /procedures/{id}/nodes body（NodeCreateIn）。
export interface NodeCreate {
  body?: string
  heading_level?: number | null
  kind?: 'node' | 'step'
  input_schema?: InputSchema
  attachment_marks?: AttachmentMark[]
  skip_numbering?: boolean
  sort_order?: number | null
}

// :batch 单项（NodeBatchItem，不含 body/attachment_marks）。
export interface NodeBatchItem {
  heading_level?: number | null
  set_heading_level?: boolean
  kind?: 'node' | 'step'
  input_schema?: InputSchema
  skip_numbering?: boolean
}

// :batch updates 映射：nodeId → 变更。
export type NodeBatchUpdates = Record<string, NodeBatchItem>
