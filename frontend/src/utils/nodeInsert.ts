import type { Node } from '@/types/node'
import { subtreeIds } from './nodeTree'

// 行级新增的插入位置计算（spec：派生树由 sort_order + heading_level 算出）。
// after-node    = 紧跟参考节点之后（成为其第一个子级 / 同层叶子）。
// after-subtree = 跳过参考节点的整棵子树后插入（同级章节，避免吞并其子节点）。
export type InsertMode = 'after-node' | 'after-subtree'

const GAP = 1000

const ordered = (nodes: Node[]): Node[] =>
  [...nodes].sort((a, b) => a.sort_order - b.sort_order || (a.id < b.id ? -1 : 1))

/**
 * 返回新节点应取的 sort_order；相邻两节点间无整数空隙时返回 null（调用方应先重排再重算）。
 * 子树在 sort_order 上连续（派生算法保证），故 after-subtree 沿排序向后吞到末个后代为止。
 */
export function insertSortOrder(nodes: Node[], refId: string, mode: InsertMode): number | null {
  const rows = ordered(nodes)
  const i = rows.findIndex((x) => x.id === refId)
  if (i < 0) {
    const last = rows[rows.length - 1]
    return last ? last.sort_order + GAP : GAP
  }

  let afterIdx = i
  if (mode === 'after-subtree') {
    const sub = new Set(subtreeIds(nodes, refId))
    while (afterIdx + 1 < rows.length && sub.has(rows[afterIdx + 1].id)) afterIdx++
  }

  const lo = rows[afterIdx].sort_order
  const hi = afterIdx + 1 < rows.length ? rows[afterIdx + 1].sort_order : null
  if (hi === null) return lo + GAP
  if (hi - lo >= 2) return Math.floor((lo + hi) / 2)
  return null
}
