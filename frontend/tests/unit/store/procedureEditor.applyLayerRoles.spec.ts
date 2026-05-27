import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

vi.mock('@/api/procedures', async () => {
  const actual = await vi.importActual<typeof import('@/api/procedures')>('@/api/procedures')
  return {
    ...actual,
    applyLayerRolesApi: vi.fn(async () => ({ chapter_map: {}, revision: 2 })),
  }
})

import { useProcedureEditorStore } from '@/store/procedureEditor'

const baseProc = { id: 'p1', revision: 1, lock_version: 1 } as any

describe('store.applyLayerRoles (overlay)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('Q25 末态冲突 → 返回 conflicts,不调 API', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [
      { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 } as never,
    ]
    // A 有两个子叶子 s1(step) 和 c1(content)。
    // roleMap: A→chapter_1, c1→chapter_2。
    // walk: A(reorder@null), s1(leaf-reparent@A), c1(to-chapter@A, L2)。
    // A 下: c1(chapter) + s1(leaf) → Q25 冲突。
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'step', title: 's1', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 } as never,
      { id: 'c1', chapter_id: 'A', kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 1 } as never,
    ]
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['c1', 'chapter_2']]))
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflicts.length).toBeGreaterThan(0)
      expect(result.conflicts[0].parent_id).toBe('A')
    }
    expect(applyLayerRolesApi).not.toHaveBeenCalled()
  })

  it('happy path → 调 applyLayerRolesApi 一次并 reload', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [
      { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 } as never,
    ]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'content', title: 'X', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 } as never,
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(
      new Map<string, import('@/utils/layerMark').LayerRole>([['A', 'chapter_1'], ['s1', 'chapter_2']]),
    )
    expect(result.ok).toBe(true)
    expect(applyLayerRolesApi).toHaveBeenCalledTimes(1)
    expect(applyLayerRolesApi).toHaveBeenCalledWith('p1', { roles: { A: 'chapter_1', s1: 'chapter_2' } }, 1)
    expect(store.reload).toHaveBeenCalled()
    expect(store.layerMode).toBe(false)
  })

  it('后端 400 SIBLING_TYPE_CONFLICT → 解构 detail 并返回 conflicts', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          detail: {
            code: 'SIBLING_TYPE_CONFLICT',
            message: 'x',
            conflicts: [{ parent_id: 'A', chapter_children: ['s1'], leaf_children: ['k'] }],
          },
        },
      },
    })
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [
      { id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 } as never,
    ]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'content', title: 'X', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 } as never,
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(
      new Map<string, import('@/utils/layerMark').LayerRole>([['A', 'chapter_1'], ['s1', 'chapter_2']]),
    )
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflicts[0].parent_id).toBe('A')
      expect(result.conflicts[0].chapterChildren).toEqual(['s1'])
      expect(result.conflicts[0].leafChildren).toEqual(['k'])
    }
  })
})
