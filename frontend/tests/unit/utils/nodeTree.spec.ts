import { describe, expect, it } from 'vitest'
import { nodeTitle, hasChildren, visibleRows, descendantIds, subtreeIds, checkStates } from '@/utils/nodeTree'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

describe('nodeTitle', () => {
  it('takes the first block element text', () => {
    expect(nodeTitle(n({ body: '<p>目的</p><p>其余</p>' }))).toBe('目的')
  })
  it('unescapes entities and strips nested tags', () => {
    expect(nodeTitle(n({ body: '<p>A &amp; <b>B</b></p>' }))).toBe('A & B')
  })
  it('empty body falls back', () => {
    expect(nodeTitle(n({ body: '', heading_level: 1 }))).toBe('未命名章节')
    expect(nodeTitle(n({ body: '   ' }))).toBe('未命名章节')
  })
})

describe('hasChildren', () => {
  it('true when some node has this id as parent_id', () => {
    const nodes = [n({ id: 'a', heading_level: 1 }), n({ id: 'b', parent_id: 'a' })]
    expect(hasChildren(nodes, 'a')).toBe(true)
    expect(hasChildren(nodes, 'b')).toBe(false)
  })
})

describe('visibleRows', () => {
  const nodes = [
    n({ id: 'a', heading_level: 1, depth: 0, parent_id: null, body: '<p>A</p>' }),
    n({ id: 'b', heading_level: 2, depth: 1, parent_id: 'a', body: '<p>B</p>' }),
    n({ id: 'c', depth: 2, parent_id: 'b', body: '<p>c</p>' }),
  ]
  it('collapsing a node hides its descendants', () => {
    const rows = visibleRows(nodes, { a: true, b: false }, { search: '', reviewOnly: false })
    expect(rows.map((r) => r.node.id)).toEqual(['a', 'b']) // c hidden under collapsed b
  })
  it('all expanded shows everything', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: '', reviewOnly: false })
    expect(rows.map((r) => r.node.id)).toEqual(['a', 'b', 'c'])
  })
  it('reviewOnly filters to review nodes', () => {
    const rv = [n({ id: 'a', body: '<p>A</p>', mark_status: 'review' }), n({ id: 'b', body: '<p>B</p>' })]
    const rows = visibleRows(rv, {}, { search: '', reviewOnly: true })
    expect(rows.map((r) => r.node.id)).toEqual(['a'])
  })
  it('search matches title text', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: 'B', reviewOnly: false })
    expect(rows.map((r) => r.node.id)).toEqual(['b'])
  })
  it('row carries derived title + hasChildren + expanded', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: '', reviewOnly: false })
    expect(rows[0]).toMatchObject({ title: 'A', hasChildren: true, expanded: true })
    expect(rows[0].node.id).toBe('a')
  })
})

describe('descendantIds / subtreeIds', () => {
  // tree: c1 > (a, c2 > (b)), c3
  const nodes = [
    n({ id: 'c1', heading_level: 1, sort_order: 0 }),
    n({ id: 'a', parent_id: 'c1', sort_order: 1000 }),
    n({ id: 'c2', heading_level: 2, parent_id: 'c1', sort_order: 2000 }),
    n({ id: 'b', parent_id: 'c2', sort_order: 3000 }),
    n({ id: 'c3', heading_level: 1, sort_order: 4000 }),
  ]
  it('descendantIds: all transitive descendants (excl. self)', () => {
    expect(descendantIds(nodes, 'c1').sort()).toEqual(['a', 'b', 'c2'])
    expect(descendantIds(nodes, 'a')).toEqual([]) // leaf
    expect(descendantIds(nodes, 'c3')).toEqual([])
  })
  it('subtreeIds: self + descendants', () => {
    expect(subtreeIds(nodes, 'c2').sort()).toEqual(['b', 'c2'])
    expect(subtreeIds(nodes, 'a')).toEqual(['a'])
  })
})

describe('checkStates', () => {
  const nodes = [
    n({ id: 'c1', heading_level: 1, sort_order: 0 }),
    n({ id: 'a', parent_id: 'c1', sort_order: 1000 }),
    n({ id: 'b', parent_id: 'c1', sort_order: 2000 }),
  ]
  it('heading checked when whole subtree selected', () => {
    const s = checkStates(nodes, new Set(['c1', 'a', 'b']))
    expect(s.get('c1')).toBe('checked')
  })
  it('heading indeterminate when partially selected', () => {
    const s = checkStates(nodes, new Set(['a']))
    expect(s.get('c1')).toBe('indeterminate')
    expect(s.get('a')).toBe('checked')
    expect(s.get('b')).toBe('unchecked')
  })
  it('heading unchecked when nothing selected', () => {
    const s = checkStates(nodes, new Set())
    expect(s.get('c1')).toBe('unchecked')
  })
})
