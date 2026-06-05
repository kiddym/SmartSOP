import { http } from './http'
import type { TimeCategoryRead, TimeCategoryCreate, TimeCategoryUpdate } from '@/types/workOrder'

export const listTimeCategories = () =>
  http.get<TimeCategoryRead[]>('/time-categories').then((r) => r.data)
export const createTimeCategory = (p: TimeCategoryCreate) =>
  http.post<TimeCategoryRead>('/time-categories', p).then((r) => r.data)
export const updateTimeCategory = (id: string, p: TimeCategoryUpdate) =>
  http.patch<TimeCategoryRead>(`/time-categories/${id}`, p).then((r) => r.data)
export const deleteTimeCategory = (id: string) =>
  http.delete(`/time-categories/${id}`).then(() => undefined)
