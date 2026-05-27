import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// 隔离 axios / element-plus 副作用：store 经 api 层间接依赖 http。
vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

const { markSpy, saveSpy, deleteChapterSpy, deleteStepSpy, moveChapterSpy, moveStepSpy } = vi.hoisted(() => ({
  markSpy: vi.fn(),
  saveSpy: vi.fn(),
  deleteChapterSpy: vi.fn(),
  deleteStepSpy: vi.fn(),
  moveChapterSpy: vi.fn(),
  moveStepSpy: vi.fn(),
}))
vi.mock('@/api/chapters', () => ({
  setChapterMarkStatus: markSpy,
  createChapter: vi.fn(),
  deleteChapter: deleteChapterSpy,
  moveChapter: moveChapterSpy,
  convertChapterToStep: vi.fn(),
  convertRootToStep: vi.fn(),
  convertChapterToContent: vi.fn(),
  splitChapterTitleContent: vi.fn(),
}))
vi.mock('@/api/steps', () => ({ deleteStep: deleteStepSpy, moveStep: moveStepSpy, convertStepToChapter: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: vi.fn(),
  saveProcedure: saveSpy,
  applyMarks: vi.fn(),
  applyLayerRolesApi: vi.fn(async () => ({ chapter_map: {}, revision: 4 })),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'
import { nextRowId } from '@/utils/reviewNav'
import type { ChapterTreeNode, EditorChapter, EditorStep, StepOut } from '@/types/node'
import type { ProcedureMeta } from '@/types/procedure'
import { convertChapterToContent as convertChapterToContentApi, splitChapterTitleContent as splitChapterTitleContentApi } from '@/api/chapters'
import { fetchProcedureDetail } from '@/api/procedures'

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

function chap(id: string, parentId: string | null, sort: number): EditorChapter {
  return {
    id,
    parent_id: parentId,
    title: id,
    skip_numbering: false,
    mark_status: 'unmarked',
    sort_order: sort,
  }
}

// 新签名 helper（题面新增用例使用）：(id, title, parentId, sort)。
function chapter(id: string, title: string, parentId: string | null, sort: number): EditorChapter {
  return {
    id,
    parent_id: parentId,
    title,
    skip_numbering: false,
    mark_status: 'unmarked',
    sort_order: sort,
  }
}

function stp(id: string, chapterId: string | null, sort: number): EditorStep {
  return {
    id,
    chapter_id: chapterId,
    kind: 'step',
    title: id,
    content: '',
    input_schema: { type: 'COMMON' },
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
  deleteChapterSpy.mockReset().mockResolvedValue({})
  deleteStepSpy.mockReset().mockResolvedValue({})
  moveChapterSpy.mockReset().mockResolvedValue({})
  moveStepSpy.mockReset().mockResolvedValue({})
})

describe('新增节点', () => {
  it('addChapterNode 建临时节点、置脏、选中', () => {
    const s = seed()
    const id = s.addChapterNode('a')
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

  it('addChapterNode 带 afterId：插到该兄弟之后并重排 sort_order', () => {
    const s = seed() // 根级已有 a(0), b(1)
    const id = s.addChapterNode(null, 'a') // 期望落在 a 与 b 之间
    const order = s.chapters
      .filter((c) => c.parent_id === null)
      .sort((x, y) => x.sort_order - y.sort_order)
      .map((c) => c.id)
    expect(order).toEqual(['a', id, 'b'])
  })

  it('addStepNode 带 afterId：在同章节内插到该步骤之后', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0), stp('s2', 'a', 1)]
    const id = s.addStepNode('a', 's1') // 期望落在 s1 与 s2 之间
    const order = s.steps
      .filter((st) => st.chapter_id === 'a')
      .sort((x, y) => x.sort_order - y.sort_order)
      .map((st) => st.id)
    expect(order).toEqual(['s1', id, 's2'])
  })

  it('addStepNode 可建 content kind 并置脏', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '操作', null, 0)]
    store.steps = []
    const id = store.addStepNode('c1', null, 'content')
    expect(store.stepMap.get(id)!.kind).toBe('content')
    expect(store.dirtySteps.has(id)).toBe(true)
  })
})

