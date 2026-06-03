import { http } from './http'
import type {
  PurchaseOrderRead,
  PurchaseOrderCreate,
  PurchaseOrderUpdate,
  PurchaseOrderStatus,
  POActivityRead,
  POResolve,
} from '@/types/inventory'

export interface ListPurchaseOrdersParams {
  status?: PurchaseOrderStatus
  vendor_id?: string
}

export const listPurchaseOrders = (params: ListPurchaseOrdersParams = {}) =>
  http.get<PurchaseOrderRead[]>('/purchase-orders', { params }).then((r) => r.data)
export const getPurchaseOrder = (id: string) =>
  http.get<PurchaseOrderRead>(`/purchase-orders/${id}`).then((r) => r.data)
export const createPurchaseOrder = (p: PurchaseOrderCreate) =>
  http.post<PurchaseOrderRead>('/purchase-orders', p).then((r) => r.data)
export const updatePurchaseOrder = (id: string, p: PurchaseOrderUpdate) =>
  http.patch<PurchaseOrderRead>(`/purchase-orders/${id}`, p).then((r) => r.data)
export const deletePurchaseOrder = (id: string) =>
  http.delete(`/purchase-orders/${id}`).then(() => undefined)
export const submitPurchaseOrder = (id: string) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/submit`).then((r) => r.data)
export const approvePurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/approve`, p).then((r) => r.data)
export const rejectPurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/reject`, p).then((r) => r.data)
export const cancelPurchaseOrder = (id: string, p: POResolve = {}) =>
  http.post<PurchaseOrderRead>(`/purchase-orders/${id}/cancel`, p).then((r) => r.data)
export const listPurchaseOrderActivities = (id: string) =>
  http.get<POActivityRead[]>(`/purchase-orders/${id}/activities`).then((r) => r.data)
