import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ http: { get } }))

import {
  exportEntityCsv,
  exportWorkOrders,
  exportAssets,
  exportLocations,
  exportParts,
  exportMeters,
} from '@/api/exports'

describe('exports api', () => {
  beforeEach(() => {
    const blob = new Blob(['x'], { type: 'text/csv' })
    get.mockReset().mockResolvedValue({ data: blob })
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x') as unknown as typeof URL.createObjectURL
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL
  })

  it.each([
    ['work-orders', exportWorkOrders],
    ['assets', exportAssets],
    ['locations', exportLocations],
    ['parts', exportParts],
    ['meters', exportMeters],
  ] as const)('%s GET /exports/%s as blob and triggers download', async (entity, fn) => {
    await fn()
    expect(get).toHaveBeenCalledWith(`/exports/${entity}`, { responseType: 'blob' })
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('exportEntityCsv passes the given entity through', async () => {
    await exportEntityCsv('parts')
    expect(get).toHaveBeenCalledWith('/exports/parts', { responseType: 'blob' })
  })
})
