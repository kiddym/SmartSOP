import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ChapterTreePanel from '@/components/editor/ChapterTreePanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import type { EditorChapter } from '@/types/node'
import type { ProcedureMeta } from '@/types/procedure'

function meta(): ProcedureMeta {
  return {
    id: 'p1',
    procedure_group_id: 'g1',
    code: 'QC-001',
    name: '测试程序',
    version: 1,
    is_current: true,
    status: 'DRAFT',
    folder_id: 'f1',
    folder_full_path: '根/叶',
    description: '',
    risk_level: 1,
    quality_level: 1,
    level_of_use: 'continuous',
    custom_values: {},
    version_update_notes: '',
    signoff_enabled: false,
    revision: 3,
    is_read: false,
    read_at: null,
    deprecated_from_folder_id: null,
    deprecated_at: null,
    archived_at: null,
    version_change_log: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function chapter(id: string, title: string, parentId: string | null, sortOrder: number): EditorChapter {
  return {
    id,
    parent_id: parentId,
    title,
    skip_numbering: false,
    mark_status: 'unmarked',
    sort_order: sortOrder,
  }
}

describe('ChapterTreePanel', () => {
  it('renders rows from the editor store', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '总则', null, 0), chapter('c2', '适用范围', 'c1', 0)]
    store.expanded = { c1: true }

    const wrapper = mount(ChapterTreePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })

    expect(store.flatRows.map((row) => row.title)).toEqual(['总则', '适用范围'])
    expect(wrapper.text()).toContain('总则')
    expect(wrapper.text()).toContain('适用范围')
  })

  it('does not fall back to rendering the full large tree when the virtual window is empty', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = Array.from({ length: 51 }, (_, i) => chapter(`c${i}`, `章节 ${i}`, null, i))

    const wrapper = mount(ChapterTreePanel, {
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })

    expect(store.flatRows).toHaveLength(51)
    expect(wrapper.findAllComponents({ name: 'TreeRow' }).length).toBeLessThan(51)
  })

  it('章节行＋新增=加子节点；步骤行＋新增=同父级加同级', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    const addChapterSpy = vi.spyOn(store, 'addChapterNode').mockReturnValue('tmp')
    const addStepSpy = vi.spyOn(store, 'addStepNode').mockReturnValue('tmp')

    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = wrapper.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    const stepRow = rows.find((r) => r.props('row').id === 's1')!

    chapterRow.vm.$emit('add', 'step')
    expect(addStepSpy).toHaveBeenCalledWith('c1', null, 'step') // 章节 → 加子节点

    stepRow.vm.$emit('add', 'step')
    expect(addStepSpy).toHaveBeenCalledWith('c1', 's1', 'step') // 步骤 → 同父级、该行之后
    expect(addChapterSpy).not.toHaveBeenCalled()
  })

  it('onAdd content 调用 addStepNode(..., content)', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    const addStepSpy = vi.spyOn(store, 'addStepNode').mockReturnValue('tmp')

    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = wrapper.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!

    chapterRow.vm.$emit('add', 'content')
    expect(addStepSpy).toHaveBeenCalledWith('c1', null, 'content')
  })

  it('@convert to-step 调用 store.setStepKind(id, step)', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'content', title: '', content: '', input_schema: {}, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = wrapper.findAllComponents({ name: 'TreeRow' })
    const contentRow = rows.find((r) => r.props('row').id === 's1')!

    contentRow.vm.$emit('convert', 'to-step')
    expect(setStepKindSpy).toHaveBeenCalledWith('s1', 'step')
  })

  it('@convert to-content 调用 store.setStepKind(id, content)', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = wrapper.findAllComponents({ name: 'TreeRow' })
    const stepRow = rows.find((r) => r.props('row').id === 's1')!

    stepRow.vm.$emit('convert', 'to-content')
    expect(setStepKindSpy).toHaveBeenCalledWith('s1', 'content')
  })

  it('存在缺标题章节时显示定位条与计数', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '', null, 0), chapter('c2', '有题', null, 1)]
    store.expanded = {}
    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    expect(wrapper.find('.missing-bar').exists()).toBe(true)
    expect(wrapper.find('.missing-bar').text()).toContain('1')
  })
})
