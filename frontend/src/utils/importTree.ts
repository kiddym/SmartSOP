// 导入向导树审查纯函数（Q351/Q354）。全部不可变（返回新树），便于 Vue 响应式 + 测试。

import type { ConfidenceTier, ImportNode, ParsedNode } from '@/types/parse'
import type { ContentType, MarkStatus } from '@/types/node'

// 向导内部树节点：仅保留可编辑 / 渲染所需字段（丢弃 order/level/parent_id/heading_source 等派生项）。
export interface WizardNode {
  id: string
  title: string
  content_type: ContentType
  rich_content: string
  skip_numbering: boolean
  mark_status: MarkStatus
  confidence_tier: ConfidenceTier
  children: WizardNode[]
}

export function buildWizardTree(nodes: ParsedNode[]): WizardNode[] {
  return nodes.map((n) => ({
    id: n.id,
    title: n.title,
    content_type: n.content_type,
    rich_content: n.rich_content,
    skip_numbering: n.skip_numbering,
    mark_status: n.mark_status,
    confidence_tier: n.confidence_tier,
    children: buildWizardTree(n.children),
  }))
}

export function cloneTree(nodes: WizardNode[]): WizardNode[] {
  return nodes.map((n) => ({ ...n, children: cloneTree(n.children) }))
}

export function findNode(nodes: WizardNode[], id: string): WizardNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findNode(n.children, id)
    if (hit) return hit
  }
  return null
}

export function updateNode(
  nodes: WizardNode[],
  id: string,
  patch: Partial<Pick<WizardNode, 'title' | 'skip_numbering' | 'mark_status'>>,
): WizardNode[] {
  return nodes.map((n) => {
    if (n.id === id) return { ...n, ...patch, children: [...n.children] }
    return { ...n, children: updateNode(n.children, id, patch) }
  })
}

export function deleteNode(nodes: WizardNode[], id: string): WizardNode[] {
  return nodes
    .filter((n) => n.id !== id)
    .map((n) => ({ ...n, children: deleteNode(n.children, id) }))
}

// direction: -1 上移 / +1 下移；同级交换；边界 no-op。
export function moveNode(nodes: WizardNode[], id: string, direction: -1 | 1): WizardNode[] {
  const idx = nodes.findIndex((n) => n.id === id)
  if (idx !== -1) {
    const target = idx + direction
    if (target < 0 || target >= nodes.length) return nodes // 边界 no-op
    const next = [...nodes]
    ;[next[idx], next[target]] = [next[target], next[idx]]
    return next
  }
  return nodes.map((n) => ({ ...n, children: moveNode(n.children, id, direction) }))
}

export function countReview(nodes: WizardNode[]): number {
  return nodes.reduce(
    (acc, n) => acc + (n.mark_status === 'review' ? 1 : 0) + countReview(n.children),
    0,
  )
}

export function clearReview(nodes: WizardNode[]): WizardNode[] {
  return nodes.map((n) => ({
    ...n,
    mark_status: n.mark_status === 'review' ? 'unmarked' : n.mark_status,
    children: clearReview(n.children),
  }))
}

// 压成 POST /procedures/import 形态：丢弃向导内部字段 + 清 review（Q354，对齐后端 REVIEW_NOT_CLEARED）。
export function toImportNodes(nodes: WizardNode[]): ImportNode[] {
  return nodes.map((n) => ({
    title: n.title,
    content_type: n.content_type,
    rich_content: n.rich_content,
    skip_numbering: n.skip_numbering,
    mark_status: n.mark_status === 'review' ? 'unmarked' : n.mark_status,
    children: toImportNodes(n.children),
  }))
}

function _computeNumbers(nodes: WizardNode[], prefix: string): Record<string, string> {
  const result: Record<string, string> = {}
  let seq = 0
  for (const node of nodes) {
    if (node.content_type !== 'chapter') continue
    if (node.skip_numbering) {
      Object.assign(result, _computeNumbers(node.children, ''))
      continue
    }
    seq++
    const num = prefix ? `${prefix}.${seq}` : String(seq)
    result[node.id] = num
    Object.assign(result, _computeNumbers(node.children, num))
  }
  return result
}

export function computeChapterNumbers(nodes: WizardNode[]): Record<string, string> {
  return _computeNumbers(nodes, '')
}

// ---- 新增树操作（import-v2 弹窗用） ---- //

// 查找节点的直接父；根节点返回 null；找不到返回 null。
export function findParent(nodes: WizardNode[], id: string): WizardNode | null {
  for (const n of nodes) {
    if (n.children.some((c) => c.id === id)) return n
    const hit = findParent(n.children, id)
    if (hit) return hit
  }
  return null
}

// 节点 id → 层级深度（根为 1，子为 2，孙为 3...）。
export function computeLevelMap(nodes: WizardNode[]): Map<string, number> {
  const map = new Map<string, number>()
  const walk = (list: WizardNode[], depth: number): void => {
    for (const n of list) {
      map.set(n.id, depth)
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 1)
  return map
}

// 生成新节点 id（与解析 id 区分，用 'new-' 前缀）。
function genNodeId(): string {
  const uuid =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36)
  return `new-${uuid}`
}

