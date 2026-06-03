import { http } from './http'
import type { PartCategoryRead, PartCategoryCreate, PartCategoryUpdate } from '@/types/inventory'

export const listPartCategories = () =>
  http.get<PartCategoryRead[]>('/part-categories').then((r) => r.data)
export const createPartCategory = (p: PartCategoryCreate) =>
  http.post<PartCategoryRead>('/part-categories', p).then((r) => r.data)
export const updatePartCategory = (id: string, p: PartCategoryUpdate) =>
  http.patch<PartCategoryRead>(`/part-categories/${id}`, p).then((r) => r.data)
export const deletePartCategory = (id: string) =>
  http.delete(`/part-categories/${id}`).then(() => undefined)
