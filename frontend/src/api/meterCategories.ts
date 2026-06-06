import { http } from './http'
import type {
  MeterCategoryRead,
  MeterCategoryCreate,
  MeterCategoryUpdate,
} from '@/types/maintenance'

export const listMeterCategories = () =>
  http.get<MeterCategoryRead[]>('/meter-categories').then((r) => r.data)
export const createMeterCategory = (p: MeterCategoryCreate) =>
  http.post<MeterCategoryRead>('/meter-categories', p).then((r) => r.data)
export const updateMeterCategory = (id: string, p: MeterCategoryUpdate) =>
  http.patch<MeterCategoryRead>(`/meter-categories/${id}`, p).then((r) => r.data)
export const deleteMeterCategory = (id: string) =>
  http.delete(`/meter-categories/${id}`).then(() => undefined)
