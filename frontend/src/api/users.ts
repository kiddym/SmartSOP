import { http } from './http'
import type { UserRead, UserCreate, UserInvite, UserUpdate, InviteResult } from '@/types/platform'

// 后端路由前缀 /users（见 backend/app/routers/users.py）。
export const listUsers = () => http.get<UserRead[]>('/users').then((r) => r.data)

export const createUser = (payload: UserCreate) =>
  http.post<UserRead>('/users', payload).then((r) => r.data)

export const inviteUser = (payload: UserInvite) =>
  http.post<InviteResult>('/users/invite', payload).then((r) => r.data)

export const updateUser = (id: string, payload: UserUpdate) =>
  http.patch<UserRead>(`/users/${id}`, payload).then((r) => r.data)

export const deleteUser = (id: string) => http.delete(`/users/${id}`).then(() => undefined)
