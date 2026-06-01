import type { ParseResponse } from '@/types/parse'

export type BatchItemStatus =
  | 'queued' | 'parsing' | 'review' | 'applying' | 'applied' | 'skipped' | 'failed'

export interface BatchCounts {
  total: number
  parsed: number
  review: number
  applied: number
  failed: number
  skipped?: number
}

export interface BatchImportJob {
  id: string
  folder_id: string
  parse_mode: string
  status: string
  counts: BatchCounts
  created_at: string
}

export interface BatchImportItem {
  id: string
  job_id: string
  filename: string
  status: BatchItemStatus
  content_hash: string
  summary: { chapter_count?: number; confidence_tier?: string; warning_count?: number }
  review_revision: number
  error: string | null
}

export type ReviewAction = 'accept' | 'to_content' | 'to_chapter' | 'set_level'

export interface ReviewOp {
  node_id: string
  action: ReviewAction
  level?: number
}

export interface ApplyPreview {
  to_create: number
  duplicate_skip: number
  target_folder_id: string
}

export type BatchBlob = ParseResponse
