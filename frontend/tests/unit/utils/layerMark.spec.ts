import { describe, it, expect } from 'vitest'
import {
  computeLayerIndents,
  computeLayerUpdates,
  defaultLayerRole,
  validateLayerQ25,
  type LayerRole,
  type LayerRow,
} from '@/utils/layerMark'
import fixtures from '../../fixtures/layerWalkFixtures.json'

function row(
  id: string,
  kind: 'chapter' | 'step' | 'content',
  level: number,
  hasLeafChildren = false,
): LayerRow {
  return { id, kind, level, hasLeafChildren }
}

describe('layerMark', () => {
  it('computeLayerUpdates：一级/二级嵌套 + content 角色挂最近章节、toContentStep', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 1), row('c', 'chapter', 1)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['b', 'chapter_2'], ['c', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('a')).toEqual({ kind: 'reorder', parent_id: null, sort_order: 0, level: 1 })
    expect(u.get('b')).toEqual({ kind: 'reorder', parent_id: 'a', sort_order: 0, level: 2 })
    expect(u.get('c')).toEqual({ kind: 'to-content', parent_id: 'b', sort_order: 0 })
  })

  it('content 行不更新 l1/l2/l3 上下文（后续 content 仍挂上一个标题）', () => {
    // a(l1) c(content) d(content)：两条 content 都挂到 a，且 content 行不改变上下文
    const rows = [row('a', 'chapter', 1), row('c', 'chapter', 2), row('d', 'chapter', 2)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['c', 'content'], ['d', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    expect(u.get('c')).toEqual({ kind: 'to-content', parent_id: 'a', sort_order: 0 })
    expect(u.get('d')).toEqual({ kind: 'to-content', parent_id: 'a', sort_order: 1 })
  })

  it('不可达层级夹紧：二级无一级父→根', () => {
    const rows = [row('a', 'chapter', 1)]
    const u = computeLayerUpdates(rows, new Map([['a', 'chapter_2']]))
    expect(u.get('a')).toEqual({ kind: 'reorder', parent_id: null, sort_order: 0, level: 1 })
  })

  it('含叶子（步骤/内容块）子节点的行标 content 仍保持章节', () => {
    const rows = [row('a', 'chapter', 1, true)]
    const u = computeLayerUpdates(rows, new Map([['a', 'content']]))
    expect(u.get('a')).toEqual({ kind: 'reorder', parent_id: null, sort_order: 0, level: 1 })
  })

  it('computeLayerIndents：章节 = level-1，content = 当前标题层级', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 2)]
    const m = new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']])
    const ind = computeLayerIndents(rows, m)
    expect(ind.get('a')).toBe(0)
    expect(ind.get('b')).toBe(1)
  })

  it('defaultLayerRole with LayerRow：章节行按 level 夹到 chapter_1/2/3', () => {
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 1, hasLeafChildren: false })).toBe('chapter_1')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 2, hasLeafChildren: false })).toBe('chapter_2')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 7, hasLeafChildren: false })).toBe('chapter_3')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 0, hasLeafChildren: false })).toBe('chapter_1')
  })

  it('defaultLayerRole with LayerRow：叶子行默认 keep', () => {
    expect(defaultLayerRole({ id: 's', kind: 'step', level: 0, hasLeafChildren: false })).toBe('keep')
    expect(defaultLayerRole({ id: 'c', kind: 'content', level: 0, hasLeafChildren: false })).toBe('keep')
  })
})

describe('computeLayerUpdates with leaves', () => {
  it('叶子保持 keep → 输出 leaf-reparent，挂到最近标题', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([['A', 'chapter_1']])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('A')).toEqual({ kind: 'reorder', parent_id: null, sort_order: 0, level: 1 })
    expect(u.get('s1')).toEqual({ kind: 'leaf-reparent', parent_id: 'A', sort_order: 0 })
  })

  it('叶子选 chapter_2 → 输出 to-chapter，并成为新 l2', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'c1', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([
      ['A', 'chapter_1'],
      ['c1', 'chapter_2'],
    ])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('s1')).toEqual({ kind: 'leaf-reparent', parent_id: 'A', sort_order: 0 })
    expect(u.get('c1')).toEqual({ kind: 'to-chapter', parent_id: 'A', sort_order: 1, level: 2 })
    expect(u.get('s2')).toEqual({ kind: 'leaf-reparent', parent_id: 'c1', sort_order: 0 })
  })

  it('叶子选 chapter_X 但无可挂父：chapter_2 无 l1 → 挂根成 L1', () => {
    const rows: LayerRow[] = [
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([['s1', 'chapter_2']])
    const u = computeLayerUpdates(rows, roles)
    expect(u.get('s1')).toEqual({ kind: 'to-chapter', parent_id: null, sort_order: 0, level: 1 })
  })
})

describe('computeLayerIndents with leaves', () => {
  it('叶子继承当前 heading level；提升后自身缩进按新 level', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'c1', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const roles = new Map<string, LayerRole>([
      ['A', 'chapter_1'],
      ['c1', 'chapter_2'],
    ])
    const m = computeLayerIndents(rows, roles)
    expect(m.get('A')).toBe(0) // L1 → 0
    expect(m.get('s1')).toBe(1) // 挂在 L1 下
    expect(m.get('c1')).toBe(1) // 自己被提升为 L2 → indent=1
    expect(m.get('s2')).toBe(2) // 挂在新 L2 下
  })
})

describe('validateLayerQ25', () => {
  it('提升一个叶子,父下另一叶子被 walk 挂到新章节下 → 无冲突', () => {
    // s1, s2 都在 A 下,s1 升 L2,walk 算 s2.parent=s1(末态正确)
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })

  it('文档序内,先 keep 叶子后 to-chapter 叶子 → 共享父 A 出现混合 → 冲突', () => {
    // k 在 s1 之前,walk: A reorder@null, k leaf-reparent@A, s1 to-chapter@A
    // A 下:[s1(chapter), k(leaf)] → 冲突
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 'k', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    const conflicts = validateLayerQ25(rows, updates)
    expect(conflicts).toHaveLength(1)
    expect(conflicts[0].parent_id).toBe('A')
    expect(conflicts[0].chapterChildren).toEqual(['s1'])
    expect(conflicts[0].leafChildren).toEqual(['k'])
  })

  it('全 leaf 兄弟(无章节兄弟) → 无冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([['A', 'chapter_1']]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })

  it('父下唯一 step 提升 → 无冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })
})

describe('computeLayerUpdates — shared fixture equivalence', () => {
  for (const fx of fixtures.fixtures) {
    it(`fixture: ${fx.name}`, () => {
      const rows: LayerRow[] = fx.rows.map((r: any) => ({
        id: r.id,
        kind: r.kind,
        level: r.level,
        hasLeafChildren: r.hasLeafChildren,
      }))
      const roleMap = new Map<string, LayerRole>(
        Object.entries(fx.roles) as [string, LayerRole][]
      )
      const updates = computeLayerUpdates(rows, roleMap)
      const actual: Record<string, unknown> = {}
      for (const [k, v] of updates) actual[k] = v
      expect(actual).toEqual(fx.updates)
    })
  }
})
