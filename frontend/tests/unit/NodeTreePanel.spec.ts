import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

function setup(nodes: Node[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  store.procedureId = 'p1'
  store.nodes = nodes
  store.selectedId = nodes[0]?.id ?? null
  const w = mount(NodeTreePanel, { global: { plugins: [ElementPlus, pinia] }, attachTo: document.body })
  return { w, store }
}

beforeEach(() => vi.restoreAllMocks())

describe('NodeTreePanel', () => {
  it('renders one NodeTreeRow per visible row', () => {
    const { w } = setup([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'a', depth: 1, sort_order: 1000, body: '<p>B</p>' }),
    ])
    expect(w.findAllComponents({ name: 'NodeTreeRow' })).toHaveLength(2)
  })

  it('row chip "l2" calls setLevel; "step" calls setKind', async () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 1, body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    const setKind = vi.spyOn(store, 'setKind').mockResolvedValue()
    const row = w.findComponent({ name: 'NodeTreeRow' })
    row.vm.$emit('chip', 'l2')
    row.vm.$emit('chip', 'step')
    expect(setLevel).toHaveBeenCalledWith('a', 2)
    expect(setKind).toHaveBeenCalledWith('a', 'step')
  })

  it('row chip "l0" sets level null (正文)', async () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 2, body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('chip', 'l0')
    expect(setLevel).toHaveBeenCalledWith('a', null)
  })

  it('row remove calls removeNode; select calls select', async () => {
    const { w, store } = setup([n({ id: 'a', body: '<p>A</p>' })])
    const remove = vi.spyOn(store, 'removeNode').mockResolvedValue()
    const row = w.findComponent({ name: 'NodeTreeRow' })
    row.vm.$emit('select')
    row.vm.$emit('remove')
    expect(store.selectedId).toBe('a')
    expect(remove).toHaveBeenCalledWith('a')
  })

  it('add button calls createNode (正文/普通)', async () => {
    const { w, store } = setup([n({ id: 'a', body: '<p>A</p>' })])
    const create = vi.spyOn(store, 'createNode').mockResolvedValue()
    await w.find('.np-add').trigger('click')
    expect(create).toHaveBeenCalledWith({ heading_level: null, kind: 'node' })
  })

  it('check builds selection; floating bar 设为L1 calls batchSetLevel then clears selection', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    const batch = vi.spyOn(store, 'batchSetLevel').mockResolvedValue()
    const rows = w.findAllComponents({ name: 'NodeTreeRow' })
    rows[0].vm.$emit('check', false)
    rows[1].vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(store.selection.size).toBe(2)
    await w.find('.np-bar-l1').trigger('click')
    expect(batch).toHaveBeenCalledWith(['a', 'b'], 1)
    expect(store.selection.size).toBe(0)
  })

  it('review filter toggle flips store.reviewOnly; count shown', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>', mark_status: 'review' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    expect(w.find('.np-review-count').text()).toContain('1')
    await w.find('.np-review-toggle').trigger('click')
    expect(store.reviewOnly).toBe(true)
  })

  it('drop reorders via computeReorder → store.reorder', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    const reorder = vi.spyOn(store, 'reorder').mockResolvedValue()
    const rows = w.findAllComponents({ name: 'NodeTreeRow' })
    rows[0].vm.$emit('dragstart', new Event('dragstart'))
    rows[1].vm.$emit('drop', new Event('drop'))
    expect(reorder).toHaveBeenCalledWith(['b', 'a'])
  })
})

describe('NodeTreePanel — cascade multiselect', () => {
  it('checking a heading cascades to its whole subtree (incl. heading)', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'a', parent_id: 'c1', sort_order: 1000, depth: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'c1', sort_order: 2000, depth: 1, body: '<p>B</p>' }),
    ])
    const rowC1 = w.findAllComponents({ name: 'NodeTreeRow' })[0]
    rowC1.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect([...store.selection].sort()).toEqual(['a', 'b', 'c1'])
    // checking again deselects the whole subtree
    rowC1.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(store.selection.size).toBe(0)
  })

  it('heading row gets indeterminate when only some descendants are selected', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'a', parent_id: 'c1', sort_order: 1000, depth: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'c1', sort_order: 2000, depth: 1, body: '<p>B</p>' }),
    ])
    store.selection = new Set(['a'])
    await w.vm.$nextTick()
    const rowC1 = w.findAllComponents({ name: 'NodeTreeRow' })[0]
    expect(rowC1.props('indeterminate')).toBe(true)
    expect(rowC1.props('selectedForMark')).toBe(false)
  })
})

describe('NodeTreePanel — readonly', () => {
  it('hides add button and floating bar; passes readonly to rows', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useNodeEditorStore()
    store.procedureId = 'p1'
    store.nodes = [n({ id: 'a', heading_level: 1, body: '<p>A</p>' })]
    store.selectedId = 'a'
    store.selection = new Set(['a']) // 即便有选中，readonly 也不显浮动条
    const w = mount(NodeTreePanel, {
      props: { readonly: true },
      global: { plugins: [ElementPlus, pinia] },
      attachTo: document.body,
    })
    expect(w.find('.np-add').exists()).toBe(false)
    expect(w.find('.np-bar').exists()).toBe(false)
    expect(w.findComponent({ name: 'NodeTreeRow' }).props('readonly')).toBe(true)
  })

  it('barStep sets only leaf members to step, skipping headings (with a warning)', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'a', parent_id: 'c1', sort_order: 1000, depth: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'c1', sort_order: 2000, depth: 1, body: '<p>B</p>' }),
    ])
    const setKind = vi.spyOn(store, 'batchSetKind').mockImplementation(() => Promise.resolve())
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
    store.selection = new Set(['c1', 'a', 'b'])
    await w.vm.$nextTick()
    await w.find('.np-bar-step').trigger('click')
    await flushPromises()
    expect(setKind).toHaveBeenCalledWith(['a', 'b'], 'step') // c1 heading skipped
    expect(warn).toHaveBeenCalled()
  })

  it('barStep no-ops with a warning when the selection is all headings', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'c2', heading_level: 1, sort_order: 1000, body: '<p>C2</p>' }),
    ])
    const setKind = vi.spyOn(store, 'batchSetKind').mockImplementation(() => Promise.resolve())
    const warn = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
    store.selection = new Set(['c1', 'c2'])
    await w.vm.$nextTick()
    await w.find('.np-bar-step').trigger('click')
    await flushPromises()
    expect(setKind).not.toHaveBeenCalled()
    expect(warn).toHaveBeenCalled()
  })
})

describe('NodeTreePanel — indent/outdent', () => {
  it('indent "in" on a content node promotes it to L1', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: null, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).toHaveBeenCalledWith('a', 1)
  })
  it('indent "in" on an L3 heading is a no-op (clamped)', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 3, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).not.toHaveBeenCalled()
  })
  it('indent on a step node is skipped', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: null, kind: 'step', body: '<p>S</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).not.toHaveBeenCalled()
  })
  it('indent "out" on an L1 heading demotes to 正文 (null)', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 1, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'out')
    expect(setLevel).toHaveBeenCalledWith('a', null)
  })
})
