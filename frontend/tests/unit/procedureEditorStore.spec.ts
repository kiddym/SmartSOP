import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// 隔离 axios / element-plus 副作用：store 经 api 层间接依赖 http。
vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

const { markSpy, saveSpy } = vi.hoisted(() => ({ markSpy: vi.fn(), saveSpy: vi.fn() }))
vi.mock('@/api/chapters', () => ({
  setChapterMarkStatus: markSpy,
  createChapter: vi.fn(),
  deleteChapter: vi.fn(),
  moveChapter: vi.fn(),
  convertChapterToStep: vi.fn(),
  convertRootToStep: vi.fn(),
  contentToSteps: vi.fn(),
  batchContentToSteps: vi.fn(),
}))
vi.mock('@/api/steps', () => ({ deleteStep: vi.fn(), moveStep: vi.fn(), convertStepToChapter: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: vi.fn(),
  saveProcedure: saveSpy,
  applyMarks: vi.fn(),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'
import type { EditorChapter, EditorStep } from '@/types/node'
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

function chap(id: string, parentId: string | null, sort: number): EditorChapter {
  return {
    id,
    parent_id: parentId,
    content_type: 'chapter',
    title: id,
    rich_content: '',
    skip_numbering: false,
    mark_status: 'unmarked',
    sort_order: sort,
  }
}

function stp(id: string, chapterId: string | null, sort: number): EditorStep {
  return {
    id,
    chapter_id: chapterId,
    title: id,
    content: '',
    input_schema: { type: 'COMMON' },
    note: '',
    caution: '',
    warning: '',
    note_schema: { type: 'COMMON' },
    caution_schema: { type: 'COMMON' },
    warning_schema: { type: 'COMMON' },
    expected_output: '',
    require_confirmation: false,
    attachment_marks: [],
    skip_numbering: false,
    sort_order: sort,
  }
}

type Store = ReturnType<typeof useProcedureEditorStore>

function seed(): Store {
  const store = useProcedureEditorStore()
  store.procedure = meta()
  store.chapters = [chap('a', null, 0), chap('b', null, 1)]
  store.steps = []
  store.expanded = { a: true, b: true }
  return store
}

beforeEach(() => {
  setActivePinia(createPinia())
  markSpy.mockReset().mockResolvedValue({})
  saveSpy.mockReset()
})

describe('新增节点', () => {
  it('addChapterNode 建临时节点、置脏、选中', () => {
    const s = seed()
    const id = s.addChapterNode('a', 'chapter')
    expect(id.startsWith('temp-')).toBe(true)
    expect(s.dirtyChapters.has(id)).toBe(true)
    expect(s.selectedId).toBe(id)
    expect(s.isDirty).toBe(true)
  })

  it('addStepNode 在 chapter 下追加 step', () => {
    const s = seed()
    const id = s.addStepNode('a')
    expect(s.dirtySteps.has(id)).toBe(true)
    expect(s.stepMap.get(id)?.chapter_id).toBe('a')
  })
})

describe('编辑与脏追踪', () => {
  it('updateStepFields 置脏', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)]
    s.updateStepFields('s1', { title: '新标题' })
    expect(s.stepMap.get('s1')?.title).toBe('新标题')
    expect(s.dirtySteps.has('s1')).toBe(true)
  })

  it('toggleSkipNumbering 翻转并置脏', () => {
    const s = seed()
    s.toggleSkipNumbering('a')
    expect(s.chapterMap.get('a')?.skip_numbering).toBe(true)
    expect(s.dirtyChapters.has('a')).toBe(true)
  })
})

describe('上下移 reorder', () => {
  it('交换同级 sort_order', () => {
    const s = seed()
    expect(s.chapterMap.get('a')?.sort_order).toBe(0)
    s.reorder('a', 'down')
    expect(s.chapterMap.get('a')?.sort_order).toBe(1)
    expect(s.chapterMap.get('b')?.sort_order).toBe(0)
    expect(s.dirtyChapters.has('a')).toBe(true)
    expect(s.dirtyChapters.has('b')).toBe(true)
  })

  it('首节点上移无操作', () => {
    const s = seed()
    s.reorder('a', 'up')
    expect(s.chapterMap.get('a')?.sort_order).toBe(0)
    expect(s.isDirty).toBe(false)
  })
})

