import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('@/api/http', () => ({
  http: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { http } from '@/api/http'
import {
  listNodes,
  patchNode,
  createNode,
  deleteNode,
  batchUpdateNodes,
  reorderNodes,
} from '@/api/nodes'

const mocked = http as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('api/nodes', () => {
  it('listNodes GETs the procedure nodes and unwraps data', async () => {
    mocked.get.mockResolvedValue({ data: [{ id: 'n1' }] })
    const out = await listNodes('p1')
    expect(mocked.get).toHaveBeenCalledWith('/procedures/p1/nodes')
    expect(out).toEqual([{ id: 'n1' }])
  })

  it('patchNode PATCHes /nodes/{id} with If-Match revision and skipErrorToast', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'n1' } })
    await patchNode('n1', { body: '<p>x</p>' }, 3)
    expect(mocked.patch).toHaveBeenCalledWith(
      '/nodes/n1',
      { body: '<p>x</p>' },
      { headers: { 'If-Match': '3' }, skipErrorToast: true },
    )
  })

  it('createNode POSTs to /procedures/{id}/nodes', async () => {
    mocked.post.mockResolvedValue({ data: { id: 'new' } })
    const out = await createNode('p1', { heading_level: 1, body: '<p>A</p>' })
    expect(mocked.post).toHaveBeenCalledWith('/procedures/p1/nodes', {
      heading_level: 1,
      body: '<p>A</p>',
    })
    expect(out).toEqual({ id: 'new' })
  })

  it('deleteNode DELETEs /nodes/{id}', async () => {
    mocked.delete.mockResolvedValue({})
    await deleteNode('n1')
    expect(mocked.delete).toHaveBeenCalledWith('/nodes/n1')
  })

  it('batchUpdateNodes PATCHes the :batch endpoint and returns the full list', async () => {
    mocked.patch.mockResolvedValue({ data: [{ id: 'n1' }, { id: 'n2' }] })
    const out = await batchUpdateNodes('p1', { n1: { set_heading_level: true, heading_level: 2 } })
    expect(mocked.patch).toHaveBeenCalledWith('/procedures/p1/nodes:batch', {
      updates: { n1: { set_heading_level: true, heading_level: 2 } },
    })
    expect(out).toHaveLength(2)
  })

  it('reorderNodes POSTs ordered_ids', async () => {
    mocked.post.mockResolvedValue({})
    await reorderNodes('p1', ['n2', 'n1'])
    expect(mocked.post).toHaveBeenCalledWith('/procedures/p1/nodes/reorder', {
      ordered_ids: ['n2', 'n1'],
    })
  })
})