describe('setStepKind', () => {
  it('setStepKind 翻转 kind 并置脏', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.steps = [
      {
        id: 's1',
        chapter_id: 'c1',
        title: 'x',
        content: '',
        kind: 'step',
        input_schema: { type: 'COMMON' },
        attachment_marks: [],
        skip_numbering: false,
        sort_order: 0,
      },
    ]
    store.setStepKind('s1', 'content')
    expect(store.stepMap.get('s1')!.kind).toBe('content')
    expect(store.dirtySteps.has('s1')).toBe(true)
  })

  it('setStepKind step→content 保留 title（新定义：content 有可选 title）', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.steps = [
      {
        id: 's1',
        chapter_id: 'c1',
        title: '概述',
        content: '<p>正文</p>',
        kind: 'step',
        input_schema: { type: 'COMMON' },
        attachment_marks: [{ kind: 't', filename: 'a.pdf', note: '' }],
        skip_numbering: false,
        sort_order: 0,
      },
    ]
    store.setStepKind('s1', 'content')
    const s = store.stepMap.get('s1')!
    expect(s.kind).toBe('content')
    expect(s.title).toBe('概述') // 保留
    expect(s.attachment_marks).toEqual([]) // 结构化字段仍清空（不再是 step 的语义）
    expect(s.input_schema).toEqual({}) // 同上
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

  it('updateStepFields 等值空操作不置脏、不入撤销栈（杜绝富文本幽灵脏）', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)] // content 初始为 ''
    const undoBefore = s.undoStack.length
    s.updateStepFields('s1', { content: '' }, 'content:s1') // 编辑器挂载回发等值空内容
    expect(s.dirtySteps.has('s1')).toBe(false)
    expect(s.undoStack.length).toBe(undoBefore)
  })

  it('updateChapterFields 等值空操作不置脏', () => {
    const s = seed()
    const title = s.chapterMap.get('a')!.title
    s.updateChapterFields('a', { title })
    expect(s.dirtyChapters.has('a')).toBe(false)
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
    const id = s.addChapterNode('a')
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
  it('仅含脏节点；章节不再承载正文字段', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('b', null, 1)]
    s.updateChapterFields('a', { title: '改名' })
    const payload = s.buildPayload()
    expect(payload.chapters.map((c) => c.id)).toEqual(['a'])
    expect(payload.chapters[0]).not.toHaveProperty('content_type')
    expect(payload.chapters[0]).not.toHaveProperty('rich_content')
    expect(payload.steps).toEqual([])
    expect(payload.name).toBe('测试程序')
  })

  it('步骤 payload 含 kind（content 步骤）', () => {
    const s = seed()
    const id = s.addStepNode('a', null, 'content')
    const payload = s.buildPayload()
    const node = payload.steps.find((st) => st.id === id)
    expect(node?.kind).toBe('content')
  })

  it('includes signoff_enabled in payload', () => {
    // reuse the describe('buildPayload') setup that already loads a procedure before calling buildPayload
    const s = useProcedureEditorStore()
    s.procedure = meta()
    s.procedure!.signoff_enabled = true
    const payload = s.buildPayload()
    expect(payload.signoff_enabled).toBe(true)
  })
})

describe('applyIdMap', () => {
  it('临时 id 改名并修正父引用 / 选中 / 展开', () => {
    const s = seed()
    const cid = s.addChapterNode('a')
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

  it('flatRows 把 content 步骤渲染为 content 行、无号', () => {
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '操作', null, 0)]
    store.expanded = { c1: true }
    store.steps = [
      {
        id: 'k',
        chapter_id: 'c1',
        title: '',
        content: '<p>x</p>',
        kind: 'content',
        input_schema: {} as never,
        attachment_marks: [],
        skip_numbering: false,
        sort_order: 0,
      },
    ]
    const row = store.flatRows.find((r) => r.id === 'k')!
    expect(row.kind).toBe('content')
    expect(row.code).toBe('')
  })
})