describe('undo / redo', () => {
  it('undo 还原新增，redo 复原', () => {
    const s = seed()
    const id = s.addChapterNode('a', 'chapter')
    expect(s.chapterMap.has(id)).toBe(true)
    s.undo()
    expect(s.chapterMap.has(id)).toBe(false)
    s.redo()
    expect(s.chapterMap.has(id)).toBe(true)
  })

  it('同 tag 连续编辑合并为一步撤销', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)]
    s.updateStepFields('s1', { title: 'A' }, 'edit:s1:title')
    s.updateStepFields('s1', { title: 'AB' }, 'edit:s1:title')
    s.updateStepFields('s1', { title: 'ABC' }, 'edit:s1:title')
    s.undo()
    expect(s.stepMap.get('s1')?.title).toBe('s1') // 回到首次编辑前
  })
})

describe('buildPayload', () => {
  it('仅含脏节点；chapter 的 rich_content 强制空', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('b', null, 1)]
    // 给 a 写非法 rich_content（章节不该承载），buildPayload 须清空
    s.updateChapterFields('a', { rich_content: '<p>x</p>' })
    const payload = s.buildPayload()
    expect(payload.chapters.map((c) => c.id)).toEqual(['a'])
    expect(payload.chapters[0].rich_content).toBe('')
    expect(payload.steps).toEqual([])
    expect(payload.name).toBe('测试程序')
  })

  it('content 节点保留 rich_content', () => {
    const s = seed()
    const id = s.addChapterNode('a', 'content')
    s.updateChapterFields(id, { rich_content: '<p>正文</p>' }, 'x')
    const payload = s.buildPayload()
    const node = payload.chapters.find((c) => c.id === id)
    expect(node?.content_type).toBe('content')
    expect(node?.rich_content).toBe('<p>正文</p>')
  })
})

describe('applyIdMap', () => {
  it('临时 id 改名并修正父引用 / 选中 / 展开', () => {
    const s = seed()
    const cid = s.addChapterNode('a', 'chapter')
    const sid = s.addStepNode(cid)
    s.selectedId = sid
    s.applyIdMap({ [cid]: 'real-c', [sid]: 'real-s' })
    expect(s.chapterMap.has('real-c')).toBe(true)
    expect(s.stepMap.get('real-s')?.chapter_id).toBe('real-c')
    expect(s.selectedId).toBe('real-s')
    expect(s.expanded['real-c']).toBe(true)
  })
})

describe('flatRows 与 Q25', () => {
  it('折叠父节点隐藏子节点', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('a1', 'a', 0)]
    s.expanded = { a: true }
    expect(s.flatRows.map((r) => r.id)).toEqual(['a', 'a1'])
    s.setExpanded('a', false)
    expect(s.flatRows.map((r) => r.id)).toEqual(['a'])
  })

  it('addButtonStateFor 反映互斥', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)]
    const st = s.addButtonStateFor('a')
    expect(st.canAddStep).toBe(true)
    expect(st.canAddChapter).toBe(false)
  })

  it('L1 章节 code 显示 .0', () => {
    const s = seed()
    const row = s.flatRows.find((r) => r.id === 'a')
    expect(row?.code).toBe('1.0')
  })
})

describe('标记模式 temp-id 安全（评审 C1/C2）', () => {
  it('临时节点 setMark 只改本地、不发后端请求', async () => {
    const s = seed()
    const id = s.addChapterNode('a', 'content')
    await s.setMark(id, 'step')
    expect(s.chapterMap.get(id)?.mark_status).toBe('step')
    expect(markSpy).not.toHaveBeenCalled()
  })

  it('已存节点 setMark 调用后端', async () => {
    const s = seed()
    await s.setMark('a', 'step')
    expect(markSpy).toHaveBeenCalledWith('a', 'step')
    expect(s.chapterMap.get('a')?.mark_status).toBe('step')
  })

  it('cycleMark 先保存把临时 id 解析为真实 id 再写后端', async () => {
    const s = seed()
    const tmp = s.addChapterNode('a', 'content')
    saveSpy.mockResolvedValue({ ...meta(), revision: 4, id_map: { [tmp]: 'real-x' } })
    await s.cycleMark(tmp)
    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(markSpy).toHaveBeenCalledWith('real-x', 'step')
    expect(s.chapterMap.get('real-x')?.mark_status).toBe('step')
  })
})

