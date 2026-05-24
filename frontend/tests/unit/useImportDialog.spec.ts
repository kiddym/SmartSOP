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
    // 直接预置一个忽略项（标定模式不再提供忽略入口）
    d.ignored.value = [{
      id: 'z', title: 'Z', content_type: 'chapter', rich_content: '',
      skip_numbering: false, mark_status: 'unmarked', confidence_tier: 'high', children: [],
    }]
    d.restoreIgnored('z')
    expect(d.tree.value.map((n) => n.id)).toEqual(['a', 'z'])
    expect(d.ignored.value).toHaveLength(0)
  })

  it('层级标定：setRole 改级别，离开模式时统一生效', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' }), pnode({ id: 'b' })]))
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('layer-marking')
    expect(d.roleMap.value.get('b')).toBe('chapter_1') // 预填默认
    d.setRole('b', 'chapter_2')
    d.toggleLayerMarking() // 离开 → 生效
    expect(d.mode.value).toBe('normal')
    expect(d.levelMap.value.get('b')).toBe(2)
    expect(d.tree.value.find((n) => n.id === 'a')?.children.map((n) => n.id)).toEqual(['b'])
  })

  it('层级标定：切到步骤标注也会生效改动', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' })]))
    d.toggleLayerMarking()
    d.setRole('a', 'content')
    d.toggleStepAnnotation() // 切走 → 应已生效
    expect(d.tree.value[0].content_type).toBe('content')
  })

  it('markRows 预填解析级别；markIndents 按字面级别给缩进', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([
      pnode({ id: 'a', children: [pnode({ id: 'a1', content_type: 'content', rich_content: '<p>x</p>' })] }),
    ]))
    d.toggleLayerMarking()
    expect(d.markRows.value.map((r) => r.id)).toEqual(['a', 'a1'])
    expect(d.roleMap.value.get('a')).toBe('chapter_1')
    expect(d.roleMap.value.get('a1')).toBe('content')
    expect(d.markIndents.value.get('a')).toBe(0)
    expect(d.markIndents.value.get('a1')).toBe(1)
  })

  it('exitMode 直接调用也应用 roleMap（完成按钮路径）', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' }), pnode({ id: 'b' })]))
    d.toggleLayerMarking()
    d.setRole('b', 'chapter_2')
    d.exitMode()
    expect(d.mode.value).toBe('normal')
    expect(d.levelMap.value.get('b')).toBe(2)
  })

  it('空树进入层级标定：markRows 为空', () => {
    const d = useImportDialog()
    d.toggleLayerMarking()
    expect(d.mode.value).toBe('layer-marking')
    expect(d.markRows.value).toEqual([])
    expect(d.markIndents.value.size).toBe(0)
  })

  it('layer-marking 中重置（loadParseResult）清空标定状态，不残留旧 baseline', () => {
    const d = useImportDialog()
    d.loadParseResult(mkParse([pnode({ id: 'a' }), pnode({ id: 'b' })]))
    d.toggleLayerMarking()
    d.setRole('b', 'chapter_2')
    d.loadParseResult(mkParse([pnode({ id: 'x' })])) // 重置核心动作
    expect(d.mode.value).toBe('normal')
    expect(d.roleMap.value.size).toBe(0)
    expect(d.markingBaseline.value).toBeNull()
    expect(d.tree.value.map((n) => n.id)).toEqual(['x'])
  })
})
