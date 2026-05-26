import { http } from './http'
import type { BatchDeleteResult, PageResult } from '@/types/common'
import type { ApplyMarksResult } from '@/types/node'
import type { PdfLayout } from '@/types/pdf'
import type {
  BatchMoveResult,
  CopyPayload,
  DiscardDraftResult,
  ProcedureCreate,
  ProcedureDetail,
  ProcedureMeta,
  ProcedureRow,
  ProcedureSaveIn,
  ProcedureSaveResult,
  ProcedureUpdate,
  RestorePayload,
  RestorePreview,
  RollbackPayload,
  TransitionPayload,
  VersionListOut,
} from '@/types/procedure'

export interface ProcedureListQuery {
  page?: number
  page_size?: number
  sort?: string
  search?: string
  folder_id?: string
  status?: string
}

export const fetchProcedureList = async (
  params?: ProcedureListQuery,
): Promise<PageResult<ProcedureRow>> =>
  (await http.get<PageResult<ProcedureRow>>('/procedures', { params })).data

export const fetchProcedureLibrary = async (
  params?: ProcedureListQuery,
): Promise<PageResult<ProcedureRow>> =>
  (await http.get<PageResult<ProcedureRow>>('/procedures/library', { params })).data

export const fetchProcedureDetail = async (id: string): Promise<ProcedureDetail> =>
  (await http.get<ProcedureDetail>(`/procedures/${id}`)).data

export const createProcedure = async (payload: ProcedureCreate): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>('/procedures', payload)).data

// PUT / transition 走乐观锁：revision 写入 If-Match 头
export const updateProcedure = async (
  id: string,
  payload: ProcedureUpdate,
  revision: number,
): Promise<ProcedureMeta> =>
  (
    await http.put<ProcedureMeta>(`/procedures/${id}`, payload, {
      headers: { 'If-Match': String(revision) },
    })
  ).data

// 编辑器整批保存：脏节点 upsert + 显式删除 + 程序元字段，走乐观锁（If-Match）。返回新 revision + id 映射。
export const saveProcedure = async (
  id: string,
  payload: ProcedureSaveIn,
  revision: number,
): Promise<ProcedureSaveResult> =>
  (
    await http.put<ProcedureSaveResult>(`/procedures/${id}`, payload, {
      headers: { 'If-Match': String(revision) },
    })
  ).data

// 应用标记（原子事务，Q9）。无 If-Match：服务端自行 bump revision，调用方应随后 reload 同步。
export const applyMarks = async (id: string): Promise<ApplyMarksResult> =>
  (await http.post<ApplyMarksResult>(`/procedures/${id}/apply-marks`)).data

export const transitionProcedure = async (
  id: string,
  payload: TransitionPayload,
  revision: number,
): Promise<ProcedureMeta> =>
  (
    await http.post<ProcedureMeta>(`/procedures/${id}/transition`, payload, {
      headers: { 'If-Match': String(revision) },
    })
  ).data

// 软删单版本；DRAFT 当前版(v>1) 走丢弃路径返 200 + DiscardDraftResult，普通软删返 204（null）。
export const deleteProcedure = async (
  id: string,
  reason: string,
): Promise<DiscardDraftResult | null> => {
  const resp = await http.delete<DiscardDraftResult | ''>(`/procedures/${id}`, {
    data: { reason },
  })
  return resp.status === 200 && resp.data ? (resp.data as DiscardDraftResult) : null
}

export const batchDeleteProcedures = async (
  ids: string[],
  reason: string,
): Promise<BatchDeleteResult> =>
  (await http.post<BatchDeleteResult>('/procedures/batch-delete', { ids, reason })).data

export const batchMoveProcedures = async (
  ids: string[],
  targetFolderId: string,
): Promise<BatchMoveResult> =>
  (
    await http.post<BatchMoveResult>('/procedures/batch-move', {
      ids,
      target_folder_id: targetFolderId,
    })
  ).data

// --------------------------------------------------------------------------- //
// 版本管理（Phase 7）。这些端点后端不读 If-Match（仅 PUT 整批保存 + transition 走乐观锁）。
// --------------------------------------------------------------------------- //
export const upgradeVersion = async (id: string): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/upgrade-version`)).data

export const rollbackVersion = async (
  id: string,
  payload: RollbackPayload,
): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/rollback`, payload)).data

export const deprecateGroup = async (id: string, reason: string): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/deprecate`, { reason })).data

export const archiveGroup = async (id: string, reason: string): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/archive`, { reason })).data

export const restorePreview = async (id: string): Promise<RestorePreview> =>
  (await http.get<RestorePreview>(`/procedures/${id}/restore-preview`)).data

export const restoreGroup = async (
  id: string,
  payload: RestorePayload,
): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/restore`, payload)).data

export const copyProcedure = async (id: string, payload: CopyPayload): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/copy`, payload)).data

export const fetchGroupVersions = async (
  groupId: string,
  countOnly = false,
): Promise<VersionListOut> =>
  (
    await http.get<VersionListOut>(`/procedure-groups/${groupId}/versions`, {
      params: { count_only: countOnly },
    })
  ).data

export const deleteGroup = async (groupId: string, reason: string): Promise<void> => {
  await http.delete(`/procedure-groups/${groupId}`, { data: { reason } })
}

// --------------------------------------------------------------------------- //
// PDF（Phase 8，§34/§59）。预览=前端渲染层（detail + layout）；下载=后端 ReportLab。
// --------------------------------------------------------------------------- //
export const fetchPdfLayout = async (id: string): Promise<PdfLayout> =>
  (await http.get<PdfLayout>(`/procedures/${id}/pdf-layout`)).data

// 下载静态 PDF（blob）→ 浏览器另存，文件名取 Content-Disposition（{code}_Rev{version}.pdf）。
export const downloadPdf = async (id: string): Promise<void> => {
  const resp = await http.get(`/procedures/${id}/pdf-download`, { responseType: 'blob' })
  const cd = String(resp.headers['content-disposition'] ?? '')
  const match = /filename="?([^"]+)"?/.exec(cd)
  const filename = match ? match[1] : `${id}.pdf`
  const url = URL.createObjectURL(resp.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// 取回导入程序的原始 .docx（供编辑器预览栏渲染）。无原文 / 取回失败 → null（非关键，不弹错）。
export const fetchSourceDocx = async (
  id: string,
): Promise<{ blob: Blob; filename: string } | null> => {
  try {
    const resp = await http.get(`/procedures/${id}/source-docx`, {
      responseType: 'blob',
      skipErrorToast: true,
    })
    const cd = String(resp.headers['content-disposition'] ?? '')
    const m = /filename\*=UTF-8''([^;]+)/.exec(cd)
    const filename = m ? decodeURIComponent(m[1]) : 'source.docx'
    return { blob: resp.data as Blob, filename }
  } catch {
    return null
  }
}
