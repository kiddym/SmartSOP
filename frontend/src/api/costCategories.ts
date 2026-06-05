import { http } from './http'
import type { CostCategoryRead, CostCategoryCreate, CostCategoryUpdate } from '@/types/workOrder'

export const listCostCategories = () =>
  http.get<CostCategoryRead[]>('/cost-categories').then((r) => r.data)
export const createCostCategory = (p: CostCategoryCreate) =>
  http.post<CostCategoryRead>('/cost-categories', p).then((r) => r.data)
export const updateCostCategory = (id: string, p: CostCategoryUpdate) =>
  http.patch<CostCategoryRead>(`/cost-categories/${id}`, p).then((r) => r.data)
export const deleteCostCategory = (id: string) =>
  http.delete(`/cost-categories/${id}`).then(() => undefined)
