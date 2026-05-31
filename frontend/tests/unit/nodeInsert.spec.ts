import { describe, expect, it } from 'vitest'
import { insertSortOrder } from '@/utils/nodeInsert'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

// c1 ▸ (a, b)   c2
const tree = (): Node[] => [
  n({ id: 'c1', heading_level: 1, sort_order: 1000 }),
  n({ id: 'a', parent_id: 'c1', depth: 1, sort_order: 2000 }),
  n({ id: 'b', parent_id: 'c1', depth: 1, sort_order: 3000 }),
  n({ id: 'c2', heading_level: 1, sort_order: 4000 }),
]

describe('insertSortOrder', () => {
  it('after-node inserts the midpoint to the next row (first child)', () => {
    expect(insertSortOrder(tree(), 'c1', 'after-node')).toBe(1500)
  })

  it('after-subtree skips the whole subtree (sibling chapter)', () => {
    // c1 子树 = {c1,a,b}；插到 b(3000) 与 c2(4000) 之间
    expect(insertSortOrder(tree(), 'c1', 'after-subtree')).toBe(3500)
  })

  it('after-node on the last child lands before the next sibling chapter', () => {
    expect(insertSortOrder(tree(), 'b', 'after-node')).toBe(3500)
  })

  it('appends GAP past the end when there is no following row', () => {
    expect(insertSortOrder(tree(), 'c2', 'after-node')).toBe(5000)
    expect(insertSortOrder(tree(), 'c2', 'after-subtree')).toBe(5000)
  })

  it('returns null when neighbours leave no integer gap (caller rebalances)', () => {
    const tight = [n({ id: 'p', sort_order: 1000 }), n({ id: 'q', sort_order: 1001 })]
    expect(insertSortOrder(tight, 'p', 'after-node')).toBe(null)
  })

  it('unknown ref appends to the end', () => {
    expect(insertSortOrder(tree(), 'nope', 'after-node')).toBe(5000)
    expect(insertSortOrder([], 'nope', 'after-node')).toBe(1000)
  })
})
