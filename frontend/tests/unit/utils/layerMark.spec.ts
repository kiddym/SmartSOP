import { describe, it, expect } from 'vitest'
import {
  computeLayerIndents,
  computeLayerUpdates,
  defaultLayerRole,
  type LayerRole,
  type LayerRow,
} from '@/utils/layerMark'

function row(id: string, level: number, hasLeafChildren = false): LayerRow {
  return { id, level, hasLeafChildren }
}

describe('layerMark', () => {
  it('defaultLayerRole：章节按 level 夹 1..3', () => {
    expect(defaultLayerRole(1)).toBe('chapter_1')
    expect(defaultLayerRole(2)).toBe('chapter_2')
    expect(defaultLayerRole(5)).toBe('chapter_3')
  })

  it('computeLayerUpdates：一级/二级嵌套 + content 角色挂最近章节、toContentStep', () => {
    const rows = [row('a', 1), row('b', 1), row('c', 1)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['b', 'chapter_2'], ['c', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('a')).toEqual({ parent_id: null, toContentStep: false, sort_order: 0 })
    expect(u.get('b')).toEqual({ parent_id: 'a', toContentStep: false, sort_order: 0 })
    expect(u.get('c')).toEqual({ parent_id: 'b', toContentStep: true, sort_order: 0 })
  })

  it('content 行不更新 l1/l2/l3 上下文（后续 content 仍挂上一个标题）', () => {
    // a(l1) c(content) d(content)：两条 content 都挂到 a，且 content 行不改变上下文
    const rows = [row('a', 1), row('c', 2), row('d', 2)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['c', 'content'], ['d', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('c')).toEqual({ parent_id: 'a', toContentStep: true, sort_order: 0 })
    expect(u.get('d')).toEqual({ parent_id: 'a', toContentStep: true, sort_order: 1 })
  })

  it('不可达层级夹紧：二级无一级父→根', () => {
    const rows = [row('a', 1)]
    const u = computeLayerUpdates(rows, new Map([['a', 'chapter_2']]))
    expect(u.get('a')?.parent_id).toBeNull()
    expect(u.get('a')?.toContentStep).toBe(false)
  })

  it('含叶子（步骤/内容块）子节点的行标 content 仍保持章节', () => {
    const rows = [row('a', 1, true)]
    const u = computeLayerUpdates(rows, new Map([['a', 'content']]))
    expect(u.get('a')?.toContentStep).toBe(false)
  })

  it('computeLayerIndents：章节 = level-1，content = 当前标题层级', () => {
    const rows = [row('a', 1), row('b', 2)]
    const m = new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']])
    const ind = computeLayerIndents(rows, m)
    expect(ind.get('a')).toBe(0)
    expect(ind.get('b')).toBe(1)
  })
})
