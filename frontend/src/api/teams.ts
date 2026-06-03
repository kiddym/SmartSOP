import { http } from './http'
import type { TeamRead, TeamCreate, TeamUpdate } from '@/types/platform'

// 后端路由前缀 /teams（见 backend/app/routers/teams.py）。
export const listTeams = () => http.get<TeamRead[]>('/teams').then((r) => r.data)

export const createTeam = (payload: TeamCreate) =>
  http.post<TeamRead>('/teams', payload).then((r) => r.data)

export const updateTeam = (id: string, payload: TeamUpdate) =>
  http.patch<TeamRead>(`/teams/${id}`, payload).then((r) => r.data)

export const deleteTeam = (id: string) => http.delete(`/teams/${id}`).then(() => undefined)

export const setTeamMembers = (id: string, user_ids: string[]) =>
  http.put<TeamRead>(`/teams/${id}/members`, { user_ids }).then((r) => r.data)
