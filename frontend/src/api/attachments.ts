import { http } from './http'
import type { AttachmentOut } from '@/types/attachment'

export const listAttachments = (procedureId: string): Promise<AttachmentOut[]> =>
  http.get<AttachmentOut[]>(`/procedures/${procedureId}/attachments`).then(r => r.data)

export const uploadAttachment = (
  procedureId: string,
  files: File[],
): Promise<AttachmentOut[]> => {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  return http
    .post<AttachmentOut[]>(`/procedures/${procedureId}/attachments`, fd)
    .then(r => r.data)
}

// 单附件操作后端扁平挂 /attachments/{id}（非嵌套在 procedures 下）。
export const downloadAttachment = async (attachId: string): Promise<void> => {
  const res = await http.get<Blob>(`/attachments/${attachId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  a.click()
  URL.revokeObjectURL(url)
}

export const deleteAttachment = (attachId: string): Promise<void> =>
  http.delete(`/attachments/${attachId}`).then(() => undefined)

// 通用多态附件（/attachments?entity_type=&entity_id=）：供工单/资产/请求等实体复用。
export const listEntityAttachments = (
  entityType: string,
  entityId: string,
): Promise<AttachmentOut[]> =>
  http
    .get<AttachmentOut[]>('/attachments', { params: { entity_type: entityType, entity_id: entityId } })
    .then((r) => r.data)

export const uploadEntityAttachment = (
  entityType: string,
  entityId: string,
  file: File,
  description = '',
): Promise<AttachmentOut> => {
  const fd = new FormData()
  fd.append('entity_type', entityType)
  fd.append('entity_id', entityId)
  fd.append('file', file)
  fd.append('description', description)
  return http.post<AttachmentOut>('/attachments', fd).then((r) => r.data)
}
