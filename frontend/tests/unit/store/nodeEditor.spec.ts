import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { listSpy, patchSpy, createSpy, deleteSpy, batchSpy, reorderSpy } = vi.hoisted(() => ({
  listSpy: vi.fn(), patchSpy: vi.fn(), createSpy: vi.fn(),
  deleteSpy: vi.fn(), batchSpy: vi.fn(), reorderSpy: vi.fn(),
}))
vi.mock('@/api/nodes', () => ({
  listNodes: listSpy, patchNode: patchSpy, createNode: createSpy,
  deleteNode: deleteSpy, batchUpdateNodes: batchSpy, reorderNodes: reorderSpy,
}))

import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
})

describe('nodeEditor store — load + derive', () => {
  it('load fetches nodes and selects the first row', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>目的</p>' }),
      n({ id: 'b', parent_id: 'a', sort_order: 1000, depth: 1, body: '<p>正文</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(listSpy).toHaveBeenCalledWith('p1')
    expect(store.nodes).toHaveLength(2)
    expect(store.selectedId).toBe('a')
    expect(store.rows.map((r) => r.title)).toEqual(['目的', '正文'])
  })

  it('toggleExpand collapses a node and hides descendants in rows', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'a', sort_order: 1000, depth: 1, body: '<p>b</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    store.toggleExpand('a')
    expect(store.rows.map((r) => r.node.id)).toEqual(['a'])
  })

  it('reviewCount + reviewOnly filter', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>', mark_status: 'review' }),
      n({ id: 'b', sort_order: 1000, body: '<p>b</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(store.reviewCount).toBe(1)
    store.reviewOnly = true
    expect(store.rows.map((r) => r.node.id)).toEqual(['a'])
  })

  it('load sets loadError on failure', async () => {
    listSpy.mockRejectedValue(new Error('boom'))
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(store.loadError).toBe(true)
    expect(store.nodes).toEqual([])
  })
})
