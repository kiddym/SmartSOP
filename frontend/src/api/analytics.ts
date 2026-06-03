import { http } from './http'
import type {
  AnalyticsParams,
  WorkOrderAnalytics,
  CostAnalytics,
  AssetReliabilityAnalytics,
  InventoryAnalytics,
  RequestAnalytics,
  PersonnelAnalytics,
  TrendAnalytics,
} from '@/types/analytics'

export const getWorkOrderAnalytics = (params: AnalyticsParams = {}) =>
  http.get<WorkOrderAnalytics>('/analytics/work-orders', { params }).then((r) => r.data)
export const getCostAnalytics = (params: AnalyticsParams = {}) =>
  http.get<CostAnalytics>('/analytics/costs', { params }).then((r) => r.data)
export const getAssetReliabilityAnalytics = (params: AnalyticsParams = {}) =>
  http
    .get<AssetReliabilityAnalytics>('/analytics/asset-reliability', { params })
    .then((r) => r.data)
export const getInventoryAnalytics = (params: AnalyticsParams = {}) =>
  http.get<InventoryAnalytics>('/analytics/inventory', { params }).then((r) => r.data)
export const getRequestAnalytics = (params: AnalyticsParams = {}) =>
  http.get<RequestAnalytics>('/analytics/requests', { params }).then((r) => r.data)
export const getPersonnelAnalytics = (params: AnalyticsParams = {}) =>
  http.get<PersonnelAnalytics>('/analytics/personnel', { params }).then((r) => r.data)
export const getTrendAnalytics = (params: AnalyticsParams = {}) =>
  http.get<TrendAnalytics>('/analytics/trends', { params }).then((r) => r.data)

export const exportAnalytics = async (dashboard: string, params: AnalyticsParams = {}) => {
  const res = await http.get(`/analytics/${dashboard}/export`, { params, responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${dashboard}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
