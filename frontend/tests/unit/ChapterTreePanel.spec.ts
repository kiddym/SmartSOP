import { describe, expect, it } from 'vitest'
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
    content_type: 'chapter',
    title,
    rich_content: '',
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
})
