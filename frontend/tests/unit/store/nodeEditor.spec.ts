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

describe('nodeEditor store — structural edits', () => {
  it('setLevel routes through :batch and replaces nodes with the full list', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 2, body: '<p>x</p>', code: '1' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', 2)
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { set_heading_level: true, heading_level: 2 } })
    expect(store.nodeMap.get('a')?.heading_level).toBe(2)
  })

  it('setLevel to null (降为正文) sends set_heading_level true + null', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: 2, body: '<p>x</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', null)
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { set_heading_level: true, heading_level: null } })
  })

  it('batchSetLevel applies one level to many (γ path)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000, body: '<p>b</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 3 }), n({ id: 'b', heading_level: 3, sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetLevel(['a', 'b'], 3)
    expect(batchSpy).toHaveBeenCalledWith('p1', {
      a: { set_heading_level: true, heading_level: 3 },
      b: { set_heading_level: true, heading_level: 3 },
    })
  })

  it('confirmReview sends an empty :batch change (backend clears review)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>', mark_status: 'review' })])
    batchSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>', mark_status: 'unmarked' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.confirmReview('a')
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: {} })
    expect(store.nodeMap.get('a')?.mark_status).toBe('unmarked')
  })

  it('createNode then re-GETs the full list', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>a</p>' })])
    createSpy.mockResolvedValue(n({ id: 'new', body: '' }))
    listSpy.mockResolvedValueOnce([
      n({ id: 'a', heading_level: 1, body: '<p>a</p>' }),
      n({ id: 'new', sort_order: 1000, body: '' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.createNode({ heading_level: null })
    expect(createSpy).toHaveBeenCalledWith('p1', { heading_level: null })
    expect(store.nodes.map((x) => x.id)).toEqual(['a', 'new'])
  })

  it('deleteNode then re-GETs', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000 })])
    deleteSpy.mockResolvedValue(undefined)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>a</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.removeNode('b')
    expect(deleteSpy).toHaveBeenCalledWith('b')
    expect(store.nodes.map((x) => x.id)).toEqual(['a'])
  })

  it('reorder then re-GETs', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a' }), n({ id: 'b', sort_order: 1000 })])
    reorderSpy.mockResolvedValue(undefined)
    listSpy.mockResolvedValueOnce([n({ id: 'b' }), n({ id: 'a', sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.reorder(['b', 'a'])
    expect(reorderSpy).toHaveBeenCalledWith('p1', ['b', 'a'])
    expect(store.nodes.map((x) => x.id)).toEqual(['b', 'a'])
  })
})

describe('nodeEditor store — content edits + undo', () => {
  it('updateBody PATCHes with the node revision and updates that node only', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 4 })])
    patchSpy.mockResolvedValue(n({ id: 'a', body: '<p>new</p>', revision: 5 }))
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateBody('a', '<p>new</p>')
    expect(patchSpy).toHaveBeenCalledWith('a', { body: '<p>new</p>' }, 4)
    expect(store.nodeMap.get('a')?.body).toBe('<p>new</p>')
    expect(store.nodeMap.get('a')?.revision).toBe(5)
  })

  it('updateForm PATCHes input_schema + attachment_marks', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', kind: 'step', revision: 2 })])
    patchSpy.mockResolvedValue(n({ id: 'a', kind: 'step', revision: 3, input_schema: { type: 'NOTE' } }))
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateForm('a', { type: 'NOTE' }, [])
    expect(patchSpy).toHaveBeenCalledWith('a', { input_schema: { type: 'NOTE' }, attachment_marks: [] }, 2)
  })

  it('undo of setLevel issues the inverse :batch', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 2, body: '<p>x</p>' })]) // do
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null, body: '<p>x</p>' })]) // undo
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', 2)
    expect(store.canUndo).toBe(true)
    await store.undo()
    expect(batchSpy).toHaveBeenLastCalledWith('p1', { a: { set_heading_level: true, heading_level: null } })
    expect(store.nodeMap.get('a')?.heading_level).toBe(null)
    expect(store.canUndo).toBe(false)
  })

  it('undo of updateBody restores the previous body', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 1 })])
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>new</p>', revision: 2 })) // do
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>old</p>', revision: 3 })) // undo
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateBody('a', '<p>new</p>')
    await store.undo()
    expect(patchSpy).toHaveBeenLastCalledWith('a', { body: '<p>old</p>' }, 2)
    expect(store.nodeMap.get('a')?.body).toBe('<p>old</p>')
  })
})

describe('nodeEditor store — batchSetKind', () => {
  it('batchSetKind sends kind for each id and replaces nodes with the full list', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000, body: '<p>b</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', kind: 'step' }), n({ id: 'b', kind: 'step', sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetKind(['a', 'b'], 'step')
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { kind: 'step' }, b: { kind: 'step' } })
    expect(store.nodeMap.get('a')?.kind).toBe('step')
  })

  it('batchSetKind on empty ids is a no-op', async () => {
    listSpy.mockResolvedValue([n({ id: 'a' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetKind([], 'step')
    expect(batchSpy).not.toHaveBeenCalled()
  })
})
