import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { MarkStatus } from '@/types/node'

let mountDiv: HTMLDivElement | null = null
let wrapper: ReturnType<typeof mount> | null = null

function setup(reviewCount: number, nodeCount = reviewCount + 1) {
  const store = useProcedureEditorStore()
  const nodeStore = useNodeEditorStore()
  // @ts-expect-error 最小 procedure
  store.procedure = { id: 'p1', version: 1, name: 'X', custom_values: {}, version_update_notes: '' }
  store.fields = []
  // B3b-2：结构来自 nodeEditor
  nodeStore.nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: `n${i}`,
    procedure_id: 'p1',
    parent_id: null,
    sort_order: i,
    heading_level: null,
    kind: 'node' as const,
    body: 'body',
    code: '',
    depth: 0,
    skip_numbering: false,
    mark_status: (i < reviewCount ? 'review' : 'unmarked') as MarkStatus,
    revision: 1,
    input_schema: {} as Record<string, never>,
    attachment_marks: [],
  }))
  mountDiv = document.createElement('div')
  document.body.appendChild(mountDiv)
  wrapper = mount(PublishChecklistDialog, {
    props: { modelValue: true },
    global: { plugins: [ElementPlus] },
    attachTo: mountDiv,
  })
  return wrapper
}

describe('PublishChecklistDialog 待确认拦截', () => {
  beforeEach(() => setActivePinia(createPinia()))

  afterEach(() => {
    wrapper?.unmount()
    mountDiv?.remove()
    wrapper = null
    mountDiv = null
  })

  it('有待确认 → 列出未通过项且确认按钮禁用', async () => {
    setup(2)
    await nextTick()
    await flushPromises()
    expect(document.body.textContent).toContain('无待确认')
    const confirm = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('确认发布'),
    )
    expect(confirm?.disabled).toBe(true)
  })

  it('无待确认 → 该项通过', async () => {
    setup(0)
    await nextTick()
    await flushPromises()
    const li = Array.from(document.body.querySelectorAll('li')).find((n) =>
      n.textContent?.includes('无待确认'),
    )
    expect(li?.classList.contains('fail')).toBe(false)
  })

  it('无节点 → "至少包含 1 个节点"项失败且确认按钮禁用', async () => {
    setup(0, 0)
    await nextTick()
    await flushPromises()
    const li = Array.from(document.body.querySelectorAll('li')).find((n) =>
      n.textContent?.includes('至少包含 1 个节点'),
    )
    expect(li?.classList.contains('fail')).toBe(true)
    const confirm = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('确认发布'),
    )
    expect(confirm?.disabled).toBe(true)
  })

  it('所有检查通过 → 确认按钮可用', async () => {
    setup(0, 1)
    await nextTick()
    await flushPromises()
    const confirm = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('确认发布'),
    )
    expect(confirm?.disabled).toBe(false)
  })
})
