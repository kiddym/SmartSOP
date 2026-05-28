import { describe, it, expect } from 'vitest'
import { buildSelection, buildCascadeSelection, MAX_BATCH_MARK } from '@/utils/batchMark'
import type { FlatRow } from '@/types/node'

const fr = (id: string, kind: FlatRow['kind'], parent: string | null): FlatRow => ({
  id,
  kind,
  depth: 0,
  parent_id: parent,
  title: id,
  code: '',
  skip_numbering: false,
  mark_status: 'unmarked',
  form_type: null,
  has_children: false,
  expanded: false,
  fallback: '',
})

const rows: FlatRow[] = [
  fr('c1', 'chapter', null),
  fr('a', 'content', 'c1'),
  fr('b', 'content', 'c1'),
  fr('s1', 'step', 'c1'),
  fr('c2', 'chapter', null),
  fr('d', 'content', 'c2'),
]

describe('buildSelection', () => {
  it('单击：选中并设锚点', () => {
    const r = buildSelection({ current: new Set(), anchor: null, rows, rowId: 'a', shift: false })
    expect([...r.selection]).toEqual(['a'])
    expect(r.anchor).toBe('a')
    expect(r.warnings).toEqual([])
  })

  it('再次单击：取消选中', () => {
    const r = buildSelection({ current: new Set(['a']), anchor: 'a', rows, rowId: 'a', shift: false })
    expect(r.selection.has('a')).toBe(false)
    expect(r.anchor).toBe('a')
  })

  it('shift 区间：选同父范围内的行', () => {
    const r = buildSelection({ current: new Set(['a']), anchor: 'a', rows, rowId: 'b', shift: true })
    expect([...r.selection].sort()).toEqual(['a', 'b'])
    expect(r.warnings).toEqual([])
  })

  it('shift 跨父：仅同父部分入选，跨父忽略并告警', () => {
    const r = buildSelection({ current: new Set(), anchor: 'a', rows, rowId: 'd', shift: true })
    expect([...r.selection].sort()).toEqual(['a', 'b', 's1']) // d 跨父忽略；s1 现在算同父入选（B 方案）
    expect(r.warnings).toContain('范围跨越了不同父节点，跨父部分已忽略')
  })

  it('shift 无锚点：退化为单击切换', () => {
    const r = buildSelection({ current: new Set(), anchor: null, rows, rowId: 'a', shift: true })
    expect([...r.selection]).toEqual(['a'])
    expect(r.anchor).toBe('a')
  })

  it('超 100：截断到最早的前 100 并告警（H1）', () => {
    const current = new Set(Array.from({ length: 100 }, (_, i) => `n${i}`))
    const r = buildSelection({ current, anchor: 'n0', rows, rowId: 'extra', shift: false })
    expect(r.selection.size).toBe(MAX_BATCH_MARK)
    expect(r.selection.has('extra')).toBe(false) // 新增的第 101 个被截掉，而非整段丢弃
    expect(r.selection.has('n0')).toBe(true) // 最早选中的保留
    expect(r.warnings.some((w) => w.includes('最多标记'))).toBe(true)
  })

  it('截断把锚点裁掉 → 锚点置 null（防错位）', () => {
    const current = new Set(Array.from({ length: 100 }, (_, i) => `n${i}`))
    const r = buildSelection({ current, anchor: 'n0', rows, rowId: 'extra', shift: false })
    expect(r.anchor).toBeNull() // 单击把锚点设为 extra，但 extra 被截掉
  })

  it('shift 区间：同父范围现在包含 step（B 方案）', () => {
    // a(idx 1) → s1(idx 3) 之间含 b(idx 2)。三者同父 c1，全部入选。
    const r = buildSelection({ current: new Set(['a']), anchor: 'a', rows, rowId: 's1', shift: true })
    expect([...r.selection].sort()).toEqual(['a', 'b', 's1'])
    expect(r.warnings).toEqual([])
  })
})

describe('buildSelection — node rows (kind node|step)', () => {
  it('selects node-kind rows (no chapter skip) and supports shift range within same parent', () => {
    const rows = [
      { id: 'a', parent_id: 'p', kind: 'node' },
      { id: 'b', parent_id: 'p', kind: 'step' },
      { id: 'c', parent_id: 'p', kind: 'node' },
    ]
    const first = buildSelection({ current: new Set(), anchor: null, rows, rowId: 'a', shift: false })
    expect([...first.selection]).toEqual(['a'])
    const range = buildSelection({ current: first.selection, anchor: 'a', rows, rowId: 'c', shift: true })
    expect([...range.selection].sort()).toEqual(['a', 'b', 'c'])
  })
})

describe('buildCascadeSelection', () => {
  it('select：空集合 + 章节级联 → 仅 descendantIds 入选（rootId 不入），anchor=rootId', () => {
    const r = buildCascadeSelection({
      current: new Set(),
      anchor: null,
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 's1']) // c1 自己不在
    expect(r.anchor).toBe('c1')
    expect(r.warnings).toEqual([])
  })

  it('deselect：仅移除 descendants；rootId 即使已在 current 也保持不动', () => {
    // c1 在 current 中是异常前置状态（章节本不该进 selection）；deselect 应只动 descendants，
    // 把 c1 留给上层逻辑自己清——这里验证 buildCascadeSelection 不擅自处理 rootId。
    const r = buildCascadeSelection({
      current: new Set(['c1', 'a', 'b', 's1', 'other']),
      anchor: 'c1',
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'deselect',
    })
    expect([...r.selection].sort()).toEqual(['c1', 'other']) // c1 没被动
    expect(r.anchor).toBe('c1')
  })

  it('select 部分命中：未在集合的后代被补齐（rootId 仍不入）', () => {
    const r = buildCascadeSelection({
      current: new Set(['a']),
      anchor: 'a',
      rootId: 'c1',
      descendantIds: ['a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 's1'])
  })

  it('超 100：截断到前 100 并告警；anchor 恒为 rootId（不受截断影响）', () => {
    const descendantIds = Array.from({ length: 150 }, (_, i) => `d${i}`)
    const r = buildCascadeSelection({
      current: new Set(),
      anchor: null,
      rootId: 'root',
      descendantIds,
      action: 'select',
    })
    expect(r.selection.size).toBe(MAX_BATCH_MARK)
    expect(r.warnings.some((w) => w.includes('最多标记'))).toBe(true)
    expect(r.selection.has('root')).toBe(false) // rootId 从不入选
    expect(r.selection.has('d0')).toBe(true) // 截断按插入序保留前 100 个 descendants
    expect(r.anchor).toBe('root') // anchor 不受截断影响
  })
})
