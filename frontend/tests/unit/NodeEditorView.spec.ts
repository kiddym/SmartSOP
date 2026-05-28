import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'

const { loadSpy, undoSpy } = vi.hoisted(() => ({ loadSpy: vi.fn(), undoSpy: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: vi.fn().mockResolvedValue({ procedure: { name: '示例程序', code: 'SOP-001' } }),
}))

import NodeEditorView from '@/views/procedures/NodeEditorView.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'

const stubs = { NodeTreePanel: { template: '<div class="tree-stub" />' }, NodeDetailPanel: { template: '<div class="detail-stub" />' } }

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  vi.spyOn(store, 'load').mockImplementation(async (id: string) => { loadSpy(id); store.procedureId = id })
  vi.spyOn(store, 'undo').mockImplementation(async () => { undoSpy() })
  const w = mount(NodeEditorView, { props: { procedureId: 'p1' }, global: { plugins: [ElementPlus, pinia], stubs } })
  return { w, store }
}

beforeEach(() => vi.clearAllMocks())

describe('NodeEditorView', () => {
  it('loads nodes on mount and fetches procedure meta (name shown)', async () => {
    const { w } = mountView()
    await flushPromises()
    expect(loadSpy).toHaveBeenCalledWith('p1')
    expect(w.text()).toContain('示例程序')
  })

  it('mounts tree + detail panels', async () => {
    const { w } = mountView()
    await flushPromises()
    expect(w.find('.tree-stub').exists()).toBe(true)
    expect(w.find('.detail-stub').exists()).toBe(true)
  })

  it('undo button disabled until canUndo, then calls store.undo', async () => {
    const { w, store } = mountView()
    await flushPromises()
    const btn = w.find('.nev-undo')
    expect(btn.attributes('disabled')).toBeDefined()
    store.undoStack = [async () => {}]
    await w.vm.$nextTick()
    expect(w.find('.nev-undo').attributes('disabled')).toBeUndefined()
    await w.find('.nev-undo').trigger('click')
    expect(undoSpy).toHaveBeenCalled()
  })
})
