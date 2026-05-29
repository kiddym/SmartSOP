# E12 — PDF Preview Jump-to-Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn E7's read-only `n / N` page indicator into an editable page input → jump (clamped) via the existing `goPage`.

**Architecture:** Pure `clampPageInput` in `pdfChrome.ts`; the indicator becomes a one-way-bound `<input>` whose commit calls `goPage`. Spec: `docs/superpowers/specs/2026-05-29-editor-e12-pdf-jump-to-page-design.md`.

**Tech Stack:** Vue 3, vitest, vue-tsc. No new dependency.

---

## File Structure

- **Modify** `frontend/src/components/PdfPreview/pdfChrome.ts` — add `clampPageInput`.
- **Modify** `frontend/tests/unit/pdfChrome.spec.ts` — `clampPageInput` tests.
- **Modify** `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` — editable page input + `onPageInput`.

No backend change. The dialog wiring is browser-verified (no jsdom layout); the pure helper is unit-tested.

---

## Task 1: `clampPageInput` + editable page indicator

**Files:**
- Modify: `frontend/src/components/PdfPreview/pdfChrome.ts`, `frontend/src/components/PdfPreview/PdfPreviewDialog.vue`
- Test: `frontend/tests/unit/pdfChrome.spec.ts`

- [ ] **Step 1: Write the failing test — `frontend/tests/unit/pdfChrome.spec.ts`**

Add `clampPageInput` to the existing import line (currently `import { clampZoom, stepZoom, fitZoom, activePageIndex, ZOOM_MIN, ZOOM_MAX } from '@/components/PdfPreview/pdfChrome'`). Append:
```ts
describe('clampPageInput', () => {
  it('parses a 1-based page to a clamped 0-based index', () => {
    expect(clampPageInput('3', 12)).toBe(2)
    expect(clampPageInput(3, 12)).toBe(2)
  })
  it('clamps out-of-range to first/last', () => {
    expect(clampPageInput('0', 12)).toBe(0)
    expect(clampPageInput('99', 12)).toBe(11)
    expect(clampPageInput('-4', 12)).toBe(0)
  })
  it('null for non-numeric, empty, or no pages', () => {
    expect(clampPageInput('abc', 12)).toBeNull()
    expect(clampPageInput('', 12)).toBeNull()
    expect(clampPageInput('5', 0)).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts`
Expected: FAIL — `clampPageInput` not exported.

- [ ] **Step 3: Implement — append to `frontend/src/components/PdfPreview/pdfChrome.ts`**

```ts
/** Parse a 1-based page input to a clamped 0-based index, or null if not a positive integer
 *  (or no pages). e.g. ('3', 12) → 2 ; ('0', 12) → 0 ; ('99', 12) → 11 ; ('abc', 12) → null. */
export function clampPageInput(raw: string | number, count: number): number | null {
  const num = typeof raw === 'number' ? raw : parseInt(String(raw).trim(), 10)
  if (!Number.isInteger(num) || count <= 0) return null
  return Math.min(count - 1, Math.max(0, num - 1))
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts` → expect all pass (existing + new).

- [ ] **Step 5: Wire the input into `PdfPreviewDialog.vue`**

(a) Add `clampPageInput` to the existing `./pdfChrome` import (line 17):
```ts
import { stepZoom, fitZoom, activePageIndex, clampPageInput, ZOOM_MIN, ZOOM_MAX } from './pdfChrome'
```
(b) Add the handler after `nextPage` (~line 75):
```ts
function onPageInput(e: Event): void {
  const el = e.target as HTMLInputElement
  const i = clampPageInput(el.value, pageCount.value)
  if (i !== null) goPage(i)
  el.value = String(currentPage.value + 1) // re-sync after a jump or an invalid entry
}
```
(c) Replace the indicator span (line 172) `<span class="pv-pageind">{{ currentPage + 1 }} / {{ pageCount }}</span>` with:
```html
            <input
              class="pv-pageind pv-pageinput"
              type="text"
              inputmode="numeric"
              :value="currentPage + 1"
              aria-label="跳转到页"
              @change="onPageInput"
              @keyup.enter="onPageInput"
            />
            <span class="pv-pagetotal">/ {{ pageCount }}</span>
```
(d) Add styles in `<style scoped>` (near the existing `.pv-pageind` rule ~line 358):
```css
.pv-pageinput {
  width: 34px;
  text-align: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 12px;
  padding: 1px 2px;
}
.pv-pagetotal {
  font-size: 12px;
  color: #909399;
}
```
(If the existing `.pv-pageind` rule sets a fixed width / no border that fights the input, the `.pv-pageinput` class wins via specificity since both classes are on the element; leave `.pv-pageind` as-is.)

- [ ] **Step 6: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PdfPreview/pdfChrome.ts frontend/tests/unit/pdfChrome.spec.ts frontend/src/components/PdfPreview/PdfPreviewDialog.vue
git commit -m "feat(pdf): jump-to-page editable indicator in PdfPreviewDialog (E12)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 1, before merge)

Launch the worktree dev servers (bootstrap backend), open a procedure editor (multi-page proc, e.g. 37-node `356e353c…`) → `PDF 预览`. Then:
1. Type `5` in the page input + Enter → the preview scrolls to page 5 and the indicator shows `5`.
2. An out-of-range entry (e.g. `99`) clamps to the last page; `0`/non-numeric → no-op (display resets).
3. Scrolling still updates the number live (E7 behavior intact).
4. Sanity: zoom +/−/适应 and prev/next still work.

---

## Self-Review

**Spec coverage:**
- Pure `clampPageInput` (parse → clamped 0-based / null) → Step 1-3. ✓
- Editable input one-way-bound to `currentPage + 1`, commit → `goPage`, re-sync on invalid → Step 5(b-c). ✓
- Inside the `.no-print` `.pv-pagenav` toolbar; reuses E7 `goPage`/`pageCount`/`currentPage` → Step 5. ✓
- Non-goals (thumbnails, PageUp/Down, el-input-number) → untouched. ✓

**Placeholder scan:** none — full code for the helper, the handler, the template, and the styles.

**Type consistency:** `clampPageInput(raw: string | number, count: number): number | null` defined in Step 3, imported + used (`el.value` is a string; `pageCount.value` a number) in Step 5; tests pass both a string and a number. `goPage`/`currentPage`/`pageCount` already exist (E7).
