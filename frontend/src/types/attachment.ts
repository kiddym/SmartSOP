export interface AttachmentOut {
  id: string
  procedure_id: string
  file_name: string
  mime_type: string
  file_type?: string
  hidden?: boolean
  size_bytes: number
  description?: string
  sort_order: number
  uploader_name?: string
  created_at: string
  updated_at: string
}

// 全局文件库列表项（跨实体浏览）。
export interface LibraryAttachment {
  id: string
  entity_type: string
  entity_id: string
  file_name: string
  mime_type: string
  file_type: string
  hidden: boolean
  size_bytes: number
  description: string
  created_at: string
  updated_at: string
}

export interface LibraryPage {
  items: LibraryAttachment[]
  total: number
  limit: number
  offset: number
}

export interface LibraryQuery {
  entity_type?: string
  file_type?: string
  include_hidden?: boolean
  q?: string
  limit?: number
  offset?: number
}
