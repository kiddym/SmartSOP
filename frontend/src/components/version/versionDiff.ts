import type { Node } from '@/types/node'
import { nodeTitle } from '@/utils/nodeTree'
import { htmlToText, similarity } from './charDiff'

export type DiffStatus = 'unchanged' | 'modified' | 'added' | 'removed'
export interface DiffRow {
  status: DiffStatus
  old: Node | null
  new: Node | null
  changedFields: string[]
}

/** Match signature: stable heading numbering when present, else first-line text. */
export function nodeSignature(n: Node): string {
  return n.code.trim() || nodeTitle(n)
}

const FIELD_LABELS: { key: 'body' | 'heading_level' | 'kind' | 'skip_numbering'; label: string }[] = [
  { key: 'body', label: '正文' },
  { key: 'heading_level', label: '层级' },
  { key: 'kind', label: '类型' },
  { key: 'skip_numbering', label: '跳号' },
]

/** Persistent fields that differ between a matched pair (human labels). */
export function changedFields(a: Node, b: Node): string[] {
  const out: string[] = []
  for (const { key, label } of FIELD_LABELS) {
    if (a[key] !== b[key]) out.push(label)
  }
  if (JSON.stringify(a.input_schema) !== JSON.stringify(b.input_schema)) out.push('执行表单')
  if (JSON.stringify(a.attachment_marks) !== JSON.stringify(b.attachment_marks)) out.push('附件')
  return out
}

const RENAME_THRESHOLD = 0.6
const MAX_RENAME_PAIRS = 2500

/** Post-pass: pair an unmatched removed+added that are the same node renamed/edited
 *  (body similarity ≥ threshold AND some persistent field changed) into one `modified` row
 *  (placed at the added slot; the paired removed dropped). Pure renumbers/moves (identical
 *  content → empty changedFields) are NOT paired. O(R·A), bounded by MAX_RENAME_PAIRS. */
export function detectRenames(rows: DiffRow[]): DiffRow[] {
  const removed = rows.map((r, i) => ({ r, i })).filter((x) => x.r.status === 'removed')
  const added = rows.map((r, i) => ({ r, i })).filter((x) => x.r.status === 'added')
  if (!removed.length || !added.length || removed.length * added.length > MAX_RENAME_PAIRS) return rows
  const pairedRemoved = new Set<number>()
  const mergeAt = new Map<number, DiffRow>()
  for (const A of added) {
    let bestIdx = -1
    let bestFields: string[] = []
    let bestSim = RENAME_THRESHOLD
    for (const R of removed) {
      if (pairedRemoved.has(R.i)) continue
      const fields = changedFields(R.r.old!, A.r.new!)
      if (!fields.length) continue // pure move/renumber → don't pair
      const sim = similarity(htmlToText(R.r.old!.body), htmlToText(A.r.new!.body))
      if (sim >= bestSim) {
        bestSim = sim
        bestIdx = R.i
        bestFields = fields
      }
    }
    if (bestIdx >= 0) {
      pairedRemoved.add(bestIdx)
      mergeAt.set(A.i, { status: 'modified', old: rows[bestIdx].old, new: A.r.new, changedFields: bestFields })
    }
  }
  if (!mergeAt.size) return rows
  const out: DiffRow[] = []
  rows.forEach((r, idx) => {
    if (mergeAt.has(idx)) out.push(mergeAt.get(idx)!)
    else if (r.status === 'removed' && pairedRemoved.has(idx)) return
    else out.push(r)
  })
  return out
}

/** Pure node-level diff: LCS over signatures of two sort_order-ordered trees.
 *  Output in new-version order; removed rows interleaved at their old position. O(n·m). */
export function diffVersions(oldNodes: Node[], newNodes: Node[]): DiffRow[] {
  const a = oldNodes
  const b = newNodes
  const sa = a.map(nodeSignature)
  const sb = b.map(nodeSignature)
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = sa[i] === sb[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (sa[i] === sb[j]) {
      const fields = changedFields(a[i], b[j])
      rows.push({ status: fields.length ? 'modified' : 'unchanged', old: a[i], new: b[j], changedFields: fields })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ status: 'removed', old: a[i], new: null, changedFields: [] })
      i++
    } else {
      rows.push({ status: 'added', old: null, new: b[j], changedFields: [] })
      j++
    }
  }
  while (i < n) {
    rows.push({ status: 'removed', old: a[i], new: null, changedFields: [] })
    i++
  }
  while (j < m) {
    rows.push({ status: 'added', old: null, new: b[j], changedFields: [] })
    j++
  }
  return detectRenames(rows)
}
