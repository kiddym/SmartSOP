import { http } from './http'
import type {
  UserRead,
  UserCreate,
  UserInvite,
  UserUpdate,
  SelfProfileUpdate,
  InviteResult,
} from '@/types/platform'

// 后端路由前缀 /users（见 backend/app/routers/users.py）。
export const listUsers = () => http.get<UserRead[]>('/users').then((r) => r.data)

// 当前登录用户的自助资料（任意认证用户可读/改自己）。
export const getMyProfile = () => http.get<UserRead>('/users/me').then((r) => r.data)

export const updateMyProfile = (payload: SelfProfileUpdate) =>
  http.patch<UserRead>('/users/me', payload).then((r) => r.data)

export const createUser = (payload: UserCreate) =>
  http.post<UserRead>('/users', payload).then((r) => r.data)

export const inviteUser = (payload: UserInvite) =>
  http.post<InviteResult>('/users/invite', payload).then((r) => r.data)

export const updateUser = (id: string, payload: UserUpdate) =>
  http.patch<UserRead>(`/users/${id}`, payload).then((r) => r.data)

export const deleteUser = (id: string) => http.delete(`/users/${id}`).then(() => undefined)

export const disableUser = (id: string) =>
  http.patch<UserRead>(`/users/${id}/disable`).then((r) => r.data)

export const enableUser = (id: string) =>
  http.patch<UserRead>(`/users/${id}/enable`).then((r) => r.data)
