import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import type { ProcedureMeta } from '@/types/procedure'

const { routeRef } = vi.hoisted(() => ({
  routeRef: { value: { params: { id: 'p1' }, query: {}, name: 'procedure-edit', path: '/procedures/p1/edit' } as Record<string, unknown> },
}))
vi.mock('vue-router', () => ({
  useRoute: () => routeRef.value,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  onBeforeRouteLeave: vi.fn(),
}))

import ProcedureEditorView from '@/views/procedures/ProcedureEditorView.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    folder_full_path: '根', version_change_log: [], has_source_docx: false,
    ...over,
  } as unknown as ProcedureMeta
}

const stubs = {
  EditorTopBar: { template: '<div class="topbar-stub" />' },
  EditorPreviewPane: { template: '<div class="preview-stub" />' },
  NodeTreePanel: { name: 'NodeTreePanel', template: '<div class="tree-stub" />', props: ['readonly'] },
  NodeDetailPanel: { name: 'NodeDetailPanel', template: '<div class="detail-stub" />', props: ['readonly'] },
  ProcedureDetailsPanel: { template: '<div class="meta-stub" />' },
  AttachmentPanel: { template: '<div class="attach-stub" />' },
  CollapsiblePanel: { template: '<div><slot /></div>' },
  PublishChecklistDialog: { template: '<div />' },
  VersionActionDialog: { template: '<div />' },
  PdfPreviewDialog: { template: '<div />' },
}

function mountView(editable = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const proc = useProcedureEditorStore()
  vi.spyOn(proc, 'load').mockImplementation(async () => {
    proc.procedure = meta(editable ? {} : { status: 'PUBLISHED', is_current: true })
  })
  const node = useNodeEditorStore()
  const nodeLoad = vi.spyOn(node, 'load').mockResolvedValue()
  const w = mount(ProcedureEditorView, { global: { plugins: [ElementPlus, pinia], stubs } })
  return { w, proc, node, nodeLoad }
}

beforeEach(() => {
  routeRef.value = { params: { id: 'p1' }, query: {}, name: 'procedure-edit', path: '/procedures/p1/edit' }
  vi.clearAllMocks()
})

describe('ProcedureEditorView — unified editor switch (B3b-1)', () => {
  it('renders NodeTreePanel + NodeDetailPanel (no node-mode gate) and loads nodeEditor', async () => {
    const { w, nodeLoad } = mountView(true)
    await flushPromises()
    expect(w.find('.tree-stub').exists()).toBe(true)
    expect(w.find('.detail-stub').exists()).toBe(true)
    expect(nodeLoad).toHaveBeenCalledWith('p1')
  })

  it('passes readonly=false to panels when editable (draft current)', async () => {
    const { w } = mountView(true)
    await flushPromises()
    expect(w.findComponent({ name: 'NodeTreePanel' }).props('readonly')).toBe(false)
    expect(w.findComponent({ name: 'NodeDetailPanel' }).props('readonly')).toBe(false)
  })

  it('passes readonly=true to panels on /view (not editable)', async () => {
    routeRef.value = { params: { id: 'p1' }, query: {}, name: 'procedure-view', path: '/procedures/p1/view' }
    const { w } = mountView(false)
    await flushPromises()
    expect(w.findComponent({ name: 'NodeTreePanel' }).props('readonly')).toBe(true)
    expect(w.findComponent({ name: 'NodeDetailPanel' }).props('readonly')).toBe(true)
  })

  it('loads nodeEditor BEFORE redirecting /edit→/view for a non-editable procedure', async () => {
    // 直达 /edit 但不可编辑 → 重定向 /view（组件复用，onMounted 不再触发）。
    // 结构须在重定向前加载，否则复用的 /view 实例树为空。
    routeRef.value = { params: { id: 'p1' }, query: {}, name: 'procedure-edit', path: '/procedures/p1/edit' }
    const { nodeLoad } = mountView(false)
    await flushPromises()
    expect(nodeLoad).toHaveBeenCalledWith('p1')
  })
})
