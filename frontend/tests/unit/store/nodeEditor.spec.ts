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

const { warnSpy, errorSpy } = vi.hoisted(() => ({ warnSpy: vi.fn(), errorSpy: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { warning: warnSpy, error: errorSpy } }))

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

  it('confirmReviewBatch clears only review nodes among ids in one :batch', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', body: '<p>a</p>', mark_status: 'review' }),
      n({ id: 'b', sort_order: 1000, body: '<p>b</p>', mark_status: 'unmarked' }),
      n({ id: 'c', sort_order: 2000, body: '<p>c</p>', mark_status: 'review' }),
    ])
    batchSpy.mockResolvedValue([
      n({ id: 'a', body: '<p>a</p>', mark_status: 'unmarked' }),
      n({ id: 'c', sort_order: 2000, body: '<p>c</p>', mark_status: 'unmarked' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.confirmReviewBatch(['a', 'b', 'c'])
    // b 非 review → 不在 change set；a/c 各发空 change
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: {}, c: {} })
  })

  it('confirmReviewBatch is a no-op when no selected node is review', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>', mark_status: 'unmarked' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.confirmReviewBatch(['a'])
    expect(batchSpy).not.toHaveBeenCalled()
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

  it('createRelative computes sort_order and delegates to createNode (single write)', async () => {
    listSpy.mockResolvedValueOnce([
      n({ id: 'c1', heading_level: 1, sort_order: 1000, body: '<p>c1</p>' }),
      n({ id: 'a', parent_id: 'c1', depth: 1, sort_order: 2000, body: '<p>a</p>' }),
    ])
    createSpy.mockResolvedValue(n({ id: 'new' }))
    listSpy.mockResolvedValueOnce([
      n({ id: 'c1', heading_level: 1, sort_order: 1000 }),
      n({ id: 'new', sort_order: 1500 }),
      n({ id: 'a', parent_id: 'c1', depth: 1, sort_order: 2000 }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.createRelative('c1', 'after-node', { heading_level: null, kind: 'step' })
    expect(createSpy).toHaveBeenCalledWith('p1', { heading_level: null, kind: 'step', sort_order: 1500 })
    expect(reorderSpy).not.toHaveBeenCalled()
  })

  it('createRelative rebalances (reorder) first when neighbours leave no gap', async () => {
    listSpy.mockResolvedValueOnce([
      n({ id: 'p', sort_order: 1000, body: '<p>p</p>' }),
      n({ id: 'q', sort_order: 1001, body: '<p>q</p>' }),
    ])
    reorderSpy.mockResolvedValue(undefined)
    listSpy.mockResolvedValueOnce([ // reorder 重排后 *1000 等距
      n({ id: 'p', sort_order: 1000 }),
      n({ id: 'q', sort_order: 2000 }),
    ])
    createSpy.mockResolvedValue(n({ id: 'new' }))
    listSpy.mockResolvedValueOnce([
      n({ id: 'p', sort_order: 1000 }),
      n({ id: 'new', sort_order: 1500 }),
      n({ id: 'q', sort_order: 2000 }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.createRelative('p', 'after-node', { heading_level: null, kind: 'node' })
    expect(reorderSpy).toHaveBeenCalledWith('p1', ['p', 'q'])
    expect(createSpy).toHaveBeenCalledWith('p1', { heading_level: null, kind: 'node', sort_order: 1500 })
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

describe('nodeEditor store — redo + robust undo (E1)', () => {
  it('redo replays setLevel after undo (round-trip)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>x</p>' })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    expect(store.canRedo).toBe(false)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    await store.undo()
    expect(store.canUndo).toBe(false)
    expect(store.canRedo).toBe(true)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>x</p>' })])
    await store.redo()
    expect(store.nodeMap.get('a')?.heading_level).toBe(1)
    expect(store.canUndo).toBe(true)
    expect(store.canRedo).toBe(false)
  })

  it('a new op after undo clears the redo stack', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 1 })])
    await store.setLevel('a', 1)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null })])
    await store.undo()
    expect(store.canRedo).toBe(true)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', kind: 'step' })])
    await store.setKind('a', 'step')
    expect(store.canRedo).toBe(false)
  })

  it('failed undo re-pushes the entry and refetches (no silent loss)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1 })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    batchSpy.mockRejectedValueOnce(new Error('conflict'))
    listSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1 })]) // refetch
    await store.undo()
    expect(store.canUndo).toBe(true) // re-pushed, not lost
    expect(listSpy).toHaveBeenCalledTimes(2) // initial load + refetch
  })
})

describe('nodeEditor store — updateBody no-op guard (undo-on-load fix)', () => {
  it('unchanged body: no patch, no spurious undo entry', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(store.canUndo).toBe(false)
    await store.updateBody('a', '<p>x</p>') // identical to current body (e.g. editor mount emit)
    expect(patchSpy).not.toHaveBeenCalled()
    expect(store.canUndo).toBe(false)
  })

  it('changed body: patches and records undo', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>y</p>', revision: 2 }))
    await store.updateBody('a', '<p>y</p>')
    expect(patchSpy).toHaveBeenCalledWith('a', { body: '<p>y</p>' }, 1)
    expect(store.canUndo).toBe(true)
  })
})

const conflict409 = { response: { status: 409, data: { detail: { code: 'VERSION_CONFLICT' } } } }

describe('nodeEditor store — 409 conflict recovery (E4)', () => {
  it('updateBody 409: reload-wins — refetch, clear undo+redo, warn, no undo push', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 4 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    // seed an undo entry so we can prove the conflict clears history
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>old</p>', revision: 4 })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    // a concurrent change makes the body save conflict
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>server</p>', revision: 9 })]) // refetch
    await store.updateBody('a', '<p>mine</p>')
    expect(store.nodeMap.get('a')?.body).toBe('<p>server</p>')
    expect(store.nodeMap.get('a')?.revision).toBe(9)
    expect(store.canUndo).toBe(false) // history cleared (inverses now reference a dead state)
    expect(store.canRedo).toBe(false)
    expect(warnSpy).toHaveBeenCalled()
  })

  it('updateBody non-409 error: toasts and rethrows (transient path intact)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 1 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockRejectedValueOnce({ response: { status: 500, data: { detail: { message: '服务器错误' } } } })
    await expect(store.updateBody('a', '<p>new</p>')).rejects.toBeTruthy()
    expect(errorSpy).toHaveBeenCalled()
    expect(store.canUndo).toBe(false) // nothing recorded on failure
  })

  it('updateForm 409: same reload-wins recovery', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', kind: 'step', revision: 2 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', kind: 'step', revision: 7 })]) // refetch
    await store.updateForm('a', { type: 'NOTE' }, [])
    expect(store.nodeMap.get('a')?.revision).toBe(7)
    expect(warnSpy).toHaveBeenCalled()
  })

  it('E1 fix: undo whose inverse updateBody 409s clears history (no stale re-push)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>v1</p>', revision: 1 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>v2</p>', revision: 2 })) // do
    await store.updateBody('a', '<p>v2</p>')
    expect(store.canUndo).toBe(true)
    // undo's inverse re-applies v1, but a concurrent change makes it 409
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>server</p>', revision: 9 })]) // refetch
    await store.undo()
    expect(store.canUndo).toBe(false) // NOT re-pushed (the old inverse is stale)
    expect(store.canRedo).toBe(false)
    expect(store.nodeMap.get('a')?.body).toBe('<p>server</p>')
    expect(warnSpy).toHaveBeenCalled()
  })
})
