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

// 从富文本提取纯文本标题（去标签 / 合并空白 / 截断）。用于「内容升级为章节」。
export function titleFromHtml(html: string): string {
  const text = html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim()
  return text.slice(0, 80)
}

export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content'

const clampLevel = (n: number): number => Math.min(3, Math.max(1, n))

// 层级标定：把 ids 内的节点设为目标角色（章节 N 级 / 正文），按「重建」语义一次性产出新树。
//
// 取代旧的「逐节点相对升降级凑深度」(moveToDepth)，根治四类缺陷：
//   - 顺序相关：先把整棵树按文档序拍平，结果与点选顺序无关。
//   - 子树脱节：选中章节按 delta=目标层级-当前层级 平移，其后代同步平移，保持父子关系。
//   - 静默错层：重建时夹紧到「最近可达父」下，绝不静默丢标记。
//   - 非法树：章节只挂到章节父；前驱是正文 / 缺父时夹紧为更浅层级，绝不嵌进 content。
// 内容↔章节互转保数据：content→章节用文本作标题、清空正文；章节→content 把标题文本回填正文。
export function applyLayerRole(
  nodes: WizardNode[],
  ids: string[],
  role: LayerRole,
): WizardNode[] {
  const idSet = new Set(ids)
  if (idSet.size === 0) return nodes

  const toContent = role === 'content'
  const targetLevel = role === 'chapter_1' ? 1 : role === 'chapter_2' ? 2 : 3

  // 拍平为文档序，并计算每个节点的「意向章节层级」。
  // delta 由「最近的被选中祖先（含自身）」决定，使被选子树整体平移。
  interface FlatItem {
    node: WizardNode
    intendedLevel: number
    asChapter: boolean
  }
  const flat: FlatItem[] = []
  const walk = (list: WizardNode[], depth: number, inheritedDelta: number): void => {
    for (const n of list) {
      let delta = inheritedDelta
      let asChapter: boolean
      if (idSet.has(n.id)) {
        if (toContent) {
          asChapter = false
        } else {
          asChapter = true
          delta = targetLevel - depth // 自身及其后代整体平移
        }
      } else {
        asChapter = n.content_type === 'chapter'
      }
      flat.push({ node: n, intendedLevel: clampLevel(depth + delta), asChapter })
      walk(n.children, depth + 1, delta)
    }
  }
  walk(nodes, 1, 0)

  // 按意向层级重建：章节挂到最近可达的章节父，正文挂到当前打开的最深章节。
  const roots: WizardNode[] = []
  let l1: WizardNode | null = null
  let l2: WizardNode | null = null
  let l3: WizardNode | null = null

  for (const { node, intendedLevel, asChapter } of flat) {
    const fromContent = asChapter && node.content_type === 'content'
    const toContentNode = !asChapter && node.content_type === 'chapter'
    const fresh: WizardNode = {
      ...node,
      content_type: asChapter ? 'chapter' : 'content',
      title: fromContent ? node.title.trim() || titleFromHtml(node.rich_content) : node.title,
      // 章节正文恒空；章节→正文时把标题文本回填正文避免丢失。
      rich_content: asChapter
        ? ''
        : toContentNode
          ? node.rich_content || (node.title.trim() ? `<p>${node.title.trim()}</p>` : '')
          : node.rich_content,
      skip_numbering: asChapter ? (fromContent ? false : node.skip_numbering) : true,
      children: [],
    }

    if (!asChapter) {
      const parent = l3 ?? l2 ?? l1
      if (parent) parent.children.push(fresh)
      else roots.push(fresh)
      continue
    }

    if (intendedLevel >= 3 && l2) {
      l2.children.push(fresh)
      l3 = fresh
    } else if (intendedLevel >= 2 && l1) {
      l1.children.push(fresh)
      l2 = fresh
      l3 = null
    } else {
      roots.push(fresh)
      l1 = fresh
      l2 = null
      l3 = null
    }
  }

  return roots
}

// ---- 平铺逐段层级标定（import-v2 标定模式用） ---- //

