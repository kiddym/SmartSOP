import { describe, expect, it } from 'vitest'
import { buildTree, collectDescendantIds } from '@/utils/tree'

interface Node {
  id: string
  parent_id: string | null
  name: string
}
const flat: Node[] = [
  { id: 'a', parent_id: null, name: 'A' },
  { id: 'b', parent_id: 'a', name: 'B' },
  { id: 'c', parent_id: 'b', name: 'C' },
  { id: 'd', parent_id: null, name: 'D' },
]

describe('buildTree', () => {
  it('按 parent_id 组装为森林并挂 children', () => {
    const tree = buildTree(flat)
    expect(tree.map((n) => n.id)).toEqual(['a', 'd'])
    expect(tree[0].children?.map((n) => n.id)).toEqual(['b'])
    expect(tree[0].children?.[0].children?.map((n) => n.id)).toEqual(['c'])
    expect(tree[1].children).toBeUndefined()
  })
  it('不污染原对象（不给叶子加空 children）', () => {
    const tree = buildTree(flat)
    expect(tree[1].children).toBeUndefined()
  })
})

describe('collectDescendantIds', () => {
  it('返回自身 + 全部后代 id', () => {
    expect([...collectDescendantIds(flat, 'a')].sort()).toEqual(['a', 'b', 'c'])
    expect([...collectDescendantIds(flat, 'b')].sort()).toEqual(['b', 'c'])
    expect([...collectDescendantIds(flat, 'd')].sort()).toEqual(['d'])
  })
})
