import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

const stubs = {
  RichTextEditor: { name: 'RichTextEditor', template: '<div class="rte-stub" />', props: ['modelValue', 'readonly'], emits: ['update:modelValue'] },
  StepFormFields: { name: 'StepFormFields', template: '<div class="sff-stub" />', props: ['schema', 'readonly'], emits: ['update:schema'] },
  FormFieldPreview: { name: 'FormFieldPreview', template: '<div class="ffp-stub" />', props: ['schema'] },
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  const w = mount(NodeDetailPanel, { global: { plugins: [ElementPlus, pinia], stubs }, attachTo: document.body })
  return { w, store }
}

beforeEach(() => vi.useRealTimers())

describe('NodeDetailPanel', () => {
  it('shows empty hint when nothing selected', () => {
    const { w } = mountPanel()
    expect(w.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })

  it('body edit (debounced) calls updateBody', async () => {
    vi.useFakeTimers()
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', body: '<p>old</p>' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'updateBody').mockResolvedValue()
    await w.vm.$nextTick()
    w.findComponent({ name: 'RichTextEditor' }).vm.$emit('update:modelValue', '<p>new</p>')
    vi.advanceTimersByTime(600)
    expect(spy).toHaveBeenCalledWith('a', '<p>new</p>')
  })

  it('level select calls setLevel', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', heading_level: null })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'setLevel').mockResolvedValue()
    await w.vm.$nextTick()
    w.findComponent({ name: 'ElSelect' }).vm.$emit('change', 2)
    expect(spy).toHaveBeenCalledWith('a', 2)
  })

  it('kind switch calls setKind', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', kind: 'node' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'setKind').mockResolvedValue()
    await w.vm.$nextTick()
    w.find('.kind-switch').findComponent({ name: 'ElSwitch' }).vm.$emit('change', true)
    expect(spy).toHaveBeenCalledWith('a', 'step')
  })

  it('step node renders form + attachment editor; adding a mark calls updateForm', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', kind: 'step', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'updateForm').mockResolvedValue()
    await w.vm.$nextTick()
    expect(w.find('.sff-stub').exists()).toBe(true)
    await w.find('.add-mark').trigger('click')
    expect(spy).toHaveBeenCalledWith('a', { type: 'CHECK' }, [{ filename: '', kind: 'document', note: '' }])
  })

  it('review node shows confirm button → confirmReview', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', mark_status: 'review' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'confirmReview').mockResolvedValue()
    await w.vm.$nextTick()
    await w.find('.confirm-review').trigger('click')
    expect(spy).toHaveBeenCalledWith('a')
  })
})

describe('NodeDetailPanel — readonly', () => {
  function mountRO() {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useNodeEditorStore()
    const w = mount(NodeDetailPanel, {
      props: { readonly: true },
      global: { plugins: [ElementPlus, pinia], stubs },
      attachTo: document.body,
    })
    return { w, store }
  }

  it('hides level/kind/skip controls, review confirm, and attachment add when readonly', async () => {
    const { w, store } = mountRO()
    store.nodes = [n({ id: 'a', kind: 'step', mark_status: 'review', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    await w.vm.$nextTick()
    expect(w.find('.kind-switch').exists()).toBe(false)
    expect(w.find('.confirm-review').exists()).toBe(false)
    expect(w.find('.add-mark').exists()).toBe(false)
  })

  it('passes readonly to RichTextEditor and StepFormFields', async () => {
    const { w, store } = mountRO()
    store.nodes = [n({ id: 'a', kind: 'step', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    await w.vm.$nextTick()
    expect(w.findComponent({ name: 'RichTextEditor' }).props('readonly')).toBe(true)
    expect(w.findComponent({ name: 'StepFormFields' }).props('readonly')).toBe(true)
  })
})
