import { http } from './http'
import type { FieldDetailOut, FieldCreate, FieldUpdate } from '@/types/field'
import type { BatchDeleteResult } from '@/types/common'

export const listFields = (params?: { field_type?: string; status?: string }) =>
  http.get<FieldDetailOut[]>('/fields', { params }).then(r => r.data)

export const createField = (payload: FieldCreate) =>
  http.post<FieldDetailOut>('/fields', payload).then(r => r.data)

export const updateField = (id: string, payload: FieldUpdate) =>
  http.put<FieldDetailOut>(`/fields/${id}`, payload).then(r => r.data)

export const deleteField = (id: string) =>
  http.delete(`/fields/${id}`).then(() => undefined)

export const updateFieldsStatus = (ids: string[], status: 'active' | 'archived') =>
  http.patch<{ updated_ids: string[] }>('/fields/status', { ids, status }).then(r => r.data)

export const batchDeleteFields = (ids: string[]) =>
  http.delete<BatchDeleteResult>('/fields', { data: { ids } }).then(r => r.data)

export const reorderFields = (ordered_ids: string[]) =>
  http.patch<FieldDetailOut[]>('/fields/reorder', { ordered_ids }).then(r => r.data)
