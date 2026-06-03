import { http } from './http'
import type {
  RequestRead,
  RequestCreate,
  RequestUpdate,
  RequestApprove,
  RequestReason,
  RequestStatus,
  WorkOrderPriority,
  ActivityRead,
  CommentCreate,
} from '@/types/maintenance'

export interface ListRequestsParams {
  status?: RequestStatus
  priority?: WorkOrderPriority
  asset_id?: string
  location_id?: string
}

export const listRequests = (params: ListRequestsParams = {}) =>
  http.get<RequestRead[]>('/requests', { params }).then((r) => r.data)
export const getRequest = (id: string) =>
  http.get<RequestRead>(`/requests/${id}`).then((r) => r.data)
export const createRequest = (p: RequestCreate) =>
  http.post<RequestRead>('/requests', p).then((r) => r.data)
export const updateRequest = (id: string, p: RequestUpdate) =>
  http.patch<RequestRead>(`/requests/${id}`, p).then((r) => r.data)
export const deleteRequest = (id: string) => http.delete(`/requests/${id}`).then(() => undefined)
export const approveRequest = (id: string, p: RequestApprove = {}) =>
  http.post<RequestRead>(`/requests/${id}/approve`, p).then((r) => r.data)
export const rejectRequest = (id: string, p: RequestReason) =>
  http.post<RequestRead>(`/requests/${id}/reject`, p).then((r) => r.data)
export const cancelRequest = (id: string, p: RequestReason) =>
  http.post<RequestRead>(`/requests/${id}/cancel`, p).then((r) => r.data)
export const listRequestActivities = (id: string) =>
  http.get<ActivityRead[]>(`/requests/${id}/activities`).then((r) => r.data)
export const addRequestComment = (id: string, p: CommentCreate) =>
  http.post<ActivityRead>(`/requests/${id}/activities`, p).then((r) => r.data)
