import { http } from './http'
import type { LocationRead, LocationCreate, LocationUpdate, LocationMini } from '@/types/maindata'

export const listLocations = () => http.get<LocationRead[]>('/locations').then((r) => r.data)
export const getLocation = (id: string) =>
  http.get<LocationRead>(`/locations/${id}`).then((r) => r.data)
export const listLocationsMini = () =>
  http.get<LocationMini[]>('/locations/mini').then((r) => r.data)
export const createLocation = (p: LocationCreate) =>
  http.post<LocationRead>('/locations', p).then((r) => r.data)
export const updateLocation = (id: string, p: LocationUpdate) =>
  http.patch<LocationRead>(`/locations/${id}`, p).then((r) => r.data)
export const deleteLocation = (id: string) => http.delete(`/locations/${id}`).then(() => undefined)
