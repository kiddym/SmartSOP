# Resizable Import Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three columns of the Word-import dialog (`ImportDialog.vue`) drag-to-resize, with widths persisted across sessions.

**Architecture:** Two draggable splitter handles sit between the columns. Column widths become reactive percentages (`{ left, mid }`, right derived) driven by inline styles. All resize/clamp math lives in a pure, unit-tested util module (`utils/importCols.ts`); the component only wires pointer events and persistence (`@vueuse/core` `useStorage`). No new dependencies.

**Tech Stack:** Vue 3 `<script setup>` + TypeScript, `@vueuse/core` (`useStorage`, `useEventListener`), Element Plus theme vars, Vitest.

**Spec:** `docs/superpowers/specs/2026-05-24-resizable-import-columns-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `frontend/src/utils/importCols.ts` | **New.** Pure functions: defaults/min constants, `rightOf`, `resizeLeftMid`, `resizeMidRight`, `sanitizeCols`. No Vue/DOM deps. |
| `frontend/tests/unit/utils/importCols.spec.ts` | **New.** Vitest unit tests for the pure functions. |
| `frontend/src/components/import-v2/ImportDialog.vue` | **Modify.** Replace static column widths with reactive state + two splitters + drag/persist/reset logic + styles. |

Subcomponents (`WordPreviewPanel`, `ImportTreePanel`, `ImportDetailPanel`, `ImportTreeRow`) are **not** touched. No backend changes.

---

## Pre-flight: commit the existing precursor changes

The working tree already has two uncommitted, user-approved changes from the previous step: the static column rebalance (38/28/34) and the `tr-title` flex fix. Commit them first so this feature builds on a clean tree. (Task 2 will later replace the static width rules with reactive bindings — committing now keeps that diff readable.)

- [ ] **Step 1: Verify the only uncommitted changes are the two expected files**

Run: `cd frontend && git status --short`
Expected: exactly
```
 M src/components/import-v2/ImportDialog.vue
 M src/components/import-v2/ImportTreeRow.vue
```
If anything else appears, stop and reconcile before continuing.

- [ ] **Step 2: Commit the precursor**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/components/import-v2/ImportDialog.vue \
        frontend/src/components/import-v2/ImportTreeRow.vue
git commit -m "$(cat <<'EOF'
style(import): rebalance columns to 38/28/34 and fix tree-row title growth

Give the Word-preview column more room; let mid-column titles use width
before truncating instead of reserving 50% as dead whitespace.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: Pure column-math util (`utils/importCols.ts`)

**Files:**
- Create: `frontend/src/utils/importCols.ts`
- Test: `frontend/tests/unit/utils/importCols.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/utils/importCols.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  COL_DEFAULTS,
  COL_MIN,
  rightOf,
  resizeLeftMid,
  resizeMidRight,
  sanitizeCols,
} from '@/utils/importCols'

describe('importCols', () => {
  it('rightOf derives the remaining width', () => {
    expect(rightOf({ left: 38, mid: 28 })).toBe(34)
  })

  describe('resizeLeftMid (drag the left|mid handle)', () => {
    it('grows left and shrinks mid by the same delta; right unchanged', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, 10)
      expect(r).toEqual({ left: 48, mid: 18 })
      expect(rightOf(r)).toBe(34)
    })

    it('shrinks left and grows mid on negative delta', () => {
      expect(resizeLeftMid({ left: 38, mid: 28 }, -10)).toEqual({ left: 28, mid: 38 })
    })

    it('clamps left to COL_MIN, never starving mid below COL_MIN', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, -100)
      expect(r.left).toBe(COL_MIN)
      expect(r.mid).toBe(38 + 28 - COL_MIN)
    })

    it('clamps mid to COL_MIN when left grows too much', () => {
      const r = resizeLeftMid({ left: 38, mid: 28 }, 100)
      expect(r.mid).toBe(COL_MIN)
      expect(r.left).toBe(38 + 28 - COL_MIN)
    })
  })

  describe('resizeMidRight (drag the mid|right handle)', () => {
    it('grows mid and shrinks right; left unchanged', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, 10)
      expect(r).toEqual({ left: 38, mid: 38 })
      expect(rightOf(r)).toBe(24)
    })

    it('clamps mid to COL_MIN on large negative delta', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, -100)
      expect(r).toEqual({ left: 38, mid: COL_MIN })
    })

    it('clamps right to COL_MIN when mid grows too much', () => {
      const r = resizeMidRight({ left: 38, mid: 28 }, 100)
      expect(rightOf(r)).toBe(COL_MIN)
      expect(r.mid).toBe(100 - 38 - COL_MIN)
    })
  })

  describe('sanitizeCols (guards persisted/dirty values)', () => {
    it('passes through a valid value', () => {
      expect(sanitizeCols({ left: 40, mid: 25 })).toEqual({ left: 40, mid: 25 })
    })

    it('falls back to defaults when a column is below COL_MIN', () => {
      expect(sanitizeCols({ left: 10, mid: 28 })).toEqual(COL_DEFAULTS)
    })

    it('falls back when left+mid leaves right below COL_MIN', () => {
      expect(sanitizeCols({ left: 60, mid: 30 })).toEqual(COL_DEFAULTS)
    })

    it('falls back on malformed input', () => {
      expect(sanitizeCols(null)).toEqual(COL_DEFAULTS)
      expect(sanitizeCols({ left: 'x' })).toEqual(COL_DEFAULTS)
    })
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/utils/importCols.spec.ts`
Expected: FAIL — cannot resolve module `@/utils/importCols` (file does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `frontend/src/utils/importCols.ts`:

```ts
/** Column widths as percentages of the 3-column import layout. `right` is derived. */
export interface ColWidths {
  left: number
  mid: number
}

/** Default split: left 38% / mid 28% / right 34%. */
export const COL_DEFAULTS: ColWidths = { left: 38, mid: 28 }

/** Minimum width any single column may occupy, in percent. */
export const COL_MIN = 18

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi)
}

