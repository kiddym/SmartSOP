import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportTreePanel from '@/components/import-v2/ImportTreePanel.vue'
import { useImportDialog } from '@/composables/useImportDialog'

describe('ImportTreePanel 工具栏', () => {
  it('Row① 始终显示两个模式按钮 + 重置', () => {
    const ctx = useImportDialog()
    const w = mount(ImportTreePanel, { props: { ctx } })
    expect(w.text()).toContain('层级标定')
    expect(w.text()).toContain('步骤标注')
    expect(w.text()).toContain('重置')
  })

  it('normal 模式无选中：Row② 显示「根级」+ 添加按钮', () => {
    const ctx = useImportDialog()
    const w = mount(ImportTreePanel, { props: { ctx } })
    expect(w.text()).toContain('根级')
    expect(w.text()).toContain('+章节')
  })

  it('layer-marking 模式：Row② 显示「完成」，不再有批量/忽略按钮', () => {
    const ctx = useImportDialog()
    ctx.toggleLayerMarking()
    const w = mount(ImportTreePanel, { props: { ctx } })
    expect(w.text()).toContain('完成')
    expect(w.text()).not.toContain('→一级')
    expect(w.text()).not.toContain('→忽略')
  })

  it('layer-marking 模式：加载树后每段渲染级别选择器', () => {
    const ctx = useImportDialog()
    ctx.loadParseResult({
      metadata: { total_chapters: 1, image_count: 0, table_count: 0, body_start_index: 0,
        body_start_detected_by: '', format: 'docx', parse_time_ms: 0 },
      chapters: [{
        id: 'a', title: '目的', level: 1, order: 0, parent_id: null, content_type: 'chapter',
        rich_content: '', skip_numbering: false, confidence: 1, confidence_tier: 'high',
        mark_status: 'unmarked', heading_source: null, children: [],
      }],
      import_blocks: [], assets: [], detected_patterns: [], validation: null,
      warnings: [], review_required: 0, parse_method: 'smart',
    })
    ctx.toggleLayerMarking()
    const w = mount(ImportTreePanel, { props: { ctx } })
    const t = w.text()
    expect(t).toContain('一级')
    expect(t).toContain('正文')
    expect(t).toContain('目的')
  })

  it('step-annotation 模式：Row② 显示步骤标注按钮', async () => {
    const ctx = useImportDialog()
    ctx.toggleStepAnnotation()
    const w = mount(ImportTreePanel, { props: { ctx } })
    expect(w.text()).toContain('→ 步骤')
    expect(w.text()).toContain('→ 内容')
    expect(w.text()).toContain('清除标注')
  })

  it('点击层级标定按钮后再点步骤标注按钮：自动退出前者进入后者', async () => {
    const ctx = useImportDialog()
    const w = mount(ImportTreePanel, { props: { ctx } })
    // 第一行有层级标定和步骤标注按钮
    expect(w.text()).toContain('层级标定')
    expect(w.text()).toContain('步骤标注')
    ctx.toggleLayerMarking()
    expect(ctx.mode.value).toBe('layer-marking')
    ctx.toggleStepAnnotation()
    expect(ctx.mode.value).toBe('step-annotation')
  })
})
