import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, delete: del } }))

import {
  listLocations,
  listLocationsMini,
  createLocation,
  updateLocation,
  deleteLocation,
} from '@/api/locations'
import {
  listAssets,
  listAssetsMini,
  createAsset,
  updateAsset,
  deleteAsset,
  listDowntimes,
  addDowntime,
  closeDowntime,
} from '@/api/assets'
import {
  listAssetCategories,
  createAssetCategory,
  updateAssetCategory,
  deleteAssetCategory,
} from '@/api/assetCategories'

describe('maindata api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })

  it('listLocations GET /locations', async () => {
    await listLocations()
    expect(get).toHaveBeenCalledWith('/locations')
  })
  it('listLocationsMini GET /locations/mini', async () => {
    await listLocationsMini()
    expect(get).toHaveBeenCalledWith('/locations/mini')
  })
  it('createLocation POST /locations', async () => {
    await createLocation({ name: 'L' })
    expect(post).toHaveBeenCalledWith('/locations', { name: 'L' })
  })
  it('updateLocation PATCH /locations/{id}', async () => {
    await updateLocation('l1', { name: 'X' })
    expect(patch).toHaveBeenCalledWith('/locations/l1', { name: 'X' })
  })
  it('deleteLocation DELETE /locations/{id}', async () => {
    await deleteLocation('l1')
    expect(del).toHaveBeenCalledWith('/locations/l1')
  })

  it('listAssets GET /assets', async () => {
    await listAssets()
    expect(get).toHaveBeenCalledWith('/assets')
  })
  it('listAssetsMini GET /assets/mini', async () => {
    await listAssetsMini()
    expect(get).toHaveBeenCalledWith('/assets/mini')
  })
  it('createAsset POST /assets', async () => {
    await createAsset({ name: 'A', status: 'OPERATIONAL' })
    expect(post).toHaveBeenCalledWith('/assets', { name: 'A', status: 'OPERATIONAL' })
  })
  it('updateAsset PATCH /assets/{id}', async () => {
    await updateAsset('a1', { status: 'DOWN' })
    expect(patch).toHaveBeenCalledWith('/assets/a1', { status: 'DOWN' })
  })
  it('deleteAsset DELETE /assets/{id}', async () => {
    await deleteAsset('a1')
    expect(del).toHaveBeenCalledWith('/assets/a1')
  })
  it('listDowntimes GET /assets/{id}/downtimes', async () => {
    await listDowntimes('a1')
    expect(get).toHaveBeenCalledWith('/assets/a1/downtimes')
  })
  it('addDowntime POST /assets/{id}/downtimes', async () => {
    await addDowntime('a1', { started_at: '2026-06-01T00:00:00', reason: 'r' })
    expect(post).toHaveBeenCalledWith('/assets/a1/downtimes', {
      started_at: '2026-06-01T00:00:00',
      reason: 'r',
    })
  })
  it('closeDowntime PATCH /assets/{id}/downtimes/{dtId}', async () => {
    await closeDowntime('a1', 'd1', { ended_at: '2026-06-02T00:00:00' })
    expect(patch).toHaveBeenCalledWith('/assets/a1/downtimes/d1', {
      ended_at: '2026-06-02T00:00:00',
    })
  })

  it('listAssetCategories GET /asset-categories', async () => {
    await listAssetCategories()
    expect(get).toHaveBeenCalledWith('/asset-categories')
  })
  it('createAssetCategory POST /asset-categories', async () => {
    await createAssetCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/asset-categories', { name: 'C' })
  })
  it('updateAssetCategory PATCH /asset-categories/{id}', async () => {
    await updateAssetCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/asset-categories/c1', { name: 'C2' })
  })
  it('deleteAssetCategory DELETE /asset-categories/{id}', async () => {
    await deleteAssetCategory('c1')
    expect(del).toHaveBeenCalledWith('/asset-categories/c1')
  })
})