describe('标记模式 temp-id 安全（评审 C1/C2）', () => {
  it('临时节点 setMark 只改本地、不发后端请求', async () => {
    const s = seed()
    const id = s.addChapterNode('a')
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
    const tmp = s.addChapterNode('a')
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
    s.addChapterNode('a') // 空标题
    expect(s.validateForSave().some((e) => e.includes('标题为空'))).toBe(true)
  })

  it('标题齐全则通过', () => {
    const s = seed()
    expect(s.validateForSave()).toEqual([])
  })
})

describe('setStepFormType 非破坏性切换', () => {
  it('切换类型保留 content，input_schema 只含 type', () => {
    const s = seed()
    const id = s.addStepNode('a')
    s.updateStepFields(id, { content: '<p>说明</p>' })
    s.setStepFormType(id, 'NUMBER')
    expect(s.stepMap.get(id)!.content).toBe('<p>说明</p>')
    expect(s.stepMap.get(id)!.input_schema).toEqual({ type: 'NUMBER' })
  })
})

describe('待确认 triage (P2b)', () => {
  it('acceptReview 清 review 并持久化', async () => {
    const s = seed()
    s.chapters = [{ ...chap('a', null, 0), mark_status: 'review' }]
    await s.acceptReview('a')
    expect(s.chapterMap.get('a')?.mark_status).toBe('unmarked')
    expect(markSpy).toHaveBeenCalledWith('a', 'unmarked')
  })

  it('acceptAllReviews 清全部 review', async () => {
    const s = seed()
    s.chapters = [
      { ...chap('a', null, 0), mark_status: 'review' },
      { ...chap('b', null, 1), mark_status: 'review' },
      { ...chap('c', null, 2), mark_status: 'unmarked' },
    ]
    await s.acceptAllReviews()
    expect(s.chapters.every((c) => c.mark_status === 'unmarked')).toBe(true)
    expect(markSpy).toHaveBeenCalledTimes(2)
  })

})

