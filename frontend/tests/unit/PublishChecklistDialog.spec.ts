import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

let mountDiv: HTMLDivElement | null = null
let wrapper: ReturnType<typeof mount> | null = null

function setup(reviewCount: number) {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure
  store.procedure = { id: 'p1', version: 1, name: 'X', custom_values: {}, version_update_notes: '' }
  store.fields = []
  store.chapters = Array.from({ length: reviewCount + 1 }, (_, i) => ({
    id: `c${i}`, parent_id: null, content_type: 'chapter', title: 'c', rich_content: '',
    skip_numbering: false, mark_status: i < reviewCount ? 'review' : 'unmarked', sort_order: i,
  }))
  store.steps = []
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
})
