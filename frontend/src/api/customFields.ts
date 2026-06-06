import { http } from './http'
import type {
  CustomFieldDef,
  CustomFieldCreate,
  CustomFieldUpdate,
  CustomFieldEntity,
} from '@/types/customField'

export const listCustomFields = (entityType: CustomFieldEntity, includeArchived = false) =>
  http
    .get<CustomFieldDef[]>('/custom-fields', {
      params: { entity_type: entityType, include_archived: includeArchived },
    })
    .then((r) => r.data)

export const createCustomField = (p: CustomFieldCreate) =>
  http.post<CustomFieldDef>('/custom-fields', p).then((r) => r.data)

export const updateCustomField = (id: string, p: CustomFieldUpdate) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}`, p).then((r) => r.data)

export const archiveCustomField = (id: string) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}/archive`).then((r) => r.data)

export const restoreCustomField = (id: string) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}/restore`).then((r) => r.data)

export const deleteCustomField = (id: string) =>
  http.delete(`/custom-fields/${id}`).then(() => undefined)

export const reorderCustomFields = (entityType: CustomFieldEntity, orderedIds: string[]) =>
  http
    .post<CustomFieldDef[]>(
      '/custom-fields/reorder',
      { ordered_ids: orderedIds },
      { params: { entity_type: entityType } },
    )
    .then((r) => r.data)
