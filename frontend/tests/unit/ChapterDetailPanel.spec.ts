import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))
vi.mock('@/api/chapters', () => ({
  setChapterMarkStatus: vi.fn().mockResolvedValue({}),
  splitChapterTitleContent: vi.fn(),
}))

import ChapterDetailPanel from '@/components/editor/ChapterDetailPanel.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import type { EditorChapter } from '@/types/node'

function mountWith(markStatus: 'review' | 'unmarked') {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure
  store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
  store.chapters = [{
    id: 'a', parent_id: null, title: '章',
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

describe('ChapterDetailPanel 空标题自动聚焦', () => {
  beforeEach(() => setActivePinia(createPinia()))

  function seedSelected(title: string) {
    const store = useProcedureEditorStore()
    // @ts-expect-error 最小 procedure
    store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
    store.chapters = [{
      id: 'a', parent_id: null, title,
      skip_numbering: false, mark_status: 'unmarked', sort_order: 0,
    }]
    store.steps = []
    store.selectedId = 'a'
  }

  it('选中标题为空的章节时，标题输入框自动获得焦点', async () => {
    seedSelected('')
    const wrapper = mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 0))
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
    expect(document.activeElement).toBe(textarea.element)
    wrapper.unmount() // 卸载，避免跨用例 activeElement 污染
  })

  it('标题非空时不抢焦点', async () => {
    seedSelected('已有标题')
    const wrapper = mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 0))
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
    expect(document.activeElement).not.toBe(textarea.element)
    wrapper.unmount()
  })
})

describe('ChapterDetailPanel split button', () => {
  beforeEach(() => setActivePinia(createPinia()))

  function mountPanel(title: string) {
    const store = useProcedureEditorStore()
    // @ts-expect-error 最小 procedure
    store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
    store.chapters = [{ id: 'ch-1', title, parent_id: null, skip_numbering: false, mark_status: 'unmarked', sort_order: 0 } as EditorChapter]
    store.steps = []
    store.selectedId = 'ch-1'
    return mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
  }

  it('disables split button when cursor is null', async () => {
    const w = mountPanel('章节标题ABCDE')
    const btn = w.find('[data-test="split-title-content-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('enables split button when cursor is in middle', async () => {
    const w = mountPanel('章节标题ABCDE')
    const textarea = w.find('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(4, 4)
    await w.find('textarea').trigger('click')
    const btn = w.find('[data-test="split-title-content-btn"]')
    expect(btn.attributes('disabled')).toBeUndefined()
    w.unmount()
  })

  it('disables split button when cursor at 0 or at end', async () => {
    const w = mountPanel('章节标题')
    const textarea = w.find('textarea').element as HTMLTextAreaElement

    textarea.setSelectionRange(0, 0)
    await w.find('textarea').trigger('click')
    expect(w.find('[data-test="split-title-content-btn"]').attributes('disabled')).toBeDefined()

    textarea.setSelectionRange(4, 4)  // 末尾 (4 chars)
    await w.find('textarea').trigger('click')
    expect(w.find('[data-test="split-title-content-btn"]').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('calls store.splitChapterTitleContent on click', async () => {
    const w = mountPanel('章节标题ABCDE')
    const store = useProcedureEditorStore()
    const spy = vi.spyOn(store, 'splitChapterTitleContent').mockResolvedValue()

    const textarea = w.find('textarea').element as HTMLTextAreaElement
    textarea.setSelectionRange(4, 4)
    await w.find('textarea').trigger('click')
    await w.find('[data-test="split-title-content-btn"]').trigger('click')

    expect(spy).toHaveBeenCalledWith('ch-1', 4)
    w.unmount()
  })
})
