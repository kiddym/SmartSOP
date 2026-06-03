import { http } from './http'
import type { VendorRead, VendorCreate, VendorUpdate, VendorMini } from '@/types/inventory'

export const listVendors = () => http.get<VendorRead[]>('/vendors').then((r) => r.data)
export const listVendorsMini = () => http.get<VendorMini[]>('/vendors/mini').then((r) => r.data)
export const createVendor = (p: VendorCreate) =>
  http.post<VendorRead>('/vendors', p).then((r) => r.data)
export const updateVendor = (id: string, p: VendorUpdate) =>
  http.patch<VendorRead>(`/vendors/${id}`, p).then((r) => r.data)
export const deleteVendor = (id: string) => http.delete(`/vendors/${id}`).then(() => undefined)
