# E5 — Virtual List for the Node-Editor Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render only the rows near the viewport in `NodeTreePanel` so large procedures stay performant, add scroll-into-view for programmatically-selected nodes, and (bonus) make the `visibleRows` pipeline O(N) — without breaking E1–E4, drag-drop, or expand/collapse.

**Architecture:** A new `useVirtualRows` composable built on two pure functions (`computeWindow`, `scrollOffsetFor`) that degrade to render-all when the viewport is unmeasured (jsdom → existing tests stay green) or the list is small. `NodeTreePanel` renders `store.rows.slice(start, end)` between two height spacers and scrolls the selected node into view. Spec: `docs/superpowers/specs/2026-05-29-editor-e5-virtual-list-design.md`.

**Tech Stack:** Vue 3 `<script setup>` + composables, Pinia, Element Plus, vitest + @vue/test-utils, vue-tsc. No new runtime dependency.

---

## File Structure

- **Modify** `frontend/src/utils/nodeTree.ts` — `visibleRows` precomputes a parent-id `Set` (O(N²)→O(N)).
- **Create** `frontend/src/composables/useVirtualRows.ts` — `computeWindow` + `scrollOffsetFor` (pure) + `useVirtualRows` (DOM wiring).
- **Create** `frontend/tests/unit/composables/useVirtualRows.spec.ts` — pure-function tests.
- **Modify** `frontend/tests/unit/nodeTree.spec.ts` — one explicit `hasChildren` assertion (refactor is output-identical).
- **Modify** `frontend/src/components/editor/NodeTreePanel.vue` — windowed template + `scrollToIndex` on selection.
- **Modify** `frontend/tests/unit/NodeTreePanel.spec.ts` — virtualization + degrade tests; existing tests stay green via the height-0 degrade.

No backend, `NodeTreeRow.vue`, or E1–E4 changes.

---

## Task 1: Make `visibleRows` O(N) (parent-id set)

**Files:**
- Modify: `frontend/src/utils/nodeTree.ts:35-64` (`visibleRows`)
- Test: `frontend/tests/unit/nodeTree.spec.ts`

This is a pure refactor (output identical), so existing `nodeTree.spec` tests must stay green before and after; we add one explicit assertion.

- [ ] **Step 1: Verify the existing suite is green (baseline)**

Run: `cd frontend && npm test -- tests/unit/nodeTree.spec.ts`
Expected: PASS (records the pre-refactor baseline).

- [ ] **Step 2: Refactor `visibleRows`**

In `frontend/src/utils/nodeTree.ts`, inside `visibleRows`, add a parent-id set right after the `byId` map (line 40) and use it for the per-row child check instead of the O(N) `hasChildren` call.

Add after `const byId = new Map(...)`:
```ts
  // O(1) child check: ids that appear as some node's parent_id.
  const parentIds = new Set<string>()
  for (const x of nodes) if (x.parent_id) parentIds.add(x.parent_id)
```
Change the `rows.push(...)` line (was `hasChildren: hasChildren(nodes, node.id)`) to:
```ts
    rows.push({ node, title, hasChildren: parentIds.has(node.id), expanded: isExpanded(node.id) })
```
Leave the exported `hasChildren` function as-is (other callers may use it).

- [ ] **Step 3: Add an explicit equivalence test**

