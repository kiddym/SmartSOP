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
  // O(1) child check: ids that appear as some node's parent_id.
  const parentIds = new Set<string>()
  for (const x of nodes) if (x.parent_id) parentIds.add(x.parent_id)
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
    rows.push({ node, title, hasChildren: parentIds.has(node.id), expanded: isExpanded(node.id) })
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

const LEVEL_SCALE: (number | null)[] = [null, 1, 2, 3]

/** 缩进/反缩进一步：在 [正文, L1, L2, L3] 标尺上移动并夹紧。
 * 'in' = 更深（→L3），'out' = 更浅（→正文）。未知层级（如旧 L>3）按最深处理。 */
export function indentLevel(current: number | null, dir: 'in' | 'out'): number | null {
  let idx = LEVEL_SCALE.indexOf(current)
  if (idx < 0) idx = current === null ? 0 : LEVEL_SCALE.length - 1
  const next = dir === 'in' ? Math.min(idx + 1, LEVEL_SCALE.length - 1) : Math.max(idx - 1, 0)
  return LEVEL_SCALE[next]
}

export type NavAction = { type: 'select' | 'expand' | 'collapse'; id: string }

/** Pure arrow-key navigation over the visible rows (tree-ordered; rows carry hasChildren/expanded;
 *  node.parent_id gives the parent). Returns the action, or null for a no-op (boundary/leaf/root). */
export function arrowNav(
  rows: TreeRow[],
  currentId: string | null,
  dir: 'up' | 'down' | 'left' | 'right',
): NavAction | null {
  const idx = rows.findIndex((r) => r.node.id === currentId)
  if (idx < 0) {
    return (dir === 'up' || dir === 'down') && rows.length
      ? { type: 'select', id: rows[0].node.id }
      : null
  }
  const r = rows[idx]
  if (dir === 'up') return idx > 0 ? { type: 'select', id: rows[idx - 1].node.id } : null
  if (dir === 'down') return idx < rows.length - 1 ? { type: 'select', id: rows[idx + 1].node.id } : null
  if (dir === 'right') {
    if (r.hasChildren && !r.expanded) return { type: 'expand', id: r.node.id }
    if (r.hasChildren && r.expanded) {
      const child = rows.find((x, j) => j > idx && x.node.parent_id === r.node.id)
      return child ? { type: 'select', id: child.node.id } : null
    }
    return null
  }
  // left
  if (r.hasChildren && r.expanded) return { type: 'collapse', id: r.node.id }
  const pid = r.node.parent_id
  return pid && rows.some((x) => x.node.id === pid) ? { type: 'select', id: pid } : null
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
