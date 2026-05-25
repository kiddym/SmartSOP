import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import EditorLayerMarking from '@/components/editor/EditorLayerMarking.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

const stubs = {
  ImportMarkingRow: {
    props: ['label', 'role', 'indent', 'disableContent'],
    emits: ['set'],
    template: '<div class="stub-mr" :data-role="role" :data-label="label" />',
  },
}

function setup() {
  const store = useProcedureEditorStore()
  store.chapters = [
    { id: 'a', parent_id: null, content_type: 'chapter', title: '甲', rich_content: '', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
    { id: 'b', parent_id: 'a', content_type: 'chapter', title: '乙', rich_content: '', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 },
  ]
  store.steps = []
  store.layerMode = true
  return mount(EditorLayerMarking, { global: { plugins: [ElementPlus], stubs } })
}

describe('EditorLayerMarking', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('渲染文档序的层级行并预填角色', () => {
    const w = setup()
    const rows = w.findAll('.stub-mr')
    expect(rows.map((r) => r.attributes('data-label'))).toEqual(['甲', '乙'])
    expect(rows[0].attributes('data-role')).toBe('chapter_1')
    expect(rows[1].attributes('data-role')).toBe('chapter_2')
  })

  it('点「应用层级」调 store.applyLayerRoles', async () => {
    const w = setup()
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'applyLayerRoles').mockImplementation(() => {})
    const btn = w.findAll('button').find((b) => b.text().includes('应用'))
    await btn!.trigger('click')
    expect(spy).toHaveBeenCalledOnce()
  })
})
