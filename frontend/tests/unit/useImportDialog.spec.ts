import { describe, expect, it } from 'vitest'
import { useImportDialog } from '@/composables/useImportDialog'
import type { ParseResponse, ParsedNode } from '@/types/parse'

function pnode(partial: Partial<ParsedNode> & { id: string }): ParsedNode {
  return {
    id: partial.id, title: partial.title ?? '', level: partial.level ?? 1,
    order: partial.order ?? 0, parent_id: partial.parent_id ?? null,
    content_type: partial.content_type ?? 'chapter', rich_content: partial.rich_content ?? '',
    skip_numbering: partial.skip_numbering ?? false, confidence: 1, confidence_tier: 'high',
    mark_status: partial.mark_status ?? 'unmarked', heading_source: null,
    children: partial.children ?? [],
  }
}

function mkParse(chapters: ParsedNode[]): ParseResponse {
  return {
    metadata: { total_chapters: chapters.length, image_count: 0, table_count: 0,
      body_start_index: 0, body_start_detected_by: '', format: 'docx', parse_time_ms: 0 },
    chapters, import_blocks: [], assets: [], detected_patterns: [], validation: null,
    warnings: [], review_required: 0, parse_method: 'smart',
  }
}

describe('useImportDialog 状态机', () => {
  it('初始状态：normal 模式、无选中、空树', () => {
    const d = useImportDialog()
    expect(d.mode.value).toBe('normal')
    expect(d.selectedId.value).toBeNull()
    expect(d.tree.value).toEqual([])
    expect(d.ignored.value).toEqual([])
    expect(d.markSelection.value.size).toBe(0)
  })

  it('toggleLayerMarking 在 normal/layer-marking 间切换', () => {
    const d = useImportDialog()
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('layer-marking')
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('normal')
  })

  it('toggleStepAnnotation 与 layer-marking 互斥', () => {
    const d = useImportDialog()
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('layer-marking')
    d.toggleStepAnnotation()
    expect(d.mode.value).toBe('step-annotation')
    d.toggleStepAnnotation()
    expect(d.mode.value).toBe('normal')
  })

  it('退出标记模式清空 markSelection', () => {
    const d = useImportDialog()
    d.toggleLayerMarking()
    d.toggleMarkSelection('x')
    expect(d.markSelection.value.size).toBe(1)
    d.toggleLayerMarking()
    expect(d.markSelection.value.size).toBe(0)
  })
})

describe('useImportDialog 装载与编辑', () => {
  it('loadParseResult 构建树并默认填充 form.name', () => {
    const d = useImportDialog()
    d.filename.value = 'doc.docx'
    d.loadParseResult(mkParse([pnode({ id: 'a', title: '总则' })]))
    expect(d.tree.value).toHaveLength(1)
    expect(d.form.name).toBe('doc')
  })

  it('selectNode / moveSelected / deleteSelected', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([
      pnode({ id: 'a', title: 'A' }),
      pnode({ id: 'b', title: 'B' }),
    ]))
    d.selectNode('a')
    expect(d.selectedId.value).toBe('a')
    d.moveSelected(1)
    expect(d.tree.value[0].id).toBe('b')
    d.deleteSelected()
    expect(d.tree.value).toHaveLength(1)
    expect(d.selectedId.value).toBeNull()
  })

  it('applyLayerMarking 把 markSelection 内节点设为目标层级', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([
      pnode({ id: 'a', children: [pnode({ id: 'a1' })] }),
    ]))
    d.toggleLayerMarking()
    d.toggleMarkSelection('a1')
    d.applyLayerMarking('chapter_1')
    // a1 提升到根
    expect(d.tree.value.map((n) => n.id)).toEqual(['a', 'a1'])
    expect(d.mode.value).toBe('normal') // 应用后退出模式
  })

  it('applyLayerMarking →正文 把节点类型改 content', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' })]))
    d.toggleLayerMarking()
    d.toggleMarkSelection('a')
    d.applyLayerMarking('content')
    expect(d.tree.value[0].content_type).toBe('content')
  })

  it('applyLayerMarking →忽略 把节点移到 ignored', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([
      pnode({ id: 'a' }), pnode({ id: 'b' }),
    ]))
    d.toggleLayerMarking()
    d.toggleMarkSelection('a')
    d.applyLayerMarking('ignored')
    expect(d.tree.value.map((n) => n.id)).toEqual(['b'])
    expect(d.ignored.value.map((n) => n.id)).toEqual(['a'])
  })

  it('applyStepAnnotation 设置 mark_status 为 step', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' }), pnode({ id: 'b' })]))
    d.toggleStepAnnotation()
    d.toggleMarkSelection('a')
    d.toggleMarkSelection('b')
    d.applyStepAnnotation('step')
    expect(d.tree.value[0].mark_status).toBe('step')
    expect(d.tree.value[1].mark_status).toBe('step')
    expect(d.mode.value).toBe('normal')
  })

  it('restoreIgnored 把单个忽略项恢复到根末尾', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' })]))
    d.toggleLayerMarking()
    d.toggleMarkSelection('a')
    d.applyLayerMarking('ignored')
    d.restoreIgnored('a')
    expect(d.tree.value.map((n) => n.id)).toEqual(['a'])
    expect(d.ignored.value).toHaveLength(0)
  })
})
