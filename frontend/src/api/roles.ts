import { http } from './http'
import type { RoleRead, RoleCreate, RoleUpdate } from '@/types/platform'

// 后端路由前缀 /roles（见 backend/app/routers/roles.py）。
export const listRoles = () => http.get<RoleRead[]>('/roles').then((r) => r.data)

export const createRole = (payload: RoleCreate) =>
  http.post<RoleRead>('/roles', payload).then((r) => r.data)

export const updateRole = (id: string, payload: RoleUpdate) =>
  http.patch<RoleRead>(`/roles/${id}`, payload).then((r) => r.data)

export const deleteRole = (id: string) => http.delete(`/roles/${id}`).then(() => undefined)
