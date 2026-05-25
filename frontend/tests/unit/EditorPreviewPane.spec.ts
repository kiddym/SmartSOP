import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/procedures', () => ({
  fetchSourceDocx: vi.fn(),
}))
import { fetchSourceDocx } from '@/api/procedures'
import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'

const stubs = {
  WordPreviewPanel: { template: '<div class="stub-preview" />' },
  ImportSideRail: {
    props: ['label', 'side'],
    emits: ['expand'],
    template: '<div class="stub-rail" @click="$emit(\'expand\')">{{ label }}</div>',
  },
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(fetchSourceDocx).mockReset()
})

describe('EditorPreviewPane', () => {
  it('无原文（null）时不渲染预览列', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue(null)
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    expect(w.find('.preview-col').exists()).toBe(false)
    expect(w.find('.stub-preview').exists()).toBe(false)
  })

  it('有原文时渲染预览面板', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue({ blob: new Blob(['x']), filename: 'a.docx' })
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    expect(w.find('.preview-col').exists()).toBe(true)
    expect(w.find('.stub-preview').exists()).toBe(true)
  })

  it('点折叠按钮 → 显示竖条；点竖条 → 还原', async () => {
    vi.mocked(fetchSourceDocx).mockResolvedValue({ blob: new Blob(['x']), filename: 'a.docx' })
    const w = mount(EditorPreviewPane, { props: { procedureId: 'p1' }, global: { stubs } })
    await flushPromises()
    await w.get('.collapse-btn').trigger('click')
    expect(w.find('.stub-rail').exists()).toBe(true)
    expect(w.find('.stub-preview').exists()).toBe(false)
    await w.get('.stub-rail').trigger('click')
    expect(w.find('.stub-preview').exists()).toBe(true)
  })
})
