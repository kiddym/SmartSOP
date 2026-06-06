import { http } from './http'
import type { DeprecationRead, DeprecationUpdate } from '@/types/deprecation'

// 折旧端点：/api/v1/assets/{assetId}/deprecation。GET 无折旧时后端返回 null。
export const getDeprecation = (assetId: string) =>
  http.get<DeprecationRead | null>(`/assets/${assetId}/deprecation`).then((r) => r.data)
export const putDeprecation = (assetId: string, p: DeprecationUpdate) =>
  http.put<DeprecationRead>(`/assets/${assetId}/deprecation`, p).then((r) => r.data)
export const deleteDeprecation = (assetId: string) =>
  http.delete(`/assets/${assetId}/deprecation`).then(() => undefined)