function blankNode(contentType: ContentType): WizardNode {
  return {
    id: genNodeId(),
    title: '',
    content_type: contentType,
    rich_content: '',
    skip_numbering: contentType === 'content',
    mark_status: 'unmarked',
    confidence_tier: 'high',
    children: [],
  }
}

// 在 parentId 末尾添加子节点（parentId=null 表示根级末尾）。
export function addChildNode(
  nodes: WizardNode[],
  parentId: string | null,
  contentType: ContentType,
): WizardNode[] {
  const node = blankNode(contentType)
  if (parentId === null) return [...nodes, node]
  return nodes.map((n) => {
    if (n.id === parentId) return { ...n, children: [...n.children, node] }
    return { ...n, children: addChildNode(n.children, parentId, contentType) }
  })
}

// 在 siblingId 之后插入同级节点。
export function addSiblingNode(
  nodes: WizardNode[],
  siblingId: string,
  contentType: ContentType,
): WizardNode[] {
  const idx = nodes.findIndex((n) => n.id === siblingId)
  if (idx !== -1) {
    const node = blankNode(contentType)
    const next = [...nodes]
    next.splice(idx + 1, 0, node)
    return next
  }
  return nodes.map((n) => ({ ...n, children: addSiblingNode(n.children, siblingId, contentType) }))
}

// 提升节点：从父的 children 中移除，紧跟父之后插入到祖父的 children；根节点 no-op。
export function promoteNode(nodes: WizardNode[], id: string): WizardNode[] {
  const parent = findParent(nodes, id)
  if (!parent) return nodes // 已是根

  let extracted: WizardNode | null = null
  const removeFromParent = (list: WizardNode[]): WizardNode[] =>
    list.map((n) => {
      if (n.id === parent.id) {
        const found = n.children.find((c) => c.id === id)
        if (found) extracted = found
        return { ...n, children: n.children.filter((c) => c.id !== id) }
      }
      return { ...n, children: removeFromParent(n.children) }
    })
  const removed = removeFromParent(nodes)
  if (!extracted) return nodes

  const grandparent = findParent(nodes, parent.id)
  if (!grandparent) {
    // parent 在根
    const idx = removed.findIndex((n) => n.id === parent.id)
    const next = [...removed]
    next.splice(idx + 1, 0, extracted)
    return next
  }
  const insertAfterParent = (list: WizardNode[]): WizardNode[] =>
    list.map((n) => {
      if (n.id === grandparent.id) {
        const idx = n.children.findIndex((c) => c.id === parent.id)
        const next = [...n.children]
        next.splice(idx + 1, 0, extracted!)
        return { ...n, children: next }
      }
      return { ...n, children: insertAfterParent(n.children) }
    })
  return insertAfterParent(removed)
}

// 降级节点：移到「前一个同级」的 children 末尾；首位 no-op。
export function demoteNode(nodes: WizardNode[], id: string): WizardNode[] {
  const demoteWithin = (siblings: WizardNode[]): WizardNode[] => {
    const idx = siblings.findIndex((n) => n.id === id)
    if (idx <= 0) return siblings
    const node = siblings[idx]
    const prev = siblings[idx - 1]
    const next = siblings.filter((_, i) => i !== idx)
    next[idx - 1] = { ...prev, children: [...prev.children, { ...node, children: [...node.children] }] }
    return next
  }

  if (nodes.some((n) => n.id === id)) return demoteWithin(nodes)
  return nodes.map((n) => ({ ...n, children: demoteNode(n.children, id) }))
}

// 设置 mark_status（单 id 或 id 数组）；返回新树。
export function setMarkStatus(
  nodes: WizardNode[],
  idOrIds: string | string[],
  status: MarkStatus,
): WizardNode[] {
  const ids = new Set(Array.isArray(idOrIds) ? idOrIds : [idOrIds])
  const walk = (list: WizardNode[]): WizardNode[] =>
    list.map((n) => ({
      ...n,
      mark_status: ids.has(n.id) ? status : n.mark_status,
      children: walk(n.children),
    }))
  return walk(nodes)
}

// 从树中移除指定 id 的节点，返回 [新树, 被移除的节点列表]。保持子树完整。
export function extractIgnored(
  nodes: WizardNode[],
  ids: string[],
): [WizardNode[], WizardNode[]] {
  const idSet = new Set(ids)
  const removed: WizardNode[] = []
  const walk = (list: WizardNode[]): WizardNode[] => {
    const out: WizardNode[] = []
    for (const n of list) {
      if (idSet.has(n.id)) {
        removed.push(n)
        continue
      }
      out.push({ ...n, children: walk(n.children) })
    }
    return out
  }
  return [walk(nodes), removed]
}

// 把忽略节点追加回根末尾。
export function restoreFromIgnored(
  nodes: WizardNode[],
  ignored: WizardNode[],
): WizardNode[] {
  return [...nodes, ...ignored]
}
