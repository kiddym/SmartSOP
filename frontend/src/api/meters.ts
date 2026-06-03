import { http } from './http'
import type {
  MeterRead,
  MeterCreate,
  MeterUpdate,
  MeterReadingRead,
  MeterReadingCreate,
  ReadingResult,
  TriggerRead,
  TriggerCreate,
  TriggerUpdate,
} from '@/types/maintenance'

export interface ListMetersParams {
  asset_id?: string
  location_id?: string
}

export const listMeters = (params: ListMetersParams = {}) =>
  http.get<MeterRead[]>('/meters', { params }).then((r) => r.data)
export const getMeter = (id: string) => http.get<MeterRead>(`/meters/${id}`).then((r) => r.data)
export const createMeter = (p: MeterCreate) =>
  http.post<MeterRead>('/meters', p).then((r) => r.data)
export const updateMeter = (id: string, p: MeterUpdate) =>
  http.patch<MeterRead>(`/meters/${id}`, p).then((r) => r.data)
export const deleteMeter = (id: string) => http.delete(`/meters/${id}`).then(() => undefined)

export const listReadings = (meterId: string) =>
  http.get<MeterReadingRead[]>(`/meters/${meterId}/readings`).then((r) => r.data)
export const submitReading = (meterId: string, p: MeterReadingCreate) =>
  http.post<ReadingResult>(`/meters/${meterId}/readings`, p).then((r) => r.data)

export const listTriggers = (meterId: string) =>
  http.get<TriggerRead[]>(`/meters/${meterId}/triggers`).then((r) => r.data)
export const createTrigger = (meterId: string, p: TriggerCreate) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers`, p).then((r) => r.data)
export const updateTrigger = (meterId: string, triggerId: string, p: TriggerUpdate) =>
  http.patch<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}`, p).then((r) => r.data)
export const deleteTrigger = (meterId: string, triggerId: string) =>
  http.delete(`/meters/${meterId}/triggers/${triggerId}`).then(() => undefined)
export const enableTrigger = (meterId: string, triggerId: string) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}/enable`).then((r) => r.data)
export const disableTrigger = (meterId: string, triggerId: string) =>
  http.post<TriggerRead>(`/meters/${meterId}/triggers/${triggerId}/disable`).then((r) => r.data)
