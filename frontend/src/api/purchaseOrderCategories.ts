import { http } from './http'
import type {
  PurchaseOrderCategoryRead,
  PurchaseOrderCategoryCreate,
  PurchaseOrderCategoryUpdate,
} from '@/types/inventory'

export const listPurchaseOrderCategories = () =>
  http.get<PurchaseOrderCategoryRead[]>('/purchase-order-categories').then((r) => r.data)
export const createPurchaseOrderCategory = (p: PurchaseOrderCategoryCreate) =>
  http.post<PurchaseOrderCategoryRead>('/purchase-order-categories', p).then((r) => r.data)
export const updatePurchaseOrderCategory = (id: string, p: PurchaseOrderCategoryUpdate) =>
  http.patch<PurchaseOrderCategoryRead>(`/purchase-order-categories/${id}`, p).then((r) => r.data)
export const deletePurchaseOrderCategory = (id: string) =>
  http.delete(`/purchase-order-categories/${id}`).then(() => undefined)
