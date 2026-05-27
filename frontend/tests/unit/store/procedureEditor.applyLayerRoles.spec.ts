import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

vi.mock('@/api/steps', async () => {
  const actual = await vi.importActual<typeof import('@/api/steps')>('@/api/steps')
  return {
    ...actual,
    convertStepToChapter: vi.fn(async () => ({ created: [], deleted: [] })),
  }
})

import { useProcedureEditorStore } from '@/store/procedureEditor'

describe('store.applyLayerRoles (overlay)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('Q25 冲突 → 返回 conflicts，不修改状态、不调 API', async () => {
    const { convertStepToChapter } = await import('@/api/steps')
    ;(convertStepToChapter as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'c1', chapter_id: 'A', kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's2', chapter_id: 'A', kind: 'step', title: 's2', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    const chBefore = JSON.parse(JSON.stringify(store.chapters))
    const stBefore = JSON.parse(JSON.stringify(store.steps))
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['c1', 'chapter_2']]))
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflicts.length).toBeGreaterThan(0)
      expect(result.conflicts[0].parent_id).toBe('A')
    }
    expect(store.chapters).toEqual(chBefore)
    expect(store.steps).toEqual(stBefore)
    expect(convertStepToChapter).not.toHaveBeenCalled()
  })

  it('叶子 chapter_X 选项无冲突 → 调 convertStepToChapter 并 reload', async () => {
    const { convertStepToChapter } = await import('@/api/steps')
    ;(convertStepToChapter as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(new Map<string, import('@/utils/layerMark').LayerRole>([['A', 'chapter_1'], ['s1', 'chapter_2']]))
    expect(result.ok).toBe(true)
    expect(convertStepToChapter).toHaveBeenCalledWith('s1')
    expect(store.reload).toHaveBeenCalled()
  })
})
