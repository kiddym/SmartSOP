import { http } from './http'
import type {
  AssetRead,
  AssetStatus,
  AssetCreate,
  AssetUpdate,
  AssetMini,
  DowntimeRead,
  DowntimeCreate,
  DowntimeClose,
} from '@/types/maindata'

export interface ListAssetsParams {
  location_id?: string
  category_id?: string
  status?: AssetStatus
  parent_id?: string
}
export const listAssets = (params: ListAssetsParams = {}) =>
  http.get<AssetRead[]>('/assets', { params }).then((r) => r.data)
export const getAsset = (id: string) => http.get<AssetRead>(`/assets/${id}`).then((r) => r.data)
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
