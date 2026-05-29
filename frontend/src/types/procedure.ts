// 程序类型（与后端 app/schemas/procedure.py 对齐）

import type { FieldOption, FieldType } from '@/types/field'

export type LevelOfUse = 'reference' | 'continuous' | 'information'
export type ProcedureStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export interface ProcedureRow {
  id: string
  procedure_group_id: string
  code: string
  name: string
  version: number
  is_current: boolean
  status: ProcedureStatus
  folder_id: string
  folder_full_path: string
  level_of_use: LevelOfUse
  risk_level: number
  quality_level: number
  description: string
  revision: number
  version_count_in_group: number
  created_at: string
  updated_at: string
}

export interface ProcedureMeta {
  id: string
  procedure_group_id: string
  code: string
  name: string
  version: number
  is_current: boolean
  status: ProcedureStatus
  folder_id: string
  folder_full_path: string
  description: string
  risk_level: number
  quality_level: number
  level_of_use: LevelOfUse
  custom_values: Record<string, unknown>
  version_update_notes: string
  signoff_enabled: boolean
  revision: number
  is_read: boolean
  read_at: string | null
  deprecated_from_folder_id: string | null
  deprecated_at: string | null
  archived_at: string | null
  version_change_log: Array<Record<string, unknown>>
  created_at: string
  updated_at: string
}

export interface ProcedureFieldView {
  id: string
  name: string
  key: string
  field_type: FieldType
  required: boolean
  options: FieldOption[]
  sort_order: number
  show_on_cover: boolean
}

export interface ProcedureDetail {
  procedure: ProcedureMeta
  attachments: unknown[]
  fields: ProcedureFieldView[]
  has_source_docx: boolean
}

export interface ProcedureCreate {
  folder_id: string
  name: string
  level_of_use: LevelOfUse
  description?: string
  risk_level?: number
  quality_level?: number
  custom_values?: Record<string, unknown>
}

export interface ProcedureUpdate {
  name: string
  level_of_use: LevelOfUse
  description?: string
  risk_level?: number
  quality_level?: number
  custom_values?: Record<string, unknown>
  version_update_notes?: string
  signoff_enabled?: boolean
}

export interface TransitionPayload {
  status: ProcedureStatus
  reason?: string
}

export interface BatchMoveResult {
  moved_ids: string[]
  failed: Array<{ id: string; code: string; message: string }>
}

// ---- 版本管理（Phase 7，与后端 app/schemas/procedure.py 对齐） ---- //

// 丢弃 DRAFT 特殊路径响应（§22.11）。普通软删返 204（前端得 null）。
export interface DiscardDraftResult {
  deleted_id: string
  new_current_id: string
  new_current_version: number
}

// 恢复前预检查（§22.5）。
export interface RestorePreview {
  folder_exists: boolean
  deprecated_from_folder_id: string | null
  folder_full_path: string | null
  version_count: number
}

// group 版本列表行（GET /procedure-groups/{group_id}/versions）。
export interface VersionListItem {
  id: string
  version: number
  status: ProcedureStatus
  is_current: boolean
  version_update_notes: string
  version_update_notes_preview: string
  created_at: string
  archived_at: string | null
}

export interface VersionListOut {
  count: number
  items: VersionListItem[]
}

export interface RollbackPayload {
  target_version: number
  reason: string
}

export interface RestorePayload {
  reason: string
  target_folder_id?: string | null
}

export interface CopyPayload {
  target_folder_id: string
  name?: string | null
}
