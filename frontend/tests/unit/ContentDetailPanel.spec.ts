import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ContentDetailPanel from '@/components/editor/ContentDetailPanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import type { ProcedureMeta } from '@/types/procedure'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock('@/api/chapters', () => ({ setChapterMarkStatus: vi.fn().mockResolvedValue({}) }))

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

describe('ContentDetailPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('绑定内容块步骤的富文本、无 review 横幅', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.steps = [
      {
        id: 'k',
        chapter_id: 'c1',
        kind: 'content',
        title: '',
        content: '<p>hi</p>',
        input_schema: {} as never,
        attachment_marks: [],
        skip_numbering: false,
        sort_order: 0,
      },
    ]
    store.selectNode('k')

    const w = mount(ContentDetailPanel, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          RichTextEditor: {
            props: ['modelValue'],
            template: '<div class="rte">{{ modelValue }}</div>',
          },
        },
      },
    })

    expect(w.find('.rte').exists()).toBe(true)
    expect(w.find('.rte').text()).toContain('hi')
    expect(w.text()).not.toContain('接受待确认')
  })

  it('无选中步骤时不渲染内容区', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.steps = []
    store.selectNode(null)

    const w = mount(ContentDetailPanel, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          RichTextEditor: {
            props: ['modelValue'],
            template: '<div class="rte">{{ modelValue }}</div>',
          },
        },
      },
    })

    expect(w.find('.content-detail').exists()).toBe(false)
    expect(w.find('.rte').exists()).toBe(false)
  })
})
