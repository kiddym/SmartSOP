import { describe, expect, it } from 'vitest'
import {
  applyBatchMark,
  buildMarkedBlocks,
  rebuildTreeFromMarks,
  toImportNodesFromBlocks,
  validateMarkedBlocks,
  type MarkedImportBlock,
} from '@/utils/importBlocks'
import type { ParsedImportBlock } from '@/types/parse'

function block(partial: Partial<ParsedImportBlock> & { id: string; source_index: number; raw_text: string }): ParsedImportBlock {
  return {
    id: partial.id,
    source_index: partial.source_index,
    raw_text: partial.raw_text,
    display_text: partial.display_text ?? partial.raw_text,
    clean_text: partial.clean_text ?? partial.raw_text,
    rich_content: partial.rich_content ?? `<p>${partial.raw_text}</p>`,
    block_type: partial.block_type ?? 'paragraph',
    has_word_numbering: partial.has_word_numbering ?? false,
    word_number: partial.word_number ?? null,
    word_number_level: partial.word_number_level ?? null,
    style_name: partial.style_name ?? null,
    suggested_type: partial.suggested_type ?? 'content',
    suggested_level: partial.suggested_level ?? null,
    confidence_tier: partial.confidence_tier ?? 'low',
    mark_status: partial.mark_status ?? 'unmarked',
  }
}

function sample(): MarkedImportBlock[] {
  return buildMarkedBlocks([
    block({ id: 'b1', source_index: 1, raw_text: '目的', clean_text: '目的' }),
    block({ id: 'b2', source_index: 2, raw_text: '正文一' }),
    block({ id: 'b3', source_index: 3, raw_text: '范围', clean_text: '范围' }),
    block({ id: 'b4', source_index: 4, raw_text: '职责', clean_text: '职责' }),
    block({ id: 'b5', source_index: 5, raw_text: '正文二' }),
  ])
}

describe('importBlocks 标定纯函数', () => {
  it('buildMarkedBlocks 按 source_index 排序并用解析建议预标定章节', () => {
    const out = buildMarkedBlocks([
      block({ id: 'b2', source_index: 2, raw_text: '正文' }),
      block({ id: 'b1', source_index: 1, raw_text: '目的', suggested_type: 'chapter', suggested_level: 1 }),
    ])

    expect(out.map((b) => b.id)).toEqual(['b1', 'b2'])
    expect(out[0].assigned_role).toBe('chapter_1')
    expect(out[1].assigned_role).toBe('content')
  })

  it('applyBatchMark 批量标定且保持不可变', () => {
    const blocks = sample()
    const next = applyBatchMark(blocks, ['b1', 'b3'], 'chapter_1')

    expect(next.find((b) => b.id === 'b1')?.assigned_role).toBe('chapter_1')
    expect(next.find((b) => b.id === 'b3')?.assigned_role).toBe('chapter_1')
    expect(blocks.find((b) => b.id === 'b1')?.assigned_role).toBe('content')
  })

  it('rebuildTreeFromMarks 根据一级二级三级章节重建树', () => {
    let blocks = sample()
    blocks = applyBatchMark(blocks, ['b1'], 'chapter_1')
    blocks = applyBatchMark(blocks, ['b3'], 'chapter_2')
    blocks = applyBatchMark(blocks, ['b4'], 'chapter_3')

    const tree = rebuildTreeFromMarks(blocks)

    expect(tree).toHaveLength(1)
    expect(tree[0].title).toBe('目的')
    expect(tree[0].children[0].content_type).toBe('content')
    expect(tree[0].children[1].title).toBe('范围')
    expect(tree[0].children[1].children[0].title).toBe('职责')
    expect(tree[0].skip_numbering).toBe(false)
  })

  it('validateMarkedBlocks 阻止二级章节缺少一级章节', () => {
    const blocks = applyBatchMark(sample(), ['b3'], 'chapter_2')
    const issues = validateMarkedBlocks(blocks)

    expect(issues).toContainEqual({
      block_id: 'b3',
      level: 'error',
      message: '二级章节前缺少一级章节',
    })
  })

  it('toImportNodesFromBlocks 输出导入结构且清理 review', () => {
    let blocks = sample()
    blocks = applyBatchMark(blocks, ['b1'], 'chapter_1')
    blocks = blocks.map((b) => (b.id === 'b1' ? { ...b, mark_status: 'review' } : b))

    const out = toImportNodesFromBlocks(blocks)

    expect(out[0]).toMatchObject({
      title: '目的',
      content_type: 'chapter',
      rich_content: '',
      skip_numbering: false,
      mark_status: 'unmarked',
    })
  })
})
