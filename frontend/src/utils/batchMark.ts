// 标记模式批量选择的纯逻辑（从 ChapterTreePanel 抽出，便于单测）。
// shift 区间选与锚点同父的行，跨父忽略；单次最多 100 项。
// 结构型行：只需 id / 父 / kind（kind 用 string，统一节点模型下为 'node'|'step'）。
export interface SelectableRow {
  id: string
  parent_id: string | null
  kind: string
}

export const MAX_BATCH_MARK = 100

export interface SelectionUpdate {
  selection: Set<string>
  anchor: string | null
  warnings: string[]
}

/**
 * 由当前选择 + 一次勾选事件，算出新选择、新锚点与告警。
 * - shift + 有锚点：选锚点↔当前行之间、与锚点同父的行；跨父部分忽略并告警。
 * - 否则：切换当前行的选中态，锚点移到当前行。
 * - 结果超 100：截断到最早选中的前 100（而非整段丢弃），告警；锚点若被截掉则置 null
 *   （避免锚点与可见选择错位）。crossed 与截断告警可同时返回（保持原逐条提示行为）。
 */
export function buildSelection(params: {
  current: ReadonlySet<string>
  anchor: string | null
  rows: readonly SelectableRow[]
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

/** 级联选择：把 ids（调用方已含 root）整批加入/移除；anchor 恒为 rootId；沿用 100 上限。 */
export interface CascadeParams {
  current: ReadonlySet<string>
  rootId: string // 仅作 anchor
  ids: readonly string[] // 要选/取消的节点（调用方决定是否含 root）
  action: 'select' | 'deselect'
}

export function buildCascadeSelection(p: CascadeParams): SelectionUpdate {
  const { current, rootId, ids, action } = p
  const sel = new Set(current)
  const warnings: string[] = []
  if (action === 'select') for (const id of ids) sel.add(id)
  else for (const id of ids) sel.delete(id)
  if (sel.size > MAX_BATCH_MARK) {
    const trimmed = new Set([...sel].slice(0, MAX_BATCH_MARK))
    warnings.push(`单次最多标记 ${MAX_BATCH_MARK} 项，已保留前 ${MAX_BATCH_MARK} 项`)
    return { selection: trimmed, anchor: rootId, warnings }
  }
  return { selection: sel, anchor: rootId, warnings }
}
