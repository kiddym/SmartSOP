import { describe, it, expect } from 'vitest'
import {
  computeLayerIndents,
  computeLayerUpdates,
  defaultLayerRole,
  type LayerRole,
  type LayerRow,
} from '@/utils/layerMark'

function row(id: string, content_type: 'chapter' | 'content', level: number, hasStepChildren = false): LayerRow {
  return { id, content_type, level, hasStepChildren }
}

describe('layerMark', () => {
  it('defaultLayerRole：content→content；章节按 level 夹 1..3', () => {
    expect(defaultLayerRole('content', 2)).toBe('content')
    expect(defaultLayerRole('chapter', 1)).toBe('chapter_1')
    expect(defaultLayerRole('chapter', 5)).toBe('chapter_3')
  })

  it('computeLayerUpdates：一级/二级/三级嵌套 + 正文挂最近章节', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 1), row('c', 'content', 1)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['b', 'chapter_2'], ['c', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('a')).toEqual({ parent_id: null, content_type: 'chapter', sort_order: 0 })
    expect(u.get('b')).toEqual({ parent_id: 'a', content_type: 'chapter', sort_order: 0 })
    expect(u.get('c')).toEqual({ parent_id: 'b', content_type: 'content', sort_order: 0 })
  })

  it('不可达层级夹紧：二级无一级父→根', () => {
    const rows = [row('a', 'chapter', 1)]
    const u = computeLayerUpdates(rows, new Map([['a', 'chapter_2']]))
    expect(u.get('a')?.parent_id).toBeNull()
  })

  it('含步骤子节点的行标 content 仍保持章节', () => {
    const rows = [row('a', 'chapter', 1, true)]
    const u = computeLayerUpdates(rows, new Map([['a', 'content']]))
    expect(u.get('a')?.content_type).toBe('chapter')
  })

  it('computeLayerIndents：章节 = level-1，正文 = 当前标题层级', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'content', 2)]
    const m = new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']])
    const ind = computeLayerIndents(rows, m)
    expect(ind.get('a')).toBe(0)
    expect(ind.get('b')).toBe(1)
  })
})