describe('层级标定 (P2c)', () => {
  it('toggleLayerMode 与 markMode 互斥', () => {
    const s = seed()
    s.toggleMarkMode()
    expect(s.markMode).toBe(true)
    s.toggleLayerMode()
    expect(s.layerMode).toBe(true)
    expect(s.markMode).toBe(false)
  })

  it('layerRows：文档序含章节、标 hasLeafChildren（步骤/内容块步骤都算）', () => {
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('b', 'a', 0)]
    s.steps = [stp('s1', 'a', 0)]
    const rows = s.layerRows
    // 新行为：章节 a、子章节 b、再是 a 下的叶子 s1（子章节先于叶子）
    expect(rows.map((r) => r.id)).toEqual(['a', 'b', 's1'])
    expect(rows.find((r) => r.id === 'a')?.hasLeafChildren).toBe(true)
    expect(rows.find((r) => r.id === 'b')?.hasLeafChildren).toBe(false)
    // 章节行无 content_type 字段。
    expect(rows[0]).not.toHaveProperty('content_type')
  })

  it('layerRows (overlay)：输出 chapter + step + content 按文档序', () => {
    const s = seed()
    s.chapters = [
      chap('A', null, 0),
      chap('B', 'A', 0),
    ]
    s.steps = [
      { id: 's1', chapter_id: 'B', kind: 'step', title: 's1', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'c1', chapter_id: 'B', kind: 'content', title: '', content: '<p>x</p>', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 1 },
    ]
    expect(s.layerRows.map((r) => r.id)).toEqual(['A', 'B', 's1', 'c1'])
    expect(s.layerRows.map((r) => r.kind)).toEqual(['chapter', 'chapter', 'step', 'content'])
    expect(s.layerRows[1].hasLeafChildren).toBe(true)
  })

  it('applyLayerRoles 无 Q25 冲突 → 调 applyLayerRolesApi 并 reload，退出模式', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    vi.mocked(applyLayerRolesApi).mockClear()
    const s = seed()
    s.chapters = [chap('a', null, 0), chap('b', 'a', 0)]
    s.layerMode = true
    vi.spyOn(s, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(s, 'reload').mockResolvedValue()
    const result = await s.applyLayerRoles(new Map([['a', 'chapter_1'], ['b', 'chapter_1']]))
    expect(result.ok).toBe(true)
    expect(applyLayerRolesApi).toHaveBeenCalledTimes(1)
    expect(applyLayerRolesApi).toHaveBeenCalledWith('p1', { roles: { a: 'chapter_1', b: 'chapter_1' } }, 3)
    expect(s.reload).toHaveBeenCalled()
    expect(s.layerMode).toBe(false)
  })

  it('applyLayerRoles review 章节：API 成功后 reload（清 review 由后端或 reload 处理）', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    vi.mocked(applyLayerRolesApi).mockClear()
    const s = seed()
    s.chapters = [{ ...chap('a', null, 0), mark_status: 'review' }, chap('b', 'a', 0)]
    s.layerMode = true
    vi.spyOn(s, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(s, 'reload').mockResolvedValue()
    const result = await s.applyLayerRoles(new Map([['a', 'chapter_1'], ['b', 'chapter_1']]))
    expect(result.ok).toBe(true)
    expect(s.reload).toHaveBeenCalled()
  })

  it('applyLayerRoles content 角色：无 Q25 → 调 applyLayerRolesApi 含 content 角色', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    vi.mocked(applyLayerRolesApi).mockClear()
    const s = seed()
    s.chapters = [chapter('a', '甲', null, 0), chapter('c', '正文文本', 'a', 0)]
    s.steps = []
    s.layerMode = true
    vi.spyOn(s, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(s, 'reload').mockResolvedValue()
    const result = await s.applyLayerRoles(new Map([['a', 'chapter_1'], ['c', 'content']]))
    expect(result.ok).toBe(true)
    expect(applyLayerRolesApi).toHaveBeenCalledWith('p1', { roles: { a: 'chapter_1', c: 'content' } }, 3)
  })

  it('applyLayerRoles content 多节点：多个 content 角色全部传入 API', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    vi.mocked(applyLayerRolesApi).mockClear()
    const s = seed()
    s.chapters = [chapter('a', '甲', null, 0), chapter('c', '<b>x & y</b>', 'a', 0), chapter('d', '   ', 'a', 1)]
    s.steps = []
    s.layerMode = true
    vi.spyOn(s, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(s, 'reload').mockResolvedValue()
    const result = await s.applyLayerRoles(new Map([['a', 'chapter_1'], ['c', 'content'], ['d', 'content']]))
    expect(result.ok).toBe(true)
    const call = vi.mocked(applyLayerRolesApi).mock.calls[0]
    expect(call[1]).toEqual({ roles: { a: 'chapter_1', c: 'content', d: 'content' } })
  })

  it('applyLayerRoles 后代重排：无 Q25 → 调 API 一次，roles 含全部节点', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    vi.mocked(applyLayerRolesApi).mockClear()
    const s = seed()
    s.chapters = [chapter('a', '甲', null, 0), chapter('b', '乙', 'a', 0), chapter('g', '丙', 'b', 0)]
    s.steps = []
    s.layerMode = true
    vi.spyOn(s, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(s, 'reload').mockResolvedValue()
    const result = await s.applyLayerRoles(new Map([['a', 'chapter_1'], ['b', 'content'], ['g', 'chapter_1']]))
    expect(result.ok).toBe(true)
    expect(applyLayerRolesApi).toHaveBeenCalledTimes(1)
    const call = vi.mocked(applyLayerRolesApi).mock.calls[0]
    expect(call[1].roles).toMatchObject({ a: 'chapter_1', b: 'content', g: 'chapter_1' })
  })
})

