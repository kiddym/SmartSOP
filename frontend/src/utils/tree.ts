/** 递归挂 children 的节点类型；叶子不含 children 键。 */
export type Tree<T> = T & { children?: Tree<T>[] }

/** 由扁平表按 parent_id 组装为森林；叶子不挂空 children（避免 el-table 误显展开箭头）。 */
export function buildTree<T extends { id: string; parent_id: string | null }>(
  flat: T[],
): Tree<T>[] {
  const byId = new Map<string, Tree<T>>()
  for (const item of flat) byId.set(item.id, { ...item })
  const roots: Tree<T>[] = []
  for (const node of byId.values()) {
    if (node.parent_id != null && byId.has(node.parent_id)) {
      const parent = byId.get(node.parent_id)!
      ;(parent.children ??= []).push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

/** 自身 + 全部后代 id（供父级选择器排除，防成环）。 */
export function collectDescendantIds<T extends { id: string; parent_id: string | null }>(
  flat: T[],
  rootId: string,
): Set<string> {
  const childrenOf = new Map<string, string[]>()
  for (const item of flat) {
    if (item.parent_id != null) {
      const arr = childrenOf.get(item.parent_id)
      if (arr) arr.push(item.id)
      else childrenOf.set(item.parent_id, [item.id])
    }
  }
  const out = new Set<string>()
  const stack = [rootId]
  while (stack.length) {
    const id = stack.pop()!
    if (out.has(id)) continue
    out.add(id)
    for (const child of childrenOf.get(id) ?? []) stack.push(child)
  }
  return out
}
