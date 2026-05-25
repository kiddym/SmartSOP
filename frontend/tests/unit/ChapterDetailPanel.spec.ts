import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock('@/api/chapters', () => ({ setChapterMarkStatus: vi.fn().mockResolvedValue({}) }))

import ChapterDetailPanel from '@/components/editor/ChapterDetailPanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

function mountWith(markStatus: 'review' | 'unmarked') {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure
  store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
  store.chapters = [{
    id: 'a', parent_id: null, content_type: 'chapter', title: '章', rich_content: '',
    skip_numbering: false, mark_status: markStatus, sort_order: 0,
  }]
  store.steps = []
  store.selectedId = 'a'
  return mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] } })
}

describe('ChapterDetailPanel 接受待确认', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('review 节点显示「接受待确认」并点按调 store.acceptReview', async () => {
    const w = mountWith('review')
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'acceptReview').mockResolvedValue()
    const btn = w.findAll('button').find((b) => b.text().includes('接受待确认'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(spy).toHaveBeenCalledWith('a')
  })

  it('非 review 节点不显示该按钮', () => {
    const w = mountWith('unmarked')
    expect(w.findAll('button').some((b) => b.text().includes('接受待确认'))).toBe(false)
  })
})