describe('缺标题 + 展开祖先', () => {
  it('missingTitleCount 统计所有标题为空的章节（步骤不计入）', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    s.procedure = meta()
    const empty = chap('e', null, 0)
    empty.title = '   ' // 纯空白
    s.chapters = [chap('a', null, 1), empty]
    s.steps = [{ ...stp('s', 'a', 0), title: '' }] // 空标题步骤不计入
    expect(s.missingTitleCount).toBe(1)
  })

  it('expandAncestors 展开目标的全部祖先', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    s.procedure = meta()
    s.chapters = [chap('g', null, 0), chap('p', 'g', 0), chap('c', 'p', 0)]
    s.expanded = {}
    s.expandAncestors('c')
    expect(s.expanded.p).toBe(true)
    expect(s.expanded.g).toBe(true)
    expect(s.expanded.c ?? false).toBe(false) // 只展开祖先，不含自身
  })

  it('chapterDocRows 按文档序、与折叠无关（折叠分支里的缺标题章节仍可命中）', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    s.procedure = meta()
    const child = chap('c', 'g', 0)
    child.title = '' // 折叠父级下的缺标题子章节
    s.chapters = [chap('g', null, 0), child]
    s.expanded = {} // g 折叠 → flatRows 里没有 c
    expect(s.flatRows.map((r) => r.id)).toEqual(['g']) // 折叠：c 不在 flatRows
    expect(s.chapterDocRows.map((r) => r.id)).toEqual(['g', 'c']) // 但 chapterDocRows 含 c
    expect(nextRowId(s.chapterDocRows, null, (r) => r.kind === 'chapter' && !r.title.trim())).toBe('c')
  })
})

describe('移除树层级 / 内容块旧 action 不再存在', () => {
  it('promoteChapter/demoteChapter/canPromoteChapter/canDemoteChapter 不再存在', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore() as unknown as Record<string, unknown>
    expect(s.promoteChapter).toBeUndefined()
    expect(s.demoteChapter).toBeUndefined()
    expect(s.canPromoteChapter).toBeUndefined()
    expect(s.canDemoteChapter).toBeUndefined()
  })
  it('toggleContentType/promoteContentToChapter/contentToSteps 已删除', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore() as unknown as Record<string, unknown>
    expect(s.toggleContentType).toBeUndefined()
    expect(s.promoteContentToChapter).toBeUndefined()
    expect(s.contentToSteps).toBeUndefined()
  })
})

describe('snapshot / restore 包含删除集合', () => {
  it('snapshot 拷贝 deletedChapterIds / deletedStepIds；restore 恢复', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const snap = s.snapshot()
    s.deletedChapterIds = new Set()
    s.deletedStepIds = new Set()
    s.restore(snap)
    expect([...s.deletedChapterIds].sort()).toEqual(['x', 'y'])
    expect([...s.deletedStepIds]).toEqual(['s'])
  })

  it('resetEditState 清空删除集合', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x'])
    s.deletedStepIds = new Set(['s'])
    s.resetEditState()
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.deletedStepIds.size).toBe(0)
  })
})

describe('isDirty 含待删除', () => {
  it('deletedChapterIds 非空时 isDirty 为 true', () => {
    const s = seed()
    expect(s.isDirty).toBe(false)
    s.deletedChapterIds = new Set(['x'])
    expect(s.isDirty).toBe(true)
  })

  it('deletedStepIds 非空时 isDirty 为 true', () => {
    const s = seed()
    s.deletedStepIds = new Set(['s'])
    expect(s.isDirty).toBe(true)
  })
})

