import type { Node } from '@/types/node'

const FALLBACK = '未命名章节'

/** 标题 = body 第一个块级元素的纯文本（spec §2.3）；空 → 占位。用浏览器 DOMParser 解析。 */
export function nodeTitle(node: Node): string {
  const body = node.body
  if (!body || !body.trim()) return FALLBACK
  const doc = new DOMParser().parseFromString(body, 'text/html')
  const first = doc.body.firstElementChild
  const text = (first ? first.textContent : doc.body.textContent) ?? ''
  const trimmed = text.trim()
  return trimmed || FALLBACK
}

/** 该节点是否有派生子（有任何节点 parent_id === id）。 */
export function hasChildren(nodes: Node[], id: string): boolean {
  return nodes.some((x) => x.parent_id === id)
}

export interface TreeRow {
  node: Node
  title: string
  hasChildren: boolean
  expanded: boolean
}

export interface RowFilter {
  search: string
  reviewOnly: boolean
}

/** 渲染行：按展开态折叠（折叠的 heading 子树整体隐藏）+ review/search 过滤。
 * nodes 假定已按 sort_order 升序（服务端保证）。展开态缺省视为展开。 */
export function visibleRows(
  nodes: Node[],
  expanded: Record<string, boolean>,
  filter: RowFilter,
): TreeRow[] {
  const byId = new Map(nodes.map((x) => [x.id, x]))
  const isExpanded = (id: string): boolean => expanded[id] !== false

  // 某节点是否被某个折叠的祖先隐藏（沿 parent_id 链上溯）。
  const hiddenByCollapse = (node: Node): boolean => {
    let pid = node.parent_id
    while (pid) {
      if (!isExpanded(pid)) return true
      pid = byId.get(pid)?.parent_id ?? null
    }
    return false
  }

  const q = filter.search.trim().toLowerCase()
  const rows: TreeRow[] = []
  for (const node of nodes) {
    if (filter.reviewOnly && node.mark_status !== 'review') continue
    const title = nodeTitle(node)
    if (q && !title.toLowerCase().includes(q)) continue
    // search/reviewOnly 激活时不做折叠（展开匹配项可见）；否则按展开态折叠。
    if (!q && !filter.reviewOnly && hiddenByCollapse(node)) continue
    rows.push({ node, title, hasChildren: hasChildren(nodes, node.id), expanded: isExpanded(node.id) })
  }
  return rows
}

/** 沿 parent_id 反向闭包，返回 id 的所有后代（不含自身）。 */
export function descendantIds(nodes: Node[], id: string): string[] {
  const childrenByParent = new Map<string | null, string[]>()
  for (const x of nodes) {
    const arr = childrenByParent.get(x.parent_id)
    if (arr) arr.push(x.id)
    else childrenByParent.set(x.parent_id, [x.id])
  }
  const out: string[] = []
  const stack = [...(childrenByParent.get(id) ?? [])]
  while (stack.length) {
    const cur = stack.pop() as string
    out.push(cur)
    const kids = childrenByParent.get(cur)
    if (kids) stack.push(...kids)
  }
  return out
}

/** 子树 = 自身 + 所有后代。 */
export function subtreeIds(nodes: Node[], id: string): string[] {
  return [id, ...descendantIds(nodes, id)]
}

export type CheckState = 'checked' | 'indeterminate' | 'unchecked'

/** 每个节点的三态：其子树（含自身）全选=checked，部分=indeterminate，皆未选=unchecked。O(N)。 */
export function checkStates(nodes: Node[], selection: ReadonlySet<string>): Map<string, CheckState> {
  const childrenByParent = new Map<string | null, Node[]>()
  for (const x of nodes) {
    const arr = childrenByParent.get(x.parent_id)
    if (arr) arr.push(x)
    else childrenByParent.set(x.parent_id, [x])
  }
  const memo = new Map<string, { sel: number; total: number }>()
  const visit = (node: Node): { sel: number; total: number } => {
    const cached = memo.get(node.id)
    if (cached) return cached
    let sel = selection.has(node.id) ? 1 : 0
    let total = 1
    for (const c of childrenByParent.get(node.id) ?? []) {
      const r = visit(c)
      sel += r.sel
      total += r.total
    }
    const r = { sel, total }
    memo.set(node.id, r)
    return r
  }
  const out = new Map<string, CheckState>()
  for (const node of nodes) {
    const { sel, total } = visit(node)
    out.set(node.id, sel === 0 ? 'unchecked' : sel === total ? 'checked' : 'indeterminate')
  }
  return out
}
