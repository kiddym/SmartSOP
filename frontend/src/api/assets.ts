import { http } from './http'
import type {
  AssetRead,
  AssetCreate,
  AssetUpdate,
  AssetMini,
  DowntimeRead,
  DowntimeCreate,
  DowntimeClose,
} from '@/types/maindata'

export const listAssets = () => http.get<AssetRead[]>('/assets').then((r) => r.data)
export const listAssetsMini = () => http.get<AssetMini[]>('/assets/mini').then((r) => r.data)
export const createAsset = (p: AssetCreate) =>
  http.post<AssetRead>('/assets', p).then((r) => r.data)
export const updateAsset = (id: string, p: AssetUpdate) =>
  http.patch<AssetRead>(`/assets/${id}`, p).then((r) => r.data)
export const deleteAsset = (id: string) => http.delete(`/assets/${id}`).then(() => undefined)
export const listDowntimes = (assetId: string) =>
  http.get<DowntimeRead[]>(`/assets/${assetId}/downtimes`).then((r) => r.data)
export const addDowntime = (assetId: string, p: DowntimeCreate) =>
  http.post<DowntimeRead>(`/assets/${assetId}/downtimes`, p).then((r) => r.data)
export const closeDowntime = (assetId: string, downtimeId: string, p: DowntimeClose) =>
  http.patch<DowntimeRead>(`/assets/${assetId}/downtimes/${downtimeId}`, p).then((r) => r.data)