describe('exportDraft / importDraft 含删除集合', () => {
  it('exportDraft 导出 deletedChapterIds / deletedStepIds', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const draft = s.exportDraft()
    expect([...draft.deletedChapterIds].sort()).toEqual(['x', 'y'])
    expect(draft.deletedStepIds).toEqual(['s'])
  })

  it('importDraft 还原 deletedChapterIds / deletedStepIds', () => {
    seed()
    const s2 = useProcedureEditorStore()
    s2.importDraft({
      procedure: meta(),
      chapters: [chap('a', null, 0)],
      steps: [],
      selectedId: null,
      expanded: {},
      dirtyChapters: [],
      dirtySteps: [],
      deletedChapterIds: ['x'],
      deletedStepIds: ['s'],
      metaDirty: false,
    })
    expect([...s2.deletedChapterIds]).toEqual(['x'])
    expect([...s2.deletedStepIds]).toEqual(['s'])
    // importDraft 历来清 undo 栈：保持原有契约
    expect(s2.undoStack).toEqual([])
    expect(s2.redoStack).toEqual([])
  })
})

describe('deleteNode 本地化（Tier 1）', () => {
  it('删除已存章节：记录 id 到 deletedChapterIds，不发请求', async () => {
    const s = seed()
    await s.deleteNode('a')
    expect([...s.deletedChapterIds]).toEqual(['a'])
    expect(deleteChapterSpy).not.toHaveBeenCalled()
    expect(s.chapterMap.has('a')).toBe(false)
  })

  it('删除已存章节可撤销：undo 还原章节和删除集合', async () => {
    const s = seed()
    await s.deleteNode('a')
    s.undo()
    expect(s.chapterMap.has('a')).toBe(true)
    expect(s.deletedChapterIds.size).toBe(0)
  })

  it('删除临时章节：不进入 deletedChapterIds（后端无此节点）', async () => {
    const s = seed()
    const tmp = s.addChapterNode('a')
    await s.deleteNode(tmp)
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.chapterMap.has(tmp)).toBe(false)
    expect(deleteChapterSpy).not.toHaveBeenCalled()
  })

  it('删除子树：所有已存后代章节 + 已存子步骤都进入对应删除集合，临时子节点忽略', async () => {
    const s = seed()
    // 已存父 a；已存子 a1；a1 下临时孙；a 下已存步骤 stepX；a1 下已存步骤 stepT_real；a1 下临时步骤
    s.chapters = [chap('a', null, 0), chap('a1', 'a', 0)]
    const tmpGrandchild = s.addChapterNode('a1')   // 临时
    s.steps = [stp('stepX', 'a', 0), stp('stepT_real', 'a1', 0)]
    const tmpStep = s.addStepNode('a1')             // 临时
    await s.deleteNode('a')
    expect([...s.deletedChapterIds].sort()).toEqual(['a', 'a1'])
    expect([...s.deletedStepIds].sort()).toEqual(['stepT_real', 'stepX'])
    // 临时节点不进入删除集合
    expect(s.deletedChapterIds.has(tmpGrandchild)).toBe(false)
    expect(s.deletedStepIds.has(tmpStep)).toBe(false)
    // 本地完全移除
    expect(s.chapterMap.has('a')).toBe(false)
    expect(s.chapterMap.has('a1')).toBe(false)
    expect(s.stepMap.has('stepX')).toBe(false)
  })

  it('删除已存步骤：记录 id 到 deletedStepIds，不发请求', async () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)]
    await s.deleteNode('s1')
    expect([...s.deletedStepIds]).toEqual(['s1'])
    expect(deleteStepSpy).not.toHaveBeenCalled()
    expect(s.stepMap.has('s1')).toBe(false)
  })
})

