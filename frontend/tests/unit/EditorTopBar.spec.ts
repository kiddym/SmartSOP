import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

function seedEditable() {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure（editable 需 is_current + DRAFT）
  store.procedure = {
    id: 'p1', code: 'QC-001', name: '测试', version: 1, is_current: true,
    status: 'DRAFT', folder_full_path: '', revision: 1,
  }
}

describe('EditorTopBar · 撤销按钮 tooltip', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('title 标明范围限于大纲结构', () => {
    seedEditable()
    const w = mount(EditorTopBar, { global: { plugins: [ElementPlus] } })
    const undoBtn = w.findAll('button').find((b) => b.text() === '↶')
    expect(undoBtn).toBeTruthy()
    const title = undoBtn!.attributes('title') ?? ''
    expect(title).toContain('撤销')
    expect(title).toContain('Ctrl+Z')
    expect(title).toContain('大纲结构')
  })
})

describe('EditorTopBar · PDF 预览按钮', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('可编辑时渲染「PDF 预览」并点按 emit preview-pdf', async () => {
    seedEditable()
    const w = mount(EditorTopBar, { global: { plugins: [ElementPlus] } })
    const btn = w.findAll('button').find((b) => b.text().includes('PDF 预览'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(w.emitted('preview-pdf')).toBeTruthy()
  })
})