/** Derived right-column width. */
export function rightOf(c: ColWidths): number {
  return 100 - c.left - c.mid
}

/**
 * Drag the left|mid boundary by `deltaPct` (percent of container width).
 * Left grows, mid shrinks by the same amount; right is untouched.
 * Both left and mid stay >= COL_MIN.
 */
export function resizeLeftMid(start: ColWidths, deltaPct: number): ColWidths {
  const pair = start.left + start.mid
  const left = clamp(start.left + deltaPct, COL_MIN, pair - COL_MIN)
  return { left, mid: pair - left }
}

/**
 * Drag the mid|right boundary by `deltaPct`.
 * Mid grows, right shrinks; left is untouched.
 * Both mid and right stay >= COL_MIN.
 */
export function resizeMidRight(start: ColWidths, deltaPct: number): ColWidths {
  const maxMid = 100 - start.left - COL_MIN
  const mid = clamp(start.mid + deltaPct, COL_MIN, maxMid)
  return { left: start.left, mid }
}

/** Validate a persisted value; fall back to defaults if missing/dirty/out-of-bounds. */
export function sanitizeCols(v: unknown): ColWidths {
  if (
    typeof v === 'object' &&
    v !== null &&
    typeof (v as ColWidths).left === 'number' &&
    typeof (v as ColWidths).mid === 'number'
  ) {
    const { left, mid } = v as ColWidths
    if (left >= COL_MIN && mid >= COL_MIN && left + mid <= 100 - COL_MIN) {
      return { left, mid }
    }
  }
  return { ...COL_DEFAULTS }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/utils/importCols.spec.ts`
Expected: PASS — all assertions green.

- [ ] **Step 5: Lint & typecheck the new files**

Run: `cd frontend && npx eslint src/utils/importCols.ts tests/unit/utils/importCols.spec.ts --max-warnings 0 && npx vue-tsc --noEmit`
Expected: no output / exit 0.

- [ ] **Step 6: Commit**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/utils/importCols.ts frontend/tests/unit/utils/importCols.spec.ts
git commit -m "$(cat <<'EOF'
feat(import): add pure column-resize math util

resizeLeftMid / resizeMidRight / sanitizeCols with 18% min-width clamp,
backing the upcoming draggable import-dialog splitters.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire splitters into `ImportDialog.vue`

**Files:**
- Modify: `frontend/src/components/import-v2/ImportDialog.vue` (script `<script setup>`, the `.cols` block in `<template>`, and `<style scoped>`)

This task has no unit test: the drag behaviour depends on real layout (`getBoundingClientRect`), which jsdom does not compute. The math is already covered by Task 1; this task is verified by typecheck + lint + build + manual browser check.

- [ ] **Step 1: Add imports and resize state to `<script setup>`**

In `frontend/src/components/import-v2/ImportDialog.vue`, the existing imports start with `import { computed, onMounted, ref, watch } from 'vue'`. Add the two `@vueuse/core` imports and the util import directly below the existing import block (after the line `import { collectLeafFolders } from '@/utils/folders'`):

```ts
import { useStorage, useEventListener } from '@vueuse/core'
import {
  COL_DEFAULTS,
  resizeLeftMid,
  resizeMidRight,
  rightOf,
  sanitizeCols,
  type ColWidths,
} from '@/utils/importCols'
```

Then add the resize state and handlers. Place this block immediately after the existing `const visible = computed(...)` definition (before `onMounted`):

```ts
const colsRef = ref<HTMLDivElement | null>(null)
const cols = useStorage<ColWidths>('smartsop.import.cols', { ...COL_DEFAULTS })
// Guard against dirty/legacy persisted values on load.
cols.value = sanitizeCols(cols.value)

const rightPct = computed(() => rightOf(cols.value))

type Handle = 'lm' | 'mr'
const drag = ref<{ handle: Handle; startX: number; start: ColWidths; containerW: number } | null>(null)

function onDragStart(e: PointerEvent, handle: Handle): void {
  if (!colsRef.value) return
  e.preventDefault()
  drag.value = {
    handle,
    startX: e.clientX,
    start: { ...cols.value },
    containerW: colsRef.value.getBoundingClientRect().width,
  }
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
}

function endDrag(): void {
  if (!drag.value) return
  drag.value = null
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

function resetCols(): void {
  cols.value = { ...COL_DEFAULTS }
}

useEventListener(window, 'pointermove', (e: PointerEvent) => {
  const d = drag.value
  if (!d || d.containerW === 0) return
  const deltaPct = ((e.clientX - d.startX) / d.containerW) * 100
  cols.value = d.handle === 'lm' ? resizeLeftMid(d.start, deltaPct) : resizeMidRight(d.start, deltaPct)
})

useEventListener(window, 'pointerup', endDrag)
```

- [ ] **Step 2: Replace the `.cols` block in `<template>`**

Find this existing block:

```html
      <div v-else class="cols">
        <div class="col left"><WordPreviewPanel :file="ctx.file.value" /></div>
        <div class="col mid"><ImportTreePanel :ctx="ctx" /></div>
        <div class="col right"><ImportDetailPanel :ctx="ctx" /></div>
      </div>
```

Replace it with:

```html
      <div v-else ref="colsRef" class="cols">
        <div class="col" :style="{ width: cols.left + '%' }"><WordPreviewPanel :file="ctx.file.value" /></div>
        <div
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'lm')"
          @dblclick="resetCols"
        />
        <div class="col" :style="{ width: cols.mid + '%' }"><ImportTreePanel :ctx="ctx" /></div>
        <div
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'mr')"
          @dblclick="resetCols"
        />
        <div class="col" :style="{ width: rightPct + '%' }"><ImportDetailPanel :ctx="ctx" /></div>
      </div>
