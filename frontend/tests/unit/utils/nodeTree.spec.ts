import { describe, expect, it } from 'vitest'
import { nodeTitle, hasChildren, visibleRows } from '@/utils/nodeTree'
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
