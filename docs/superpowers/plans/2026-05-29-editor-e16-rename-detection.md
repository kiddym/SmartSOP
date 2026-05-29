# E16 — Rename Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pair an unmatched removed+added that are the same node renamed/edited (body similarity ≥ 0.6 AND a real field change) into one `modified` row; pure renumbers/moves stay remove+add.

**Architecture:** `similarity` (reuses E14 `charDiff`) + a `detectRenames` post-pass in `diffVersions`. Pure; no dialog/host change. Spec: `docs/superpowers/specs/2026-05-29-editor-e16-rename-detection-design.md`.

**Tech Stack:** TypeScript, vitest. No new dependency.

---

## File Structure

- **Modify** `frontend/src/components/version/charDiff.ts` — add `similarity`.
- **Modify** `frontend/tests/unit/charDiff.spec.ts` — `similarity` tests.
- **Modify** `frontend/src/components/version/versionDiff.ts` — add `detectRenames`; call it in `diffVersions`.
- **Modify** `frontend/tests/unit/versionDiff.spec.ts` — rename-detection tests.

No `VersionCompareDialog` / host / backend change.

---

## Task 1: `similarity` in `charDiff.ts`

**Files:**
- Modify: `frontend/src/components/version/charDiff.ts`
- Test: `frontend/tests/unit/charDiff.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/charDiff.spec.ts`**

Add `similarity` to the existing `@/components/version/charDiff` import. Append:
```ts
describe('similarity', () => {
  it('identical → 1; disjoint → 0', () => {
    expect(similarity('abc', 'abc')).toBe(1)
    expect(similarity('abc', 'xyz')).toBe(0)
  })
  it('both empty → 1; one empty → 0', () => {
    expect(similarity('', '')).toBe(1)
    expect(similarity('abc', '')).toBe(0)
  })
  it('shared tail → high ratio', () => {
    expect(similarity('目的本程序适用于公司股东', '宗旨本程序适用于公司股东')).toBeCloseTo(0.833, 2)
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/charDiff.spec.ts` → FAIL (`similarity` not exported).

- [ ] **Step 3: Implement — append to `frontend/src/components/version/charDiff.ts`**

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

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/charDiff.spec.ts` → expect all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/charDiff.ts frontend/tests/unit/charDiff.spec.ts
git commit -m "feat(version): similarity ratio (via charDiff equal segments) (E16 Task 1)"
```

---

## Task 2: `detectRenames` post-pass in `versionDiff.ts`

**Files:**
- Modify: `frontend/src/components/version/versionDiff.ts`
- Test: `frontend/tests/unit/versionDiff.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/versionDiff.spec.ts`**

Add inside the `describe('diffVersions', …)` block (reuses the file's `n(over)` node factory):
```ts
  it('rename: a title change (different signature) → one modified row, not remove+add', () => {
    const old = [n({ id: 'o', code: '', body: '<p>目的</p><p>本程序适用于公司股东</p>' })]
    const neu = [n({ id: 'nn', code: '', body: '<p>宗旨</p><p>本程序适用于公司股东</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows).toHaveLength(1)
    expect(rows[0].status).toBe('modified')
    expect(rows[0].changedFields).toEqual(['正文'])
    expect(rows[0].old?.id).toBe('o')
    expect(rows[0].new?.id).toBe('nn')
  })
  it('pure renumber (identical body, code differs) stays remove+add', () => {
    const old = [n({ id: 'o', code: '3.1', body: '<p>多少分</p>' })]
    const neu = [n({ id: 'nn', code: '4.1', body: '<p>多少分</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status).sort()).toEqual(['added', 'removed'])
  })
  it('dissimilar add+remove (changed fields but low overlap) stays separate', () => {
    const old = [n({ id: 'o', code: '', body: '<p>完全旧</p>' })]
    const neu = [n({ id: 'nn', code: '', body: '<p>毫不相干新内容</p>' })]
    const rows = diffVersions(old, neu)
    expect(rows.map((r) => r.status).sort()).toEqual(['added', 'removed'])
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/versionDiff.spec.ts` → the rename test FAILS (still remove+add). The other two pass even pre-implementation (they assert remove+add, which is the current behavior) — that's fine; they lock in the guards after Step 3.

- [ ] **Step 3: Implement in `frontend/src/components/version/versionDiff.ts`**

(a) Add the import (after the existing imports at the top):
```ts
import { htmlToText, similarity } from './charDiff'
```
(b) Add the constants + `detectRenames` (after `changedFields`, before `diffVersions`):
```ts
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
```
(c) Change `diffVersions`'s final `return rows` (last line of the function) to:
```ts
  return detectRenames(rows)
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/versionDiff.spec.ts` → expect all pass (existing + 3 new). The rename test now yields one `modified`; the renumber + dissimilar tests stay remove+add (guards hold).

- [ ] **Step 5: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/version/versionDiff.ts frontend/tests/unit/versionDiff.spec.ts
git commit -m "feat(version): detectRenames post-pass folds renamed nodes into modified rows (E16 Task 2)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 2, before merge)

Stage (like E14) a code-1 node in both versions of the `a5b865ed` group where the **first line/title differs but the rest matches** — e.g. v1 body `<p>目的</p><p>本程序适用于公司创始股东</p>`, v2 `<p>宗旨</p><p>本程序适用于公司创始股东</p>`. Open the v2 detail page → `对比当前` (or `对比所选` v1+v2) → confirm it shows **one `~` modified row** (not a `−` removed + `+` added pair), and the char-diff highlights 目的→宗旨. If staging is impractical, note it — the detection is unit-tested.

---

## Self-Review

**Spec coverage:**
- `similarity` (charDiff equal-seg ratio, empty handling) → Task 1. ✓
- `detectRenames` (similarity≥0.6 AND non-empty changedFields → merge to modified at the added slot; drop paired removed; bounded) + wired into `diffVersions` → Task 2. ✓
- Pure renumber/move stays remove+add (non-empty-changedFields guard) → Task 2 test. ✓
- No dialog/host change; merged modified renders via E10/E14 → no task touches them. ✓
- Non-goals (pure move detection, distinct chip, split/merge, optimal matching, UI threshold) → untouched. ✓

**Placeholder scan:** none — full code for both functions and all tests.

**Type consistency:** `similarity(a:string,b:string):number` defined Task 1, imported Task 2. `detectRenames(rows: DiffRow[]): DiffRow[]` uses existing `DiffRow`/`changedFields`; `R.r.old!`/`A.r.new!` non-null by construction (removed rows carry `old`, added carry `new`). `diffVersions` return type unchanged (`DiffRow[]`).