describe('validateForSave（评审 H2 / §8.2）', () => {
  it('空标题章节被拦截', () => {
    const s = seed()
    s.addChapterNode('a', 'chapter') // 空标题
    expect(s.validateForSave().some((e) => e.includes('标题为空'))).toBe(true)
  })

  it('标题齐全则通过', () => {
    const s = seed()
    expect(s.validateForSave()).toEqual([])
  })
})

describe('toggleContentType', () => {
  it('switches chapter → content and marks dirty', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [chap('c1', null, 0)]
      state.steps = []
    })
    expect(store.chapterMap.get('c1')!.content_type).toBe('chapter')

    store.toggleContentType('c1')

    expect(store.chapterMap.get('c1')!.content_type).toBe('content')
    expect(store.dirtyChapters.has('c1')).toBe(true)
  })

  it('switches content → chapter', () => {
    const store = useProcedureEditorStore()
    const c: EditorChapter = { ...chap('c1', null, 0), content_type: 'content' }
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [c]
      state.steps = []
    })

    store.toggleContentType('c1')

    expect(store.chapterMap.get('c1')!.content_type).toBe('chapter')
  })

  it('ignores unknown id', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = []
      state.steps = []
    })
    expect(() => store.toggleContentType('nonexistent')).not.toThrow()
  })
})

describe('canPromoteChapter', () => {
  it('returns false for root chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [chap('c1', null, 0)]
      state.steps = []
    })
    expect(store.canPromoteChapter('c1')).toBe(false)
  })

  it('returns true for nested chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [chap('c1', null, 0), chap('c2', 'c1', 0)]
      state.steps = []
    })
    expect(store.canPromoteChapter('c2')).toBe(true)
  })
})

describe('canDemoteChapter', () => {
  it('returns false when no previous sibling', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [chap('c1', null, 0)]
      state.steps = []
    })
    expect(store.canDemoteChapter('c1')).toBe(false)
  })

  it('returns true when previous sibling is chapter', () => {
    const store = useProcedureEditorStore()
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [chap('c1', null, 0), chap('c2', null, 1)]
      state.steps = []
    })
    expect(store.canDemoteChapter('c2')).toBe(true)
  })

  it('returns false when previous sibling is content', () => {
    const store = useProcedureEditorStore()
    const contentNode: EditorChapter = { ...chap('c1', null, 0), content_type: 'content' }
    store.$patch((state) => {
      state.procedure = meta()
      state.chapters = [contentNode, chap('c2', null, 1)]
      state.steps = []
    })
    expect(store.canDemoteChapter('c2')).toBe(false)
  })
})

describe('内容提升为章节', () => {
  it('promoteContentToChapter 把内容节点变章节并保留正文为子内容', () => {
    const s = seed()
    s.chapters = [
      {
        id: 'c1',
        parent_id: null,
        content_type: 'content',
        title: '',
        rich_content: '<p>系统启动条件</p><p>正文</p>',
        skip_numbering: true,
        mark_status: 'unmarked',
        sort_order: 0,
      },
    ]

    s.promoteContentToChapter('c1')

    const promoted = s.chapterMap.get('c1')
    expect(promoted?.content_type).toBe('chapter')
    expect(promoted?.title).toBe('系统启动条件 正文')
    expect(promoted?.rich_content).toBe('')
    expect(promoted?.skip_numbering).toBe(false)

    const child = s.chapters.find((c) => c.parent_id === 'c1')
    expect(child?.content_type).toBe('content')
    expect(child?.rich_content).toBe('<p>系统启动条件</p><p>正文</p>')
    expect(s.dirtyChapters.has('c1')).toBe(true)
    expect(child && s.dirtyChapters.has(child.id)).toBe(true)
  })

  it('promoteContentToChapter 忽略已有子节点的内容节点', () => {
    const s = seed()
    s.chapters = [
      {
        id: 'c1',
        parent_id: null,
        content_type: 'content',
        title: '',
        rich_content: '<p>正文</p>',
        skip_numbering: true,
        mark_status: 'unmarked',
        sort_order: 0,
      },
      chap('child', 'c1', 0),
    ]

    s.promoteContentToChapter('c1')

    expect(s.chapterMap.get('c1')?.content_type).toBe('content')
  })
})