export interface MarkRow {
  id: string
  label: string // 章节用 title；正文用去标签摘要
  defaultRole: LayerRole
}

// 节点 + 深度 → 解析器当前级别：content→content；章节按深度→chapter_1/2/3。
// depth 为 1-based 树深度（≥1）；超出 1..3 的值会被夹紧。
export function defaultRoleOf(node: WizardNode, depth: number): LayerRole {
  if (node.content_type === 'content') return 'content'
  const lv = Math.min(3, Math.max(1, depth))
  return `chapter_${lv}` as LayerRole
}

// 按文档前序遍历拍平为平铺标定行（顺序 = Word 原文顺序）。
export function flattenForMarking(nodes: WizardNode[]): MarkRow[] {
  const rows: MarkRow[] = []
  const walk = (list: WizardNode[], depth: number): void => {
    for (const n of list) {
      rows.push({
        id: n.id,
        label: n.content_type === 'content' ? titleFromHtml(n.rich_content) : n.title || '（无标题）',
        defaultRole: defaultRoleOf(n, depth),
      })
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 1)
  return rows
}

// 章节角色 → 字面层级（1..3）。
function roleLevel(role: LayerRole): number {
  return role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
}

// 用「每段 id → 目标级别」映射表从基准树按文档序重建嵌套树。
// 每段都有显式级别（缺失回落 defaultRoleOf）；章节挂最近可达父、正文挂最深章节；
// 不可达层级夹紧（chapter_2 无一级父→根级；chapter_3 无二级父→退挂一级）；内容↔章节互转保数据。
export function buildTreeFromRoles(
  nodes: WizardNode[],
  roleMap: Map<string, LayerRole>,
): WizardNode[] {
  interface Flat { node: WizardNode; role: LayerRole }
  const flat: Flat[] = []
  const walk = (list: WizardNode[], depth: number): void => {
    for (const n of list) {
      flat.push({ node: n, role: roleMap.get(n.id) ?? defaultRoleOf(n, depth) })
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 1)

  const roots: WizardNode[] = []
  let l1: WizardNode | null = null
  let l2: WizardNode | null = null
  let l3: WizardNode | null = null

  for (const { node, role } of flat) {
    const asChapter = role !== 'content'
    const fromContent = asChapter && node.content_type === 'content'
    const toContentNode = !asChapter && node.content_type === 'chapter'
    const fresh: WizardNode = {
      ...node,
      content_type: asChapter ? 'chapter' : 'content',
      title: fromContent ? node.title.trim() || titleFromHtml(node.rich_content) : node.title,
      rich_content: asChapter
        ? ''
        : toContentNode
          ? node.rich_content || (node.title.trim() ? `<p>${node.title.trim()}</p>` : '')
          : node.rich_content,
      skip_numbering: asChapter ? (fromContent ? false : node.skip_numbering) : true,
      children: [],
    }

    if (!asChapter) {
      const parent = l3 ?? l2 ?? l1
      if (parent) parent.children.push(fresh)
      else roots.push(fresh)
      continue
    }

    // level 仅对章节有意义（正文已在上面 return）
    const level = roleLevel(role)
    if (level >= 3 && l2) {
      l2.children.push(fresh)
      l3 = fresh
    } else if (level >= 2 && l1) {
      l1.children.push(fresh)
      l2 = fresh
      l3 = null
    } else {
      roots.push(fresh)
      l1 = fresh
      l2 = null
      l3 = null
    }
  }

  return roots
}

// 平铺清单的「所见即所选」缩进：章节缩进 = 字面 level-1；正文 = 当前标题 level（深一级）。
export function computeMarkIndents(
  rows: MarkRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  for (const row of rows) {
    const role = roleMap.get(row.id) ?? row.defaultRole
    if (role === 'content') {
      map.set(row.id, headingLevel)
    } else {
      const lv = roleLevel(role)
      map.set(row.id, lv - 1)
      headingLevel = lv
    }
  }
  return map
}
