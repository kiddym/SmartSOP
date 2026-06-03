import { http } from './http'
import type { PermissionGroup } from '@/types/platform'

// 后端路由前缀 /permissions（见 backend/app/routers/permissions.py）。
export const listPermissions = () => http.get<PermissionGroup[]>('/permissions').then((r) => r.data)
