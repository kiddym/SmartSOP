// 标记模式批量选择的纯逻辑（从 ChapterTreePanel 抽出，便于单测）。
// shift 区间选与锚点同父的章节/正文/步骤，跨父忽略；单次最多 100 项。
import type { FlatRow } from '@/types/node'

export const MAX_BATCH_MARK = 100

export interface SelectionUpdate {
  selection: Set<string>
  anchor: string | null
  warnings: string[]
}

/**
 * 由当前选择 + 一次勾选事件，算出新选择、新锚点与告警。
 * - shift + 有锚点：选锚点↔当前行之间、与锚点同父、非步骤的行；跨父部分忽略并告警。
 * - 否则：切换当前行的选中态，锚点移到当前行。
 * - 结果超 100：截断到最早选中的前 100（而非整段丢弃），告警；锚点若被截掉则置 null
 *   （避免锚点与可见选择错位）。crossed 与截断告警可同时返回（保持原逐条提示行为）。
 */
export function buildSelection(params: {
  current: ReadonlySet<string>
  anchor: string | null
  rows: FlatRow[]
  rowId: string
  shift: boolean
}): SelectionUpdate {
  const { current, anchor, rows, rowId, shift } = params
  const sel = new Set(current)
  let nextAnchor = anchor
  const warnings: string[] = []

  if (shift && anchor) {
    const a = rows.findIndex((r) => r.id === anchor)
    const b = rows.findIndex((r) => r.id === rowId)
    if (a >= 0 && b >= 0) {
      const [lo, hi] = a < b ? [a, b] : [b, a]
      const anchorParent = rows[a].parent_id
      let crossed = false
      for (let i = lo; i <= hi; i++) {
        const r = rows[i]
        if (r.parent_id !== anchorParent) {
          crossed = true
          continue
        }
        sel.add(r.id)
      }
      if (crossed) warnings.push('范围跨越了不同父节点，跨父部分已忽略')
    }
  } else {
    if (sel.has(rowId)) sel.delete(rowId)
    else sel.add(rowId)
    nextAnchor = rowId
  }

  if (sel.size > MAX_BATCH_MARK) {
    const trimmed = new Set([...sel].slice(0, MAX_BATCH_MARK))
    if (nextAnchor && !trimmed.has(nextAnchor)) nextAnchor = null
    warnings.push(`单次最多标记 ${MAX_BATCH_MARK} 项，已保留前 ${MAX_BATCH_MARK} 项`)
    return { selection: trimmed, anchor: nextAnchor, warnings }
  }
  return { selection: sel, anchor: nextAnchor, warnings }
}

/** 章节级联选择参数。
 * - rootId：被点击的章节 id（自身也会被加入/移除）。
 * - descendantIds：rootId 的全部后代 id（含 chapter / content / step；DFS 顺序由调用方决定）。
 * - action：select 加入；deselect 移除。半选/未选/全选的判定在调用方，这里只执行结果。
 * - 100 项上限沿用 buildSelection 的策略：按 Set 插入顺序保留前 100，告警；锚点若被截则 null。
 */
export interface CascadeParams {
  current: ReadonlySet<string>
  anchor: string | null
  rootId: string
  descendantIds: readonly string[]
  action: 'select' | 'deselect'
}

export function buildCascadeSelection(p: CascadeParams): SelectionUpdate {
  const { current, rootId, descendantIds, action } = p
  const sel = new Set(current)
  const warnings: string[] = []

  if (action === 'select') {
    sel.add(rootId)
    for (const id of descendantIds) sel.add(id)
  } else {
    sel.delete(rootId)
    for (const id of descendantIds) sel.delete(id)
  }

  let nextAnchor: string | null = rootId
  if (sel.size > MAX_BATCH_MARK) {
    const trimmed = new Set([...sel].slice(0, MAX_BATCH_MARK))
    if (!trimmed.has(nextAnchor)) nextAnchor = null
    warnings.push(`单次最多标记 ${MAX_BATCH_MARK} 项，已保留前 ${MAX_BATCH_MARK} 项`)
    return { selection: trimmed, anchor: nextAnchor, warnings }
  }
  return { selection: sel, anchor: nextAnchor, warnings }
}
