// Word 上传 / 解析 / 导入类型（与后端 app/schemas/parse.py 对齐，全 snake_case，Q350）。

import type { MarkStatus } from '@/types/node'

// ---- 上传 ---- //
export interface UploadResult {
  upload_token: string
  expires_at: string
  filename: string
}

// ---- 解析方法 ---- //
export interface ParseMethod {
  key: string // 'standard' | 'smart'
  label: string
  description: string
}

export type ParseMode = 'standard' | 'smart'
export type ConfidenceTier = 'high' | 'medium' | 'low'

// ---- 解析返回的章节树节点（带置信度 / review） ---- //
export interface ParsedNode {
  id: string
  title: string
  level: number
  order: number
  parent_id: string | null
  content_type: 'chapter' | 'content'
  rich_content: string
  skip_numbering: boolean
  confidence: number
  confidence_tier: ConfidenceTier
  mark_status: MarkStatus
  heading_source: string | null
  children: ParsedNode[]
}

export interface ParsedAsset {
  temp_id: string
  url: string
  sha256: string
  mime: string
  size_bytes: number
  width: number | null
  height: number | null
}

// ---- 零样式编号模式建议（Q200） ---- //
export interface DetectedPattern {
  pattern: string
  suggested_level: number
  count: number
  sample_titles: string[]
}

// ---- 模板校验报告（standard） ---- //
export interface ValidationRule {
  code: string
  level: string // pass | warning | error
  passed: boolean
  message: string
}

export interface ValidationReport {
  passed: boolean
  level: string // pass | warning | error
  rules: ValidationRule[]
  summary: string
}

export interface ParseWarning {
  stage: string // boundary | completeness | image | structure
  message: string
}

export interface ParseMetadata {
  total_chapters: number
  image_count: number
  table_count: number
  body_start_index: number
  body_start_detected_by: string
  format: string
  parse_time_ms: number
}

export interface ParseResponse {
  metadata: ParseMetadata
  chapters: ParsedNode[]
  assets: ParsedAsset[]
  detected_patterns: DetectedPattern[]
  validation: ValidationReport | null
  warnings: ParseWarning[]
  review_required: number
  parse_method: string
}

// ---- 导入入参（POST /procedures/import） ---- //
export interface ImportNode {
  id?: string
  title: string
  content_type: 'chapter' | 'content'
  rich_content: string
  skip_numbering: boolean
  mark_status: MarkStatus
  children: ImportNode[]
}

export interface ImportRequest {
  name: string
  folder_id: string
  description?: string
  upload_token?: string
  chapters: ImportNode[]
}

// ---- 编辑器图片直传（Q214） ---- //
export interface AssetUploadResult {
  asset_id: string
  url: string
  width: number | null
  height: number | null
}
