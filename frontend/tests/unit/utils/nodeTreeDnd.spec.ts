import { describe, expect, it } from 'vitest'
import { computeReorder } from '@/utils/nodeTreeDnd'

// depth 表达派生层级：a(0) 下挂 b(1)/c(1)，d(0) 独立。
const nodes = [
  { id: 'a', depth: 0 },
  { id: 'b', depth: 1 },
  { id: 'c', depth: 1 },
  { id: 'd', depth: 0 },
]

describe('computeReorder', () => {
  it('moves a leaf after a sibling', () => {
    expect(computeReorder(nodes, 'b', 'c', 'after')).toEqual(['a', 'c', 'b', 'd'])
  })
  it('moves a leaf before a sibling', () => {
    expect(computeReorder(nodes, 'c', 'b', 'before')).toEqual(['a', 'c', 'b', 'd'])
  })
  it('drags a heading and carries its whole subtree as a block', () => {
    expect(computeReorder(nodes, 'a', 'd', 'after')).toEqual(['d', 'a', 'b', 'c'])
  })
  it('drags a heading before another heading (subtree intact)', () => {
    expect(computeReorder(nodes, 'd', 'a', 'before')).toEqual(['d', 'a', 'b', 'c'])
  })
  it('dropping onto own descendant is a no-op', () => {
    expect(computeReorder(nodes, 'a', 'b', 'after')).toEqual(['a', 'b', 'c', 'd'])
  })
  it('unknown drag/target id returns the original order', () => {
    expect(computeReorder(nodes, 'zz', 'a', 'after')).toEqual(['a', 'b', 'c', 'd'])
    expect(computeReorder(nodes, 'a', 'zz', 'after')).toEqual(['a', 'b', 'c', 'd'])
  })
})
