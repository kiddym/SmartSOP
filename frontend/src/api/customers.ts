import { http } from './http'
import type { CustomerRead, CustomerCreate, CustomerUpdate, CustomerMini } from '@/types/inventory'

export const listCustomers = () => http.get<CustomerRead[]>('/customers').then((r) => r.data)
export const listCustomersMini = () =>
  http.get<CustomerMini[]>('/customers/mini').then((r) => r.data)
export const createCustomer = (p: CustomerCreate) =>
  http.post<CustomerRead>('/customers', p).then((r) => r.data)
export const updateCustomer = (id: string, p: CustomerUpdate) =>
  http.patch<CustomerRead>(`/customers/${id}`, p).then((r) => r.data)
export const deleteCustomer = (id: string) => http.delete(`/customers/${id}`).then(() => undefined)
