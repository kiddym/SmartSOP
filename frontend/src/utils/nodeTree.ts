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
