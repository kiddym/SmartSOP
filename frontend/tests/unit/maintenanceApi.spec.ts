import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, delete: del } }))

import {
  listRequests,
  getRequest,
  createRequest,
  updateRequest,
  deleteRequest,
  approveRequest,
  rejectRequest,
  cancelRequest,
  listRequestActivities,
  addRequestComment,
} from '@/api/requests'
import {
  listPMs,
  getPM,
  createPM,
  updatePM,
  deletePM,
  enablePM,
  disablePM,
  generatePM,
  listPMActivities,
  addPMComment,
} from '@/api/preventiveMaintenances'
import {
  listMeters,
  getMeter,
  createMeter,
  updateMeter,
  deleteMeter,
  listReadings,
  submitReading,
  listTriggers,
  createTrigger,
  updateTrigger,
  deleteTrigger,
  enableTrigger,
  disableTrigger,
} from '@/api/meters'

describe('maintenance api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, del]) m.mockReset().mockResolvedValue({ data: [] })
  })

  // requests
  it('listRequests GET /requests (no params)', async () => {
    await listRequests()
    expect(get).toHaveBeenCalledWith('/requests', { params: {} })
  })
  it('listRequests GET /requests with filters', async () => {
    await listRequests({ status: 'PENDING', priority: 'HIGH', asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/requests', {
      params: { status: 'PENDING', priority: 'HIGH', asset_id: 'a1', location_id: 'l1' },
    })
  })
  it('getRequest GET /requests/{id}', async () => {
    await getRequest('r1')
    expect(get).toHaveBeenCalledWith('/requests/r1')
  })
  it('createRequest POST /requests', async () => {
    await createRequest({ title: 'T' })
    expect(post).toHaveBeenCalledWith('/requests', { title: 'T' })
  })
  it('updateRequest PATCH /requests/{id}', async () => {
    await updateRequest('r1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/requests/r1', { title: 'T2' })
  })
  it('deleteRequest DELETE /requests/{id}', async () => {
    await deleteRequest('r1')
    expect(del).toHaveBeenCalledWith('/requests/r1')
  })
  it('approveRequest POST /approve', async () => {
    await approveRequest('r1', {
      note: 'ok',
      primary_user_id: 'u1',
      assignee_ids: [],
      team_ids: [],
    })
    expect(post).toHaveBeenCalledWith('/requests/r1/approve', {
      note: 'ok',
      primary_user_id: 'u1',
      assignee_ids: [],
      team_ids: [],
    })
  })
  it('rejectRequest POST /reject', async () => {
    await rejectRequest('r1', { reason: 'no' })
    expect(post).toHaveBeenCalledWith('/requests/r1/reject', { reason: 'no' })
  })
  it('cancelRequest POST /cancel', async () => {
    await cancelRequest('r1', { reason: 'x' })
    expect(post).toHaveBeenCalledWith('/requests/r1/cancel', { reason: 'x' })
  })
  it('listRequestActivities GET /activities', async () => {
    await listRequestActivities('r1')
    expect(get).toHaveBeenCalledWith('/requests/r1/activities')
  })
  it('addRequestComment POST /activities', async () => {
    await addRequestComment('r1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/requests/r1/activities', { comment: 'hi' })
  })

  // PM
  it('listPMs GET /preventive-maintenances (no params)', async () => {
    await listPMs()
    expect(get).toHaveBeenCalledWith('/preventive-maintenances', { params: {} })
  })
  it('listPMs GET with filters', async () => {
    await listPMs({ is_enabled: true, asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/preventive-maintenances', {
      params: { is_enabled: true, asset_id: 'a1', location_id: 'l1' },
    })
  })
  it('getPM GET /{id}', async () => {
    await getPM('p1')
    expect(get).toHaveBeenCalledWith('/preventive-maintenances/p1')
  })
  it('createPM POST', async () => {
    await createPM({
      title: 'T',
      start_date: '2026-06-03',
      frequency_unit: 'DAY',
      frequency_value: 7,
    })
    expect(post).toHaveBeenCalledWith('/preventive-maintenances', {
      title: 'T',
      start_date: '2026-06-03',
      frequency_unit: 'DAY',
      frequency_value: 7,
    })
  })
  it('updatePM PATCH /{id}', async () => {
    await updatePM('p1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/preventive-maintenances/p1', { title: 'T2' })
  })
  it('deletePM DELETE /{id}', async () => {
    await deletePM('p1')
    expect(del).toHaveBeenCalledWith('/preventive-maintenances/p1')
  })
  it('enablePM POST /enable', async () => {
    await enablePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/enable')
  })
  it('disablePM POST /disable', async () => {
    await disablePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/disable')
  })
  it('generatePM POST /generate', async () => {
    await generatePM('p1')
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/generate')
  })
  it('listPMActivities GET /activities', async () => {
    await listPMActivities('p1')
    expect(get).toHaveBeenCalledWith('/preventive-maintenances/p1/activities')
  })
  it('addPMComment POST /comments', async () => {
    await addPMComment('p1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/preventive-maintenances/p1/comments', { comment: 'hi' })
  })

  // meters
  it('listMeters GET /meters (no params)', async () => {
    await listMeters()
    expect(get).toHaveBeenCalledWith('/meters', { params: {} })
  })
  it('listMeters GET with filters', async () => {
    await listMeters({ asset_id: 'a1', location_id: 'l1' })
    expect(get).toHaveBeenCalledWith('/meters', { params: { asset_id: 'a1', location_id: 'l1' } })
  })
  it('getMeter GET /{id}', async () => {
    await getMeter('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1')
  })
  it('createMeter POST', async () => {
    await createMeter({ name: 'M' })
    expect(post).toHaveBeenCalledWith('/meters', { name: 'M' })
  })
  it('updateMeter PATCH /{id}', async () => {
    await updateMeter('m1', { unit: 'h' })
    expect(patch).toHaveBeenCalledWith('/meters/m1', { unit: 'h' })
  })
  it('deleteMeter DELETE /{id}', async () => {
    await deleteMeter('m1')
    expect(del).toHaveBeenCalledWith('/meters/m1')
  })
  it('listReadings GET /readings', async () => {
    await listReadings('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1/readings')
  })
  it('submitReading POST /readings', async () => {
    await submitReading('m1', { value: '12.5' })
    expect(post).toHaveBeenCalledWith('/meters/m1/readings', { value: '12.5' })
  })
  it('listTriggers GET /triggers', async () => {
    await listTriggers('m1')
    expect(get).toHaveBeenCalledWith('/meters/m1/triggers')
  })
  it('createTrigger POST /triggers', async () => {
    await createTrigger('m1', { name: 'T', comparator: 'MORE_THAN', threshold: '100', title: 'X' })
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers', {
      name: 'T',
      comparator: 'MORE_THAN',
      threshold: '100',
      title: 'X',
    })
  })
  it('updateTrigger PATCH /triggers/{tid}', async () => {
    await updateTrigger('m1', 't1', { threshold: '200' })
    expect(patch).toHaveBeenCalledWith('/meters/m1/triggers/t1', { threshold: '200' })
  })
  it('deleteTrigger DELETE /triggers/{tid}', async () => {
    await deleteTrigger('m1', 't1')
    expect(del).toHaveBeenCalledWith('/meters/m1/triggers/t1')
  })
  it('enableTrigger POST /enable', async () => {
    await enableTrigger('m1', 't1')
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers/t1/enable')
  })
  it('disableTrigger POST /disable', async () => {
    await disableTrigger('m1', 't1')
    expect(post).toHaveBeenCalledWith('/meters/m1/triggers/t1/disable')
  })
})
