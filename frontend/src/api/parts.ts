import { http } from './http'
import type { PartRead, PartCreate, PartUpdate, PartMini } from '@/types/inventory'
import type { WorkOrderRead } from '@/types/workOrder'

export interface ListPartsParams {
  category_id?: string
  asset_id?: string
  low_stock?: boolean
}

export const listParts = (params: ListPartsParams = {}) =>
  http.get<PartRead[]>('/parts', { params }).then((r) => r.data)
export const listPartsMini = () => http.get<PartMini[]>('/parts/mini').then((r) => r.data)
export const getPart = (id: string) => http.get<PartRead>(`/parts/${id}`).then((r) => r.data)
export const listPartWorkOrders = (id: string) =>
  http.get<WorkOrderRead[]>(`/parts/${id}/work-orders`).then((r) => r.data)
export const createPart = (p: PartCreate) => http.post<PartRead>('/parts', p).then((r) => r.data)
export const updatePart = (id: string, p: PartUpdate) =>
  http.patch<PartRead>(`/parts/${id}`, p).then((r) => r.data)
export const deletePart = (id: string) => http.delete(`/parts/${id}`).then(() => undefined)
