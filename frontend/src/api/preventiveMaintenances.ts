import { http } from './http'
import type { PMRead, PMCreate, PMUpdate, ActivityRead, CommentCreate } from '@/types/maintenance'

export interface ListPMsParams {
  is_enabled?: boolean
  asset_id?: string
  location_id?: string
}

export const listPMs = (params: ListPMsParams = {}) =>
  http.get<PMRead[]>('/preventive-maintenances', { params }).then((r) => r.data)
export const getPM = (id: string) =>
  http.get<PMRead>(`/preventive-maintenances/${id}`).then((r) => r.data)
export const createPM = (p: PMCreate) =>
  http.post<PMRead>('/preventive-maintenances', p).then((r) => r.data)
export const updatePM = (id: string, p: PMUpdate) =>
  http.patch<PMRead>(`/preventive-maintenances/${id}`, p).then((r) => r.data)
export const deletePM = (id: string) =>
  http.delete(`/preventive-maintenances/${id}`).then(() => undefined)
export const enablePM = (id: string) =>
  http.post<PMRead>(`/preventive-maintenances/${id}/enable`).then((r) => r.data)
export const disablePM = (id: string) =>
  http.post<PMRead>(`/preventive-maintenances/${id}/disable`).then((r) => r.data)
export const generatePM = (id: string) =>
  http.post(`/preventive-maintenances/${id}/generate`).then((r) => r.data)
export const listPMActivities = (id: string) =>
  http.get<ActivityRead[]>(`/preventive-maintenances/${id}/activities`).then((r) => r.data)
export const addPMComment = (id: string, p: CommentCreate) =>
  http.post<ActivityRead>(`/preventive-maintenances/${id}/comments`, p).then((r) => r.data)