```

- [ ] **Step 3: Update `<style scoped>` — drop static widths, add splitter**

Find these three rules at the bottom of the `<style scoped>` block:

```css
.col.left { width: 38%; }
.col.mid { width: 28%; }
.col.right { width: 34%; }
```

Replace them with the splitter styling (widths now come from inline `:style`):

```css
.splitter {
  flex: none;
  width: 6px;
  cursor: col-resize;
  position: relative;
  z-index: 1;
  touch-action: none;
}
.splitter::after {
  content: '';
  position: absolute;
  inset: 0 2px;
  background: transparent;
  transition: background 0.15s;
}
.splitter:hover::after { background: var(--el-color-primary, #d97757); }
```

(The `.col { ... min-width: 0; }` rule already exists and lets columns flex-shrink to absorb the two 6px splitters; leave it as-is. The resting divider lines come from the panels' own `border-right`, so the splitter is transparent until hovered.)

- [ ] **Step 4: Typecheck, lint, build**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/import-v2/ImportDialog.vue --max-warnings 0 && npm run build`
Expected: typecheck clean, lint clean, `vite build` succeeds.

- [ ] **Step 5: Manual verification in the browser**

The dev server is already running at <http://localhost:5173>. Open the procedure library, launch **从 Word 导入**, upload a `.docx` (e.g. one under `_pdf_extract/`), and on the three-column view confirm:
- Hovering between columns shows a terracotta vertical line and `col-resize` cursor.
- Dragging the left|mid handle widens the left column and narrows the middle; the right column stays put.
- Dragging the mid|right handle widens the middle and narrows the right; the left column stays put.
- Neither drag lets any column shrink past ~18%.
- Double-clicking a handle snaps back to 38/28/34.
- Reloading the page (F5) and reopening the dialog preserves the last-dragged widths (check `localStorage['smartsop.import.cols']` in devtools).

- [ ] **Step 6: Commit**

```bash
cd "/Users/yuming/Desktop/claude projects/HP_smart sop/SmartSOP"
git add frontend/src/components/import-v2/ImportDialog.vue
git commit -m "$(cat <<'EOF'
feat(import): drag-to-resize the 3 import-dialog columns

Two splitter handles between the columns drive reactive percentage
widths, persisted across sessions via useStorage; 18% min per column,
double-click a handle to reset to 38/28/34.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Run the full frontend gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build && npm run test`
Expected: all four green.

- [ ] **Confirm clean tree**

Run: `git status --short`
Expected: empty (everything committed).