describe('moveCrossParent 本地化（Tier 1）', () => {
  it('章节跨父：parent_id 与两侧 sort_order 重排，置脏，不发请求', async () => {
    const s = seed()
    // 两个根：a（含 a1, a2）、b（含 b1）
    s.chapters = [
      chap('a', null, 0),
      chap('b', null, 1),
      chap('a1', 'a', 0),
      chap('a2', 'a', 1),
      chap('b1', 'b', 0),
    ]
    // 把 a1 移到 b 下，索引 0（变成 b 的首子）
    await s.moveCrossParent('a1', 'b', 0)
    expect(moveChapterSpy).not.toHaveBeenCalled()
    expect(s.chapterMap.get('a1')!.parent_id).toBe('b')
    // 新父组 (b 下) 应为 [a1, b1]，sort_order 0..1
    const bGroup = s.chapters.filter((c) => c.parent_id === 'b').sort((x, y) => x.sort_order - y.sort_order)
    expect(bGroup.map((c) => c.id)).toEqual(['a1', 'b1'])
    expect(bGroup.map((c) => c.sort_order)).toEqual([0, 1])
    // 原父组 (a 下) 应只剩 a2，sort_order 重排为 0
    const aGroup = s.chapters.filter((c) => c.parent_id === 'a').sort((x, y) => x.sort_order - y.sort_order)
    expect(aGroup.map((c) => c.id)).toEqual(['a2'])
    expect(aGroup.map((c) => c.sort_order)).toEqual([0])
    // 三个被触碰的章节都进入 dirty
    expect(s.dirtyChapters.has('a1')).toBe(true)
    expect(s.dirtyChapters.has('a2')).toBe(true)
    expect(s.dirtyChapters.has('b1')).toBe(true)
  })

  it('章节跨父可撤销', async () => {
    const s = seed()
    s.chapters = [
      chap('a', null, 0),
      chap('b', null, 1),
      chap('a1', 'a', 0),
    ]
    await s.moveCrossParent('a1', 'b', 0)
    s.undo()
    expect(s.chapterMap.get('a1')!.parent_id).toBe('a')
    expect(s.chapterMap.get('a1')!.sort_order).toBe(0)
  })

  it('步骤跨父：chapter_id 与两侧 sort_order 重排，置脏，不发请求', async () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0), stp('s2', 'a', 1), stp('s3', 'b', 0)]
    await s.moveCrossParent('s1', 'b', 1)
    expect(moveStepSpy).not.toHaveBeenCalled()
    expect(s.stepMap.get('s1')!.chapter_id).toBe('b')
    const bSteps = s.steps.filter((x) => x.chapter_id === 'b').sort((x, y) => x.sort_order - y.sort_order)
    expect(bSteps.map((x) => x.id)).toEqual(['s3', 's1'])
    expect(bSteps.map((x) => x.sort_order)).toEqual([0, 1])
    const aSteps = s.steps.filter((x) => x.chapter_id === 'a').sort((x, y) => x.sort_order - y.sort_order)
    expect(aSteps.map((x) => x.id)).toEqual(['s2'])
    expect(aSteps.map((x) => x.sort_order)).toEqual([0])
    expect(s.dirtySteps.has('s1')).toBe(true)
    expect(s.dirtySteps.has('s2')).toBe(true)
    expect(s.dirtySteps.has('s3')).toBe(true)
  })
})

describe('buildPayload + save 链路含删除集合', () => {
  it('buildPayload 输出 deleted_chapter_ids / deleted_step_ids', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const payload = s.buildPayload()
    expect([...payload.deleted_chapter_ids].sort()).toEqual(['x', 'y'])
    expect(payload.deleted_step_ids).toEqual(['s'])
  })

  it('save 成功后删除集合清空', async () => {
    const s = seed()
    // 触发 isDirty 让 save 真正发起：先标一笔 dirty
    s.updateChapterFields('a', { title: '改名' })
    s.deletedChapterIds = new Set(['x'])
    s.deletedStepIds = new Set(['s'])
    saveSpy.mockResolvedValue({ ...meta(), revision: 4, id_map: {} })
    await s.save()
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.deletedStepIds.size).toBe(0)
    // 同时 payload 在 save 调用时确实带了删除 id
    const calledPayload = saveSpy.mock.calls[0][1]
    expect(calledPayload.deleted_chapter_ids).toEqual(['x'])
    expect(calledPayload.deleted_step_ids).toEqual(['s'])
  })
})