Append to `frontend/tests/unit/nodeTree.spec.ts` (use the file's existing `Node` import; build nodes inline if the file has no shared factory):
```ts
it('visibleRows: hasChildren reflects parent_id membership (O(N) parent set)', () => {
  const nodes: Node[] = [
    { id: 'p', procedure_id: 'p1', sort_order: 0, heading_level: 1, kind: 'node', body: '<p>P</p>',
      code: '', skip_numbering: false, input_schema: {}, attachment_marks: [], mark_status: 'unmarked',
      revision: 1, parent_id: null, depth: 0 },
    { id: 'c', procedure_id: 'p1', sort_order: 1000, heading_level: null, kind: 'node', body: '<p>C</p>',
      code: '', skip_numbering: false, input_schema: {}, attachment_marks: [], mark_status: 'unmarked',
      revision: 1, parent_id: 'p', depth: 1 },
  ]
  const rows = visibleRows(nodes, {}, { search: '', reviewOnly: false })
  expect(rows.map((r) => r.hasChildren)).toEqual([true, false])
})
```
(If `nodeTree.spec.ts` already imports `Node` and/or a node factory, reuse them and drop the inline literals.)

- [ ] **Step 4: Run the suite — green**

Run: `cd frontend && npm test -- tests/unit/nodeTree.spec.ts`
Expected: PASS (all prior tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/nodeTree.ts frontend/tests/unit/nodeTree.spec.ts
git commit -m "perf(editor): visibleRows uses a parent-id set (O(N^2)->O(N)) (E5 Task 1)"
```

---

## Task 2: `useVirtualRows` composable + pure windowing math

**Files:**
- Create: `frontend/src/composables/useVirtualRows.ts`
- Test: `frontend/tests/unit/composables/useVirtualRows.spec.ts`

- [ ] **Step 1: Write the failing test — CREATE `frontend/tests/unit/composables/useVirtualRows.spec.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { computeWindow, scrollOffsetFor, MIN_TO_VIRTUALIZE } from '@/composables/useVirtualRows'

describe('computeWindow', () => {
  it('renders all when the viewport is unmeasured (height 0)', () => {
    expect(computeWindow(0, 0, 500)).toEqual({ start: 0, end: 500, padTop: 0, padBottom: 0 })
  })
  it('renders all when total <= minToVirtualize', () => {
    expect(computeWindow(0, 300, MIN_TO_VIRTUALIZE)).toEqual({
      start: 0, end: MIN_TO_VIRTUALIZE, padTop: 0, padBottom: 0,
    })
  })
  it('windows the middle with overscan', () => {
    // scrollTop 600, viewport 300, total 100, rowH 30, overscan 8
    // first=20, visible=10 → start=12, end=38
    expect(computeWindow(600, 300, 100)).toEqual({ start: 12, end: 38, padTop: 360, padBottom: 1860 })
  })
  it('clamps start at 0 near the top', () => {
    const w = computeWindow(0, 300, 100)
    expect(w.start).toBe(0)
    expect(w.padTop).toBe(0)
  })
  it('clamps end at total near the bottom', () => {
    const w = computeWindow(100 * 30, 300, 100)
    expect(w.end).toBe(100)
    expect(w.padBottom).toBe(0)
  })
})

describe('scrollOffsetFor', () => {
  it('returns null when the row is already visible', () => {
    expect(scrollOffsetFor(10, 0, 600)).toBeNull() // row 10 spans [300,330) within [0,600)
  })
  it('aligns to the top when the row is above the viewport', () => {
    expect(scrollOffsetFor(2, 300, 300)).toBe(60) // top 60 < scrollTop 300
  })
  it('aligns to the bottom when the row is below the viewport', () => {
    expect(scrollOffsetFor(30, 0, 300)).toBe(630) // bottom 930 - viewport 300
  })
  it('returns null when the viewport is unmeasured', () => {
    expect(scrollOffsetFor(5, 0, 0)).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify it FAILS**

Run: `cd frontend && npm test -- tests/unit/composables/useVirtualRows.spec.ts`
Expected: FAIL — module does not exist yet.

- [ ] **Step 3: Implement `frontend/src/composables/useVirtualRows.ts`**

```ts
import { computed, onMounted, onUnmounted, ref, type ComputedRef, type Ref } from 'vue'

export const ROW_H = 30
export const OVERSCAN = 8
export const MIN_TO_VIRTUALIZE = 60

export interface RowWindow {
  start: number
  end: number
  padTop: number
  padBottom: number
}

/** Pure: which slice [start,end) of `total` fixed-height rows to render.
 *  Degrades to render-all when the viewport is unmeasured (height 0) or the list is small. */
export function computeWindow(
  scrollTop: number,
  viewportH: number,
  total: number,
  rowH = ROW_H,
  overscan = OVERSCAN,
  minToVirtualize = MIN_TO_VIRTUALIZE,
): RowWindow {
  if (viewportH <= 0 || total <= minToVirtualize) {
    return { start: 0, end: total, padTop: 0, padBottom: 0 }
  }
  const first = Math.floor(scrollTop / rowH)
  const visible = Math.ceil(viewportH / rowH)
  const start = Math.max(0, first - overscan)
  const end = Math.min(total, first + visible + overscan)
  return { start, end, padTop: start * rowH, padBottom: (total - end) * rowH }
}

/** Pure: the scrollTop needed to bring row `index` into view, or null if already visible. */
export function scrollOffsetFor(
  index: number,
  scrollTop: number,
  viewportH: number,
  rowH = ROW_H,
): number | null {
  if (index < 0 || viewportH <= 0) return null
  const top = index * rowH
  const bottom = top + rowH
  if (top < scrollTop) return top
  if (bottom > scrollTop + viewportH) return bottom - viewportH
  return null
}

export function useVirtualRows(
  containerRef: Ref<HTMLElement | null>,
  total: () => number,
): {
  start: ComputedRef<number>
  end: ComputedRef<number>
  padTop: ComputedRef<number>
  padBottom: ComputedRef<number>
  totalHeight: ComputedRef<number>
  scrollToIndex: (index: number) => void
} {
  const scrollTop = ref(0)
  const viewportH = ref(0)

  const measure = (): void => {
    const el = containerRef.value
    if (!el) return
    scrollTop.value = el.scrollTop
    viewportH.value = el.clientHeight
  }

  const win = computed(() => computeWindow(scrollTop.value, viewportH.value, total()))
  const start = computed(() => win.value.start)
  const end = computed(() => win.value.end)
  const padTop = computed(() => win.value.padTop)
  const padBottom = computed(() => win.value.padBottom)
  const totalHeight = computed(() => total() * ROW_H)

  function scrollToIndex(index: number): void {
    const el = containerRef.value
    if (!el) return
    const next = scrollOffsetFor(index, scrollTop.value, viewportH.value)
    if (next != null) {
      el.scrollTop = next
      scrollTop.value = next // jsdom won't fire scroll on programmatic set; keep state in sync
    }
  }

  let ro: ResizeObserver | null = null
  onMounted(() => {
    const el = containerRef.value
    if (!el) return
    measure()
    el.addEventListener('scroll', measure, { passive: true })
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => { viewportH.value = el.clientHeight })
      ro.observe(el)
    }
  })
  onUnmounted(() => {
    const el = containerRef.value
    if (el) el.removeEventListener('scroll', measure)
    ro?.disconnect()
    ro = null
  })

  return { start, end, padTop, padBottom, totalHeight, scrollToIndex }
}
```

(The `measure` handler re-reads `clientHeight` on every scroll, so resize-without-scroll is the only case relying on `ResizeObserver`; the `typeof` guard keeps the composable safe in jsdom where `ResizeObserver` may be absent.)

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/composables/useVirtualRows.spec.ts`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useVirtualRows.ts frontend/tests/unit/composables/useVirtualRows.spec.ts
git commit -m "feat(editor): useVirtualRows composable + pure window/scroll math (E5 Task 2)"
```

---

## Task 3: Wire windowing + scroll-into-view into `NodeTreePanel`

**Files:**
- Modify: `frontend/src/components/editor/NodeTreePanel.vue` (`<script setup>` imports + the `.np-rows` template block)
- Test: `frontend/tests/unit/NodeTreePanel.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/NodeTreePanel.spec.ts`**

Add this describe block at the end of the file (it reuses the existing `n` and `setup` helpers):
```ts
describe('NodeTreePanel — virtualization', () => {
  function many(count: number) {
    return Array.from({ length: count }, (_, i) =>
      n({ id: `r${i}`, sort_order: i * 1000, body: `<p>${i}</p>` }),
    )
  }

  it('renders only the windowed rows once the viewport is measured', async () => {
    const { w } = setup(many(100))
    const el = w.find('.np-rows').element as HTMLElement
    Object.defineProperty(el, 'clientHeight', { configurable: true, value: 300 })
    Object.defineProperty(el, 'scrollTop', { configurable: true, writable: true, value: 600 })
    await w.find('.np-rows').trigger('scroll')
    await w.vm.$nextTick()
    // first=20, visible=10, overscan 8 → start 12, end 38 → 26 rows
    expect(w.findAllComponents({ name: 'NodeTreeRow' }).length).toBe(26)
  })

  it('degrades to render-all when the viewport is unmeasured (jsdom height 0)', () => {
    const { w } = setup(many(80))
    expect(w.findAllComponents({ name: 'NodeTreeRow' }).length).toBe(80)
  })
})
```

- [ ] **Step 2: Run to verify the windowing test FAILS**

Run: `cd frontend && npm test -- tests/unit/NodeTreePanel.spec.ts`
Expected: the "renders only the windowed rows" test FAILS (still renders all 100); the degrade test passes by luck (no windowing yet). Existing tests still pass.

- [ ] **Step 3: Update the `<script setup>` of `NodeTreePanel.vue`**

Change the Vue import (line 2) to add `watch` + `nextTick`:
```ts
import { computed, ref, watch, nextTick } from 'vue'
```
Add the composable import near the other `@/` imports (after line 9):
```ts
import { useVirtualRows } from '@/composables/useVirtualRows'
```
After `const states = computed(...)` (line 20), add the virtual-rows wiring + scroll-into-view:
```ts
const rowsEl = ref<HTMLElement | null>(null)
const { start, end, padTop, padBottom, totalHeight, scrollToIndex } = useVirtualRows(
  rowsEl,
  () => store.rows.length,
)

// Programmatic selection (create / undo / keyboard) may target an off-window row → scroll it in.
watch(
  () => store.selectedId,
  (id) => {
    if (!id) return
    const i = store.rows.findIndex((r) => r.node.id === id)
    if (i >= 0) void nextTick(() => scrollToIndex(i))
  },
)
```

- [ ] **Step 4: Update the `.np-rows` template block**

Replace the current `.np-rows` block (lines 151-173) with the windowed version — bind the `ref`, wrap rows in a `totalHeight` sizer with `padTop`/`padBottom` spacers, and slice the rows. **Every `NodeTreeRow` prop/handler stays identical**; only `v-for` source and the wrapper change:
```html
    <div class="np-rows" ref="rowsEl">
      <div class="np-sizer" :style="{ height: totalHeight + 'px' }">
        <div class="np-spacer" :style="{ height: padTop + 'px' }" />
        <NodeTreeRow
          v-for="row in store.rows.slice(start, end)"
          :key="row.node.id"
          :row="row"
          :readonly="props.readonly"
          :selected="store.selectedId === row.node.id"
          :selected-for-mark="states.get(row.node.id) === 'checked'"
          :indeterminate="states.get(row.node.id) === 'indeterminate'"
          :drop-hint="hintFor(row)"
          @select="onSelect(row.node.id)"
          @toggle="store.toggleExpand(row.node.id)"
          @check="(shift: boolean) => onCheck(row.node.id, shift)"
          @chip="(c: string) => onChip(row.node.id, c)"
          @remove="store.removeNode(row.node.id)"
          @indent="(dir: 'in' | 'out') => onIndent(row.node.id, dir)"
          @dragstart="onDragStart(row.node.id)"
          @dragover="(ev: DragEvent) => onDragOver(row.node.id, ev)"
          @drop="onDrop(row.node.id)"
          @dragend="onDragEnd"
        />
        <div class="np-spacer" :style="{ height: padBottom + 'px' }" />
      </div>
      <el-empty v-if="!store.rows.length" description="暂无节点" />
    </div>
```
(No CSS changes: `.np-sizer`/`.np-spacer` are plain block divs; `.np-rows` keeps `overflow-y: auto`. The spacers + sliced rows sum to `totalHeight`, so the scrollbar is correct.)

- [ ] **Step 5: Run the panel suite — all green**

Run: `cd frontend && npm test -- tests/unit/NodeTreePanel.spec.ts`
Expected: PASS — the windowing test now sees 26 rows; the degrade test sees 80; every pre-existing test (row count = 2, chip/remove/select, drag reorder, cascade, indent, readonly, barStep) stays green because jsdom's height-0 degrade renders all rows for those small fixtures.

- [ ] **Step 6: Full suite + type check — all green**

Run: `cd frontend && npm test`
Then: `cd frontend && npm run typecheck`
Expected: 0 test failures; vue-tsc reports no errors. (Confirm count rose by the new tests — don't fixate on the exact number; require 0 failures.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/editor/NodeTreePanel.vue frontend/tests/unit/NodeTreePanel.spec.ts
git commit -m "feat(editor): windowed NodeTreePanel rows + scroll-selected-into-view (E5 Task 3)"
```

---

## Self-Review

**Spec coverage:**
- Bespoke fixed-height windowing via pure `computeWindow` → Task 2. ✓
- Degrade-to-render-all (height 0 / `≤ MIN_TO_VIRTUALIZE`) → `computeWindow` + Task 3 degrade test + existing tests staying green. ✓
- `scrollOffsetFor` + `scrollToIndex` + `watch(selectedId)` with `i >= 0` guard → Task 2 + Task 3. ✓
- Spacers + `totalHeight` sizer; row markup unchanged; DnD via full `store.nodes` → Task 3 Step 4. ✓
- `ROW_H=30`, `OVERSCAN=8`, `MIN_TO_VIRTUALIZE=60` → Task 2 constants. ✓
- Bonus O(N) `visibleRows` → Task 1. ✓
- Non-goals (variable heights, custom drag auto-scroll, arrow-key nav, no backend/row/E1–E4 change) → no task touches them. ✓

**Placeholder scan:** none — every code step has complete code. The only conditional is "reuse `nodeTree.spec`'s existing node factory if present" with a self-contained fallback literal provided.

**Type consistency:** `useVirtualRows` returns `ComputedRef<number>` for `start`/`end`/`padTop`/`padBottom`/`totalHeight` (all `computed`) and `scrollToIndex(index: number): void`; `NodeTreePanel` destructures exactly those names. `RowWindow`/`computeWindow`/`scrollOffsetFor` signatures match between Task 2 definition and the tests. `rowsEl: Ref<HTMLElement | null>` matches the composable's `containerRef` param.

**Browser verification (orchestrator, post-merge, best-effort):** load a large procedure, confirm DOM `NodeTreeRow` count ≪ total, smooth scroll, create/undo scrolls the selection into view, and drag-drop / checkbox / Tab-indent still work. Skip only if staging a large procedure is impractical (note it).
