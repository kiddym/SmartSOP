import { http } from './http'
import type {
  ApplyPreview, BatchBlob, BatchImportItem, BatchImportJob, ReviewOp,
} from '@/types/batchImport'

export interface BatchCreatePayload {
  folder_id: string
  parse_mode: string
  items: { filename: string; upload_token: string }[]
}

export const createBatchImport = async (payload: BatchCreatePayload): Promise<BatchImportJob> => {
  const { data } = await http.post<BatchImportJob>('/batch-imports', payload)
  return data
}

export const fetchBatchJob = async (jobId: string): Promise<BatchImportJob> => {
  const { data } = await http.get<BatchImportJob>(`/batch-imports/${jobId}`)
  return data
}

export const fetchBatchItems = async (
  jobId: string, status?: string,
): Promise<BatchImportItem[]> => {
  const { data } = await http.get<BatchImportItem[]>(`/batch-imports/${jobId}/items`, {
    params: status ? { status } : undefined,
  })
  return data
}

export const fetchParseResult = async (jobId: string, itemId: string): Promise<BatchBlob> => {
  const { data } = await http.get<BatchBlob>(`/batch-imports/${jobId}/items/${itemId}/parse-result`)
  return data
}

export const patchReviewItem = async (
  jobId: string, itemId: string, body: { review_revision: number; ops: ReviewOp[] },
): Promise<{ review_revision: number }> => {
  const { data } = await http.patch<{ review_revision: number }>(
    `/batch-imports/${jobId}/items/${itemId}/review`, body, { skipErrorToast: true },
  )
  return data
}

export const previewApply = async (
  jobId: string, itemIds: string[] | null,
): Promise<ApplyPreview> => {
  const { data } = await http.post<ApplyPreview>(
    `/batch-imports/${jobId}/apply-preview`, { item_ids: itemIds },
  )
  return data
}

export const applyBatch = async (
  jobId: string, opts: { itemIds?: string[] | null; highConfidenceOnly?: boolean },
): Promise<{ enqueued: number }> => {
  const { data } = await http.post<{ enqueued: number }>(`/batch-imports/${jobId}/apply`, {
    item_ids: opts.itemIds ?? null,
    high_confidence_only: opts.highConfidenceOnly ?? false,
  })
  return data
}

export const retryItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/retry`).then(() => undefined)

export const skipItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/skip`).then(() => undefined)

export const undoItem = (jobId: string, itemId: string): Promise<void> =>
  http.post(`/batch-imports/${jobId}/items/${itemId}/undo`).then(() => undefined)
