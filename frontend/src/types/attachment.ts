export interface AttachmentOut {
  id: string
  procedure_id: string
  file_name: string
  mime_type: string
  size_bytes: number
  description?: string
  sort_order: number
  uploader_name?: string
  created_at: string
  updated_at: string
}
