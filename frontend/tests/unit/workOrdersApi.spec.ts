import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, patch, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))
vi.mock('@/api/http', () => ({ http: { get, post, patch, put, delete: del } }))

import {
  listWorkOrders,
  listWorkOrderEvents,
  getWorkOrder,
  createWorkOrder,
  updateWorkOrder,
  deleteWorkOrder,
  setAssignees,
  setTeams,
  transitionWorkOrder,
  attachProcedure,
  detachProcedure,
  listWorkOrderActivities,
  addWorkOrderComment,
  getExecution,
  listLabor,
  createLabor,
  startTimer,
  stopTimer,
  updateLabor,
  deleteLabor,
  listAdditionalCosts,
  createAdditionalCost,
  updateAdditionalCost,
  deleteAdditionalCost,
  getCostSummary,
} from '@/api/workOrders'
import {
  listWorkOrderCategories,
  createWorkOrderCategory,
  updateWorkOrderCategory,
  deleteWorkOrderCategory,
} from '@/api/workOrderCategories'
import { listTimeCategories } from '@/api/timeCategories'
import { listCostCategories } from '@/api/costCategories'

describe('work orders api', () => {
  beforeEach(() => {
    for (const m of [get, post, patch, put, del]) m.mockReset().mockResolvedValue({ data: {} })
  })

  it('listWorkOrders GET /work-orders (no params)', async () => {
    await listWorkOrders()
    expect(get).toHaveBeenCalledWith('/work-orders', { params: {} })
  })
  it('listWorkOrders GET with filters', async () => {
    await listWorkOrders({ status: 'OPEN', assignee_id: 'u1', procedure_attached: true })
    expect(get).toHaveBeenCalledWith('/work-orders', {
      params: { status: 'OPEN', assignee_id: 'u1', procedure_attached: true },
    })
  })
  it('listWorkOrderEvents GET /work-orders/events with start/end', async () => {
    await listWorkOrderEvents('2026-06-01', '2026-06-30')
    expect(get).toHaveBeenCalledWith('/work-orders/events', {
      params: { start: '2026-06-01', end: '2026-06-30' },
    })
  })
  it('getWorkOrder GET /work-orders/{id}', async () => {
    await getWorkOrder('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1')
  })
  it('createWorkOrder POST /work-orders', async () => {
    await createWorkOrder({ title: 'T' })
    expect(post).toHaveBeenCalledWith('/work-orders', { title: 'T' })
  })
  it('updateWorkOrder PATCH /work-orders/{id}', async () => {
    await updateWorkOrder('w1', { title: 'T2' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1', { title: 'T2' })
  })
  it('deleteWorkOrder DELETE /work-orders/{id}', async () => {
    await deleteWorkOrder('w1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1')
  })
  it('setAssignees PUT /assignees', async () => {
    await setAssignees('w1', { user_ids: ['u1'] })
    expect(put).toHaveBeenCalledWith('/work-orders/w1/assignees', { user_ids: ['u1'] })
  })
  it('setTeams PUT /teams', async () => {
    await setTeams('w1', { team_ids: ['t1'] })
    expect(put).toHaveBeenCalledWith('/work-orders/w1/teams', { team_ids: ['t1'] })
  })
  it('transitionWorkOrder POST /transition', async () => {
    await transitionWorkOrder('w1', { to_status: 'IN_PROGRESS', note: '' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/transition', {
      to_status: 'IN_PROGRESS',
      note: '',
    })
  })
  it('attachProcedure POST /attach-procedure', async () => {
    await attachProcedure('w1', { procedure_id: 'p1' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/attach-procedure', { procedure_id: 'p1' })
  })
  it('detachProcedure DELETE /procedure', async () => {
    await detachProcedure('w1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/procedure')
  })
  it('listWorkOrderActivities GET /activities', async () => {
    await listWorkOrderActivities('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/activities')
  })
  it('addWorkOrderComment POST /activities', async () => {
    await addWorkOrderComment('w1', { comment: 'hi' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/activities', { comment: 'hi' })
  })
  it('getExecution GET /execution', async () => {
    await getExecution('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/execution')
  })
  it('listLabor GET /labor', async () => {
    await listLabor('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/labor')
  })
  it('createLabor POST /labor', async () => {
    await createLabor('w1', { duration_seconds: 600 })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor', { duration_seconds: 600 })
  })
  it('startTimer POST /labor/start', async () => {
    await startTimer('w1', { user_id: 'u1' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor/start', { user_id: 'u1' })
  })
  it('stopTimer POST /labor/{lid}/stop', async () => {
    await stopTimer('w1', 'l1')
    expect(post).toHaveBeenCalledWith('/work-orders/w1/labor/l1/stop')
  })
  it('updateLabor PATCH /labor/{lid}', async () => {
    await updateLabor('w1', 'l1', { notes: 'x' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1/labor/l1', { notes: 'x' })
  })
  it('deleteLabor DELETE /labor/{lid}', async () => {
    await deleteLabor('w1', 'l1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/labor/l1')
  })
  it('listAdditionalCosts GET /additional-costs', async () => {
    await listAdditionalCosts('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/additional-costs')
  })
  it('createAdditionalCost POST /additional-costs', async () => {
    await createAdditionalCost('w1', { title: 'C', amount: '10' })
    expect(post).toHaveBeenCalledWith('/work-orders/w1/additional-costs', {
      title: 'C',
      amount: '10',
    })
  })
  it('updateAdditionalCost PATCH /additional-costs/{cid}', async () => {
    await updateAdditionalCost('w1', 'c1', { amount: '20' })
    expect(patch).toHaveBeenCalledWith('/work-orders/w1/additional-costs/c1', { amount: '20' })
  })
  it('deleteAdditionalCost DELETE /additional-costs/{cid}', async () => {
    await deleteAdditionalCost('w1', 'c1')
    expect(del).toHaveBeenCalledWith('/work-orders/w1/additional-costs/c1')
  })
  it('getCostSummary GET /cost-summary', async () => {
    await getCostSummary('w1')
    expect(get).toHaveBeenCalledWith('/work-orders/w1/cost-summary')
  })

  it('listWorkOrderCategories GET /work-order-categories', async () => {
    await listWorkOrderCategories()
    expect(get).toHaveBeenCalledWith('/work-order-categories')
  })
  it('createWorkOrderCategory POST', async () => {
    await createWorkOrderCategory({ name: 'C' })
    expect(post).toHaveBeenCalledWith('/work-order-categories', { name: 'C' })
  })
  it('updateWorkOrderCategory PATCH /{id}', async () => {
    await updateWorkOrderCategory('c1', { name: 'C2' })
    expect(patch).toHaveBeenCalledWith('/work-order-categories/c1', { name: 'C2' })
  })
  it('deleteWorkOrderCategory DELETE /{id}', async () => {
    await deleteWorkOrderCategory('c1')
    expect(del).toHaveBeenCalledWith('/work-order-categories/c1')
  })
  it('listTimeCategories GET /time-categories', async () => {
    await listTimeCategories()
    expect(get).toHaveBeenCalledWith('/time-categories')
  })
  it('listCostCategories GET /cost-categories', async () => {
    await listCostCategories()
    expect(get).toHaveBeenCalledWith('/cost-categories')
  })
})
