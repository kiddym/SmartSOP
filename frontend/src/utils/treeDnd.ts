// 树拖拽的纯决策逻辑（从 ChapterTreePanel 抽出，便于单测）。
// 校验规则：不拖入自身子树（章节循环）、inside 仅对章节容器、章节最大 3 级、Q25 同父类型不混排。
import { getAddButtonState } from '@/utils/editor'
import type { EditorChapter, EditorStep, FlatRow, NodeKind } from '@/types/node'

export type DropHint = 'before' | 'after' | 'inside'

// 拖拽判定所需的树快照（由 store getter 组装；纯函数不直接依赖 store）。
export interface DndTree {
  chapters: EditorChapter[]
  steps: EditorStep[]
  levelMap: Map<string, number> // 章节 id → 层级（root 章节 = 1）
}

type Sortable = { sort_order: number; id: string }
const byOrder = (a: Sortable, b: Sortable): number =>
  a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1

export function kindOf(tree: DndTree, id: string): NodeKind {
  if (tree.chapters.some((x) => x.id === id)) return 'chapter'
  const s = tree.steps.find((x) => x.id === id)
  return s?.kind === 'content' ? 'content' : 'step'
}

/** 含 root 的章节子树 id 集合（与 store.collectSubtree 同义：沿章节 parent_id 闭包）。 */
export function subtreeChapterIds(chapters: EditorChapter[], rootId: string): Set<string> {
  const ids = new Set<string>([rootId])
  let changed = true
  while (changed) {
    changed = false
    for (const c of chapters) {
      if (c.parent_id && ids.has(c.parent_id) && !ids.has(c.id)) {
        ids.add(c.id)
        changed = true
      }
    }
  }
  return ids
}

/** 章节子树的章节嵌套高度（章节才计；步骤/内容块同属叶子项不计）。 */
export function subtreeChapterHeight(chapters: EditorChapter[], id: string): number {
  const kids = chapters.filter((c) => c.parent_id === id)
  return kids.length ? 1 + Math.max(...kids.map((k) => subtreeChapterHeight(chapters, k.id))) : 1
}

/** 某 parent 下的同类同胞（章节或步骤），按 sort_order/id 排序。 */
export function siblingsOf(
  tree: DndTree,
  parentId: string | null,
  asChapter: boolean,
): (EditorChapter | EditorStep)[] {
  return asChapter
    ? [...tree.chapters.filter((c) => c.parent_id === parentId)].sort(byOrder)
    : [...tree.steps.filter((s) => s.chapter_id === parentId)].sort(byOrder)
}

/** 拖 id 落到 target 的 hint 位置是否合法。 */
export function validDrop(tree: DndTree, id: string, target: FlatRow, hint: DropHint): boolean {
  if (id === target.id) return false
  const parentId = hint === 'inside' ? target.id : target.parent_id
  const dragged = kindOf(tree, id)
  const isChapter = tree.chapters.some((c) => c.id === id)
  // 不得拖入自身子树（章节循环）。
  if (isChapter) {
    const sub = subtreeChapterIds(tree.chapters, id)
    if (parentId && sub.has(parentId)) return false
  }
  // 'inside' 仅对章节容器有效。
  if (hint === 'inside' && target.kind !== 'chapter') return false
  // 章节最大嵌套 3 级（§2.4 / CHAPTER_DEPTH_EXCEEDED）：新位层级 + 子树高度 - 1 ≤ 3。
  if (dragged === 'chapter') {
    const parentLevel = parentId ? (tree.levelMap.get(parentId) ?? 1) : 0
    if (parentLevel + 1 + subtreeChapterHeight(tree.chapters, id) - 1 > 3) return false
  }
  // Q25：目标 parent 现有子类型（排除被拖节点）+ 被拖类型不得混排（与 store.childKindsOf 同义）。
  const kinds: NodeKind[] = []
  for (const c of tree.chapters) if (c.parent_id === parentId && c.id !== id) kinds.push('chapter')
  for (const s of tree.steps)
    if (s.chapter_id === parentId && s.id !== id) kinds.push(s.kind === 'content' ? 'content' : 'step')
  const st = getAddButtonState(kinds)
  if (dragged === 'step') return st.canAddStep
  if (dragged === 'content') return st.canAddContent
  return st.canAddChapter
}

export interface DropPlan {
  parentId: string | null
  index: number
  currentParent: string | null // 同 parent → 组内重排；否则 → 跨父移动
}

/** 由合法 drop 算目标父级、插入下标与当前父级。 */
export function computeDrop(tree: DndTree, id: string, target: FlatRow, hint: DropHint): DropPlan {
  const asChapter = tree.chapters.some((c) => c.id === id)
  const parentId = hint === 'inside' ? target.id : target.parent_id
  const others = siblingsOf(tree, parentId, asChapter).filter((n) => n.id !== id)
  let index: number
  if (hint === 'inside') index = others.length
  else {
    const ti = others.findIndex((n) => n.id === target.id)
    index = (ti < 0 ? others.length : ti) + (hint === 'after' ? 1 : 0)
  }
  const dragChapter = tree.chapters.find((c) => c.id === id)
  const currentParent = dragChapter
    ? dragChapter.parent_id
    : (tree.steps.find((s) => s.id === id)?.chapter_id ?? null)
  return { parentId, index, currentParent }
}