describe('procedureEditorStore.convertChapterToContent', () => {
  function detailResponse(overrides: Partial<{ chapters: ChapterTreeNode[]; steps: StepOut[] }> = {}) {
    return {
      procedure: meta(),
      chapters: overrides.chapters ?? [],
      steps: overrides.steps ?? [],
      attachments: [],
      fields: [],
      has_source_docx: false,
    }
  }

  it('calls API and selects new step', async () => {
    vi.mocked(convertChapterToContentApi).mockResolvedValue({ created: ['new-step-id'], deleted: ['ch-1'] })
    vi.mocked(fetchProcedureDetail).mockResolvedValue(detailResponse())

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []
    const refreshSpy = vi.spyOn(store, 'refreshAfterConversion')

    await store.convertChapterToContent('ch-1')

    expect(vi.mocked(convertChapterToContentApi)).toHaveBeenCalledWith('ch-1')
    expect(refreshSpy).toHaveBeenCalled()
    expect(store.selectedId).toBe('new-step-id')
  })

  it('records undo on success', async () => {
    vi.mocked(convertChapterToContentApi).mockResolvedValue({ created: ['new-id'], deleted: ['ch-1'] })
    vi.mocked(fetchProcedureDetail).mockResolvedValue(detailResponse())

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []
    const before = store.undoStack.length

    await store.convertChapterToContent('ch-1')

    expect(store.undoStack.length).toBe(before + 1)
  })

  it('does not mutate state on API failure', async () => {
    vi.mocked(convertChapterToContentApi).mockRejectedValue(new Error('500 error'))

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []
    const before = store.undoStack.length

    await expect(store.convertChapterToContent('ch-1')).rejects.toThrow()

    expect(store.undoStack.length).toBe(before)
    expect(store.chapters.find((c) => c.id === 'ch-1')).toBeDefined()
  })
})

describe('procedureEditorStore.splitChapterTitleContent', () => {
  beforeEach(() => {
    vi.mocked(splitChapterTitleContentApi).mockReset()
  })

  function detailResponse(overrides: Partial<{ chapters: ChapterTreeNode[]; steps: StepOut[] }> = {}) {
    return {
      procedure: meta(),
      chapters: overrides.chapters ?? [],
      steps: overrides.steps ?? [],
      attachments: [],
      fields: [],
      has_source_docx: false,
    }
  }

  it('calls API with cursor_offset and selects new step', async () => {
    vi.mocked(splitChapterTitleContentApi).mockResolvedValue({ created: ['new-step-id'], deleted: [] })
    vi.mocked(fetchProcedureDetail).mockResolvedValue(detailResponse())

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []

    await store.splitChapterTitleContent('ch-1', 15)

    expect(vi.mocked(splitChapterTitleContentApi)).toHaveBeenCalledWith('ch-1', { cursor_offset: 15 })
    expect(store.selectedId).toBe('new-step-id')
  })

  it('blocks duplicate calls via inflight lock', async () => {
    let resolveCall: (v: unknown) => void = () => {}
    const pending = new Promise((r) => { resolveCall = r })
    vi.mocked(splitChapterTitleContentApi).mockReturnValue(pending as never)
    vi.mocked(fetchProcedureDetail).mockResolvedValue(detailResponse())

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []

    const p1 = store.splitChapterTitleContent('ch-1', 4)
    const p2 = store.splitChapterTitleContent('ch-1', 4)  // 双击
    resolveCall({ created: ['new-id'], deleted: [] })
    await Promise.all([p1, p2])

    expect(vi.mocked(splitChapterTitleContentApi)).toHaveBeenCalledTimes(1)
  })

  it('records undo on success', async () => {
    vi.mocked(splitChapterTitleContentApi).mockResolvedValue({ created: ['new-id'], deleted: [] })
    vi.mocked(fetchProcedureDetail).mockResolvedValue(detailResponse())

    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chap('ch-1', null, 0)]
    store.steps = []
    const before = store.undoStack.length

    await store.splitChapterTitleContent('ch-1', 4)
    expect(store.undoStack.length).toBe(before + 1)
  })
})
