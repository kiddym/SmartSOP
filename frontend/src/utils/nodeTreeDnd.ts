import type { Node } from '@/types/node'

export type DropPosition = 'before' | 'after'

/** 子树感知重排：把 dragId（及其后 depth 更大的连续后代）整体移到 targetId 的 before/after，
 * 返回该程序全部节点的新 id 排列（喂给 store.reorder）。
 * 落点落在被拖块内部（拖到自己/后代）→ 原样返回（no-op）。
 * nodes 假定按 sort_order 升序、depth 为派生层级。 */
export function computeReorder(
  nodes: Pick<Node, 'id' | 'depth'>[],
  dragId: string,
  targetId: string,
  position: DropPosition,
): string[] {
  const ids = nodes.map((n) => n.id)
  const start = nodes.findIndex((n) => n.id === dragId)
  if (start < 0) return ids
  const dragDepth = nodes[start].depth
  let end = start
  while (end + 1 < nodes.length && nodes[end + 1].depth > dragDepth) end++
  const block = ids.slice(start, end + 1)
  const blockSet = new Set(block)
  if (blockSet.has(targetId)) return ids // 落在被拖块内 → no-op
  const rest = ids.filter((id) => !blockSet.has(id))
  const ti = rest.indexOf(targetId)
  if (ti < 0) return ids
  rest.splice(position === 'before' ? ti : ti + 1, 0, ...block)
  return rest
}
