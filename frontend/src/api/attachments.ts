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
