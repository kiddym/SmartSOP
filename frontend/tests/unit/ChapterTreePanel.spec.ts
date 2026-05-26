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
      { id: 's1', chapter_id: 'c1', kind: 'content', title: '', content: '', input_schema: { type: 'NONE' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
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

describe('ChapterTreePanel · 结构工具行（标记模式 + 层级标定）', () => {
  it('渲染两枚互斥按钮：标记模式 + 层级标定', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '总则', null, 0)]
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    const tools = w.find('.structure-tools')
    expect(tools.exists()).toBe(true)
    expect(tools.text()).toContain('标记模式')
    expect(tools.text()).toContain('层级标定')
  })

  it('点击「标记模式」进入 markMode；再点「层级标定」自动退出 markMode 进入 layerMode', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '总则', null, 0)]
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    const tools = w.find('.structure-tools')
    const markBtn = tools.findAll('button').find((b) => b.text().includes('标记模式'))!
    const layerBtn = tools.findAll('button').find((b) => b.text().includes('层级标定'))!
    await markBtn.trigger('click')
    expect(store.markMode).toBe(true)
    expect(store.layerMode).toBe(false)
    await layerBtn.trigger('click')
    expect(store.markMode).toBe(false)
    expect(store.layerMode).toBe(true)
  })
})

describe('ChapterTreePanel · 标记模式级联', () => {
  it('部分子节点入选时，章节 checkbox 为 indeterminate', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 's2', chapter_id: 'c1', kind: 'step', title: '步二', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's3', chapter_id: 'c1', kind: 'step', title: '步三', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const stepRow = rows.find((r) => r.props('row').id === 's1')!

    // 勾选 1/3 子节点
    stepRow.vm.$emit('check', false)
    await w.vm.$nextTick()

    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    expect(chapterRow.props('indeterminate')).toBe(true)
  })

  it('章节 checkbox 未选 → 点击级联选 root + 全部后代', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0), chapter('c1a', '子章', 'c1', 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true, c1a: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!

    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    // root c1 + 子章 c1a + 步 s1 全入选
    expect(chapterRow.props('selectedForMark')).toBe(true)
    const subRow = rows.find((r) => r.props('row').id === 'c1a')!
    const stepRow = rows.find((r) => r.props('row').id === 's1')!
    expect(subRow.props('selectedForMark')).toBe(true)
    expect(stepRow.props('selectedForMark')).toBe(true)
  })

  it('章节 checkbox 已全选 → 点击级联取消 root + 全部后代', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!

    // 先级联选中
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    // 再点击 → 全部取消
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()

    expect(chapterRow.props('selectedForMark')).toBe(false)
    const stepRow = rows.find((r) => r.props('row').id === 's1')!
    expect(stepRow.props('selectedForMark')).toBe(false)
  })

  it('章节 indeterminate → 点击 = 级联选所有剩余', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 's2', chapter_id: 'c1', kind: 'step', title: '二', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 1 },
      { id: 's3', chapter_id: 'c1', kind: 'step', title: '三', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 2 },
    ]
    store.expanded = { c1: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    const s1 = rows.find((r) => r.props('row').id === 's1')!
    s1.vm.$emit('check', false)
    await w.vm.$nextTick()
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    expect(chapterRow.props('indeterminate')).toBe(true)

    // 点 indeterminate 章节 → 选所有剩余
    chapterRow.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(chapterRow.props('selectedForMark')).toBe(true)
    expect(chapterRow.props('indeterminate')).toBe(false)
    for (const sid of ['s1', 's2', 's3']) {
      expect(rows.find((r) => r.props('row').id === sid)!.props('selectedForMark')).toBe(true)
    }
  })

  it('applyBatch(content) 混合选择：chapter→setMark / step→setStepKind / content 跳过', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0), chapter('c2', '章二', null, 1)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
      { id: 'ct1', chapter_id: 'c2', kind: 'content', title: '', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true, c2: true }
    store.markMode = true
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    const setMarkSpy = vi.spyOn(store, 'setMark').mockResolvedValue()
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    // 手动构造混合选择（避免依赖 cascade 的展开/折叠细节）
    rows.find((r) => r.props('row').id === 'c1')!.vm.$emit('check', false)  // c1 cascade → c1+s1
    rows.find((r) => r.props('row').id === 'ct1')!.vm.$emit('check', false) // ct1 单选
    await w.vm.$nextTick()

    // 触发"标记为内容"
    const markBar = w.find('.mark-bar')
    const contentBtn = markBar.findAll('button').find((b) => b.text().includes('标记为内容'))!
    await contentBtn.trigger('click')
    await w.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0)) // 让 await ensureSaved 的 microtask 结算

    // c1 → setMark(c1, 'content')；ct1（已是 content）跳过；s1 → setStepKind(s1, 'content')
    expect(setMarkSpy).toHaveBeenCalledWith('c1', 'content')
    expect(setStepKindSpy).toHaveBeenCalledWith('s1', 'content')
    expect(setStepKindSpy).not.toHaveBeenCalledWith('ct1', expect.anything())
  })

  it('applyBatch(step) 对已是 step 的行跳过', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', kind: 'step', title: '步', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    store.markMode = true
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    const setStepKindSpy = vi.spyOn(store, 'setStepKind')

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })
    rows.find((r) => r.props('row').id === 's1')!.vm.$emit('check', false)
    await w.vm.$nextTick()

    const markBar = w.find('.mark-bar')
    const stepBtn = markBar.findAll('button').find((b) => b.text().includes('标记为步骤'))!
    await stepBtn.trigger('click')
    await w.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(setStepKindSpy).not.toHaveBeenCalled()
  })

  it('章节 + shift → 走 range 而非级联（不选第二个章节的后代）', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0), chapter('c2', '章二', null, 1)]
    store.steps = [
      { id: 's2a', chapter_id: 'c2', kind: 'step', title: 'a', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true, c2: true }
    store.markMode = true

    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = w.findAllComponents({ name: 'TreeRow' })

    // 单击 c1 建立锚点（非 shift → 级联，但 c1 没有后代，所以只选自身）
    rows.find((r) => r.props('row').id === 'c1')!.vm.$emit('check', false)
    await w.vm.$nextTick()

    // shift 点 c2 → 走 buildSelection 的 range 路径（同父 null），不级联到 c2 的后代 s2a
    rows.find((r) => r.props('row').id === 'c2')!.vm.$emit('check', true)
    await w.vm.$nextTick()

    expect(rows.find((r) => r.props('row').id === 'c1')!.props('selectedForMark')).toBe(true)
    expect(rows.find((r) => r.props('row').id === 'c2')!.props('selectedForMark')).toBe(true)
    // 关键断言：c2 的 step 后代不在选择中（否则就是 cascade 行为了）
    expect(rows.find((r) => r.props('row').id === 's2a')!.props('selectedForMark')).toBe(false)
  })
})
