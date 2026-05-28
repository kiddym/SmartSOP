import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { ProcedureMeta } from '@/types/procedure'

// 控制 nodeEditor 真实 action 的网络往返，以驱动 $onAction（autosave 指示）。
const { batchSpy } = vi.hoisted(() => ({ batchSpy: vi.fn() }))
vi.mock('@/api/nodes', () => ({
  batchUpdateNodes: batchSpy,
  listNodes: vi.fn(),
  patchNode: vi.fn(),
  createNode: vi.fn(),
  deleteNode: vi.fn(),
  reorderNodes: vi.fn(),
}))

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: '示例', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    folder_full_path: '根', version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

function setup(over: Partial<ProcedureMeta> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const proc = useProcedureEditorStore()
  proc.procedure = meta(over)
  const node = useNodeEditorStore()
  const w = mount(EditorTopBar, { global: { plugins: [ElementPlus, pinia] }, attachTo: document.body })
  return { w, proc, node }
}

beforeEach(() => vi.restoreAllMocks())

describe('EditorTopBar (B3b-1)', () => {
  it('renders code + name', () => {
    const { w } = setup()
    expect(w.text()).toContain('C-1')
    expect(w.text()).toContain('示例')
  })

  it('has NO save button', () => {
    const { w } = setup()
    expect(w.findAll('button').some((b) => b.text().includes('保存'))).toBe(false)
  })

  it('undo disabled until canUndo, then calls nodeEditor.undo', async () => {
    const { w, node } = setup()
    const undo = vi.spyOn(node, 'undo').mockResolvedValue()
    const btn = w.find('.etb-undo')
    expect(btn.attributes('disabled')).toBeDefined()
    node.undoStack = [async () => {}]
    await w.vm.$nextTick()
    expect(w.find('.etb-undo').attributes('disabled')).toBeUndefined()
    await w.find('.etb-undo').trigger('click')
    expect(undo).toHaveBeenCalled()
  })

  it('shows autosave indicator that flips while a mutating action is in-flight', async () => {
    const { w, node } = setup()
    node.procedureId = 'p1' // 让真实 setLevel 不早退
    let release!: (v: unknown) => void
    batchSpy.mockReturnValue(new Promise((res) => { release = res }))
    expect(w.find('.etb-save').text()).toContain('已保存')
    void node.setLevel('x', 1) // 真实 action（非 mock），$onAction 触发
    await w.vm.$nextTick()
    expect(w.find('.etb-save').text()).toContain('保存中')
    release([]) // resolve：setLevel 用空 list 收尾
    await flushPromises()
    expect(w.find('.etb-save').text()).toContain('已保存')
  })

  it('emits lifecycle events (publish/preview-pdf/copy)', async () => {
    const { w } = setup()
    await w.findAll('button').find((b) => b.text() === '发布')!.trigger('click')
    await w.findAll('button').find((b) => b.text() === 'PDF 预览')!.trigger('click')
    expect(w.emitted('publish')).toBeTruthy()
    expect(w.emitted('preview-pdf')).toBeTruthy()
  })
})
