import { http } from './http'
import type { AssetCategoryRead, AssetCategoryCreate, AssetCategoryUpdate } from '@/types/maindata'

export const listAssetCategories = () =>
  http.get<AssetCategoryRead[]>('/asset-categories').then((r) => r.data)
export const createAssetCategory = (p: AssetCategoryCreate) =>
  http.post<AssetCategoryRead>('/asset-categories', p).then((r) => r.data)
export const updateAssetCategory = (id: string, p: AssetCategoryUpdate) =>
  http.patch<AssetCategoryRead>(`/asset-categories/${id}`, p).then((r) => r.data)
export const deleteAssetCategory = (id: string) =>
  http.delete(`/asset-categories/${id}`).then(() => undefined)
