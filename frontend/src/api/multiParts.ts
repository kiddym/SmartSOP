import { http } from './http'
import type { MultiPartRead, MultiPartCreate, MultiPartUpdate } from '@/types/inventory'

export const listMultiParts = () =>
  http.get<MultiPartRead[]>('/multi-parts').then((r) => r.data)
export const getMultiPart = (id: string) =>
  http.get<MultiPartRead>(`/multi-parts/${id}`).then((r) => r.data)
export const createMultiPart = (p: MultiPartCreate) =>
  http.post<MultiPartRead>('/multi-parts', p).then((r) => r.data)
export const updateMultiPart = (id: string, p: MultiPartUpdate) =>
  http.patch<MultiPartRead>(`/multi-parts/${id}`, p).then((r) => r.data)
export const deleteMultiPart = (id: string) =>
  http.delete(`/multi-parts/${id}`).then(() => undefined)
