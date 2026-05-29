# E16 — Rename Detection in the Version Diff — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Follow-up to E10 (version diff) + E14 (char-diff). The last noted diff-viewer follow-up.
**Status:** Design approved; ready for implementation plan.

## Goal

Fix E10's documented caveat: a node whose first-line/title changed gets a different match signature (`code || title`), so it shows as **remove + add** instead of one **modified** row. Add a post-pass that pairs an unmatched `removed`+`added` that are clearly the same node (high body similarity + an actual field change) and reclassifies the pair as a single `modified` row — which E10/E14 already render (the char-diff shows the rename inline). Pure renumbers/moves (identical content) are deliberately **not** paired.

## Background (present today)

`versionDiff.ts`: `diffVersions(old, new)` does an LCS over `nodeSignature = code.trim() || nodeTitle(node)` → `DiffRow[]` (`unchanged`/`modified`/`added`/`removed`), with `changedFields(a,b)` listing differing persistent fields (正文/层级/类型/跳号/执行表单/附件). A title change → different signature → the node appears as a `removed` (old) row + an `added` (new) row. `charDiff.ts` (E14) has `htmlToText` + `charDiff(a,b): DiffSeg[]` (equal/del/ins). `VersionCompareDialog` renders `modified` rows with the char-diff (E14). **No dialog/host change is needed** — a merged `modified` row renders like any other.

## Components & changes

### 1. `similarity` — `frontend/src/components/version/charDiff.ts`

```ts
/** Similarity ratio in [0,1]: 2·commonChars / (|a|+|b|), where commonChars = total length of
 *  charDiff's equal segments. 1 when both empty; 0 when exactly one is empty. */
export function similarity(a: string, b: string): number {
  if (!a && !b) return 1
  if (!a || !b) return 0
  const equalLen = charDiff(a, b).reduce((sum, seg) => sum + (seg.type === 'equal' ? seg.text.length : 0), 0)
  return (2 * equalLen) / (a.length + b.length)
}
```
(`charDiff` is size-guarded, so `similarity` is too — a huge fully-different pair → 0 equal → 0.)

### 2. `detectRenames` — `frontend/src/components/version/versionDiff.ts`

```ts
import { htmlToText, similarity } from './charDiff'

const RENAME_THRESHOLD = 0.6
const MAX_RENAME_PAIRS = 2500

/** Post-pass over diff rows: pair an unmatched removed+added that are likely the same node
 *  renamed/edited — body similarity ≥ threshold AND some persistent field changed — into one
 *  `modified` row (placed at the added row's slot; the paired removed row dropped). Pure
 *  renumbers/moves (identical content → empty changedFields) are NOT paired. O(R·A), bounded. */
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
    else if (r.status === 'removed' && pairedRemoved.has(idx)) return // drop the paired removed
    else out.push(r)
  })
  return out
}
```
- `diffVersions`'s final `return rows` becomes `return detectRenames(rows)`.

## Data flow

```
diffVersions: LCS over signatures → DiffRow[] (incl. removed/added for sig-changed nodes)
  → detectRenames: for each added, find the best removed with similarity≥0.6 AND changedFields≠∅
       → emit one `modified` at the added's slot, drop the paired removed
  → VersionCompareDialog renders the `modified` row + E14 char-diff (shows the rename) — unchanged
```

## Error handling / edge cases

- **Non-empty `changedFields` guard** is the key safety: a pure renumber/move (only `code`/position changed, identical body/fields → empty `changedFields`) is **not** paired and stays `removed`+`added` — avoids turning a big renumber into a wall of empty "modified" rows.
- **Similarity threshold (0.6):** two genuinely unrelated nodes (one removed, one added) with differing fields but low body overlap stay separate.
- **Greedy + first-come:** each `removed` is paired at most once (`pairedRemoved`); `added` rows are processed in order. Acceptable for the small unmatched counts in practice.
- **Cost bound:** detection skips entirely if `removed × added > 2500`; `charDiff`/`similarity` are size-guarded for long bodies.
- Merged `modified` is placed at the `added` row's position (new-order), consistent with E10's ordering.

## Testing

- **`frontend/tests/unit/charDiff.spec.ts`** (extend): `similarity` — `('abc','abc')→1`, `('abc','xyz')→0`, `('','')→1`, `('abc','')→0`, `('目的本程序适用于公司股东','宗旨本程序适用于公司股东')` ≈ `0.833` (`toBeCloseTo(0.833, 2)`).
- **`frontend/tests/unit/versionDiff.spec.ts`** (extend): a title-renamed node (`code:''`, body `<p>目的</p><p>本程序适用于公司股东</p>` → `<p>宗旨</p>…`) → `diffVersions` returns **one `modified`** row with `changedFields:['正文']` (not remove+add); a pure renumber (`code '3.1'`/`'4.1'`, identical body) **stays `removed`+`added`** (empty changedFields → not paired); a dissimilar add+remove (changed fields but body overlap < 0.6) **stays separate**; existing diff tests green.
- **Browser smoke**: stage v1/v2 where a node's title changed but the rest of the body is the same → compare shows **one modified row** with the char-diff (not remove+add).
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Pure move/renumber detection (identical content → stays remove+add), a distinct `重命名`/`moved` status or chip (reuse `modified`; the char-diff + `正文` chip suffice), split/merge (one node → many or vice-versa) detection, optimal bipartite matching (greedy is enough), a UI-tunable threshold.
