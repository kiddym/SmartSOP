import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get } }))

import {
  getWorkOrderAnalytics,
  getCostAnalytics,
  getAssetReliabilityAnalytics,
  getInventoryAnalytics,
  getRequestAnalytics,
  getPersonnelAnalytics,
  getTrendAnalytics,
  exportAnalytics,
} from '@/api/analytics'

describe('analytics api', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: {} })
  })

  it('getWorkOrderAnalytics GET /analytics/work-orders', async () => {
    await getWorkOrderAnalytics({ date_from: '2026-01-01', date_to: '2026-03-31' })
    expect(get).toHaveBeenCalledWith('/analytics/work-orders', {
      params: { date_from: '2026-01-01', date_to: '2026-03-31' },
    })
  })
  it('getCostAnalytics GET /analytics/costs', async () => {
    await getCostAnalytics({ asset_id: 'a1' })
    expect(get).toHaveBeenCalledWith('/analytics/costs', { params: { asset_id: 'a1' } })
  })
  it('getAssetReliabilityAnalytics GET /analytics/asset-reliability', async () => {
    await getAssetReliabilityAnalytics({ category_id: 'c1' })
    expect(get).toHaveBeenCalledWith('/analytics/asset-reliability', {
      params: { category_id: 'c1' },
    })
  })
  it('getInventoryAnalytics GET /analytics/inventory', async () => {
    await getInventoryAnalytics({ category_id: 'pc1' })
    expect(get).toHaveBeenCalledWith('/analytics/inventory', { params: { category_id: 'pc1' } })
  })
  it('getRequestAnalytics GET /analytics/requests', async () => {
    await getRequestAnalytics({})
    expect(get).toHaveBeenCalledWith('/analytics/requests', { params: {} })
  })
  it('getPersonnelAnalytics GET /analytics/personnel', async () => {
    await getPersonnelAnalytics({ date_from: '2026-01-01' })
    expect(get).toHaveBeenCalledWith('/analytics/personnel', {
      params: { date_from: '2026-01-01' },
    })
  })
  it('getTrendAnalytics GET /analytics/trends', async () => {
    await getTrendAnalytics({ granularity: 'week' })
    expect(get).toHaveBeenCalledWith('/analytics/trends', { params: { granularity: 'week' } })
  })

  it('exportAnalytics GET /analytics/{dashboard}/export blob', async () => {
    const blob = new Blob(['x'], { type: 'text/csv' })
    get.mockResolvedValueOnce({ data: blob })
    const createSpy = vi.fn().mockReturnValue('blob:x')
    const revokeSpy = vi.fn()
    URL.createObjectURL = createSpy as unknown as typeof URL.createObjectURL
    URL.revokeObjectURL = revokeSpy as unknown as typeof URL.revokeObjectURL
    await exportAnalytics('work-orders', { date_from: '2026-01-01' })
    expect(get).toHaveBeenCalledWith('/analytics/work-orders/export', {
      params: { date_from: '2026-01-01' },
      responseType: 'blob',
    })
    expect(createSpy).toHaveBeenCalled()
  })
})
