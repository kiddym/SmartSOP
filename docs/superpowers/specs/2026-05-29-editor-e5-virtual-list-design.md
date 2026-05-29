# E5 — Virtual List for the Node-Editor Tree — Design

**Date:** 2026-05-29
**Track:** Post-migration node-editor enhancements (follows E1 undo/redo, E2 cascading multi-select, E3 Tab indent, E4 409 conflict recovery).
**Status:** Design approved; ready for implementation plan.

## Goal

Keep the node-editor tree (`NodeTreePanel`) performant for large procedures (hundreds–thousands of nodes) by rendering only the rows near the viewport, without breaking E1 undo/redo, E2 cascading multi-select, E3 keyboard Tab indent, drag-and-drop reorder, or expand/collapse. Also add scroll-into-view so a programmatically-selected node (just-created / undone / keyboard-navigated) is always shown.

## Background (current rendering)

- `NodeTreePanel.vue` renders a **flat list** `store.rows` (a `TreeRow[]` from the `rows` getter → `visibleRows()`), one `NodeTreeRow` per visible node, inside a single scroll container `.np-rows` (`flex:1; overflow-y:auto; min-height:0`).
- **Every row is a fixed 30px** (`NodeTreeRow` CSS `.ntr { height: 30px }`), indented by `paddingLeft: depth*16+6`. Fixed height makes windowing trivial.
- Drag-drop is **native HTML5** (`dragstart`/`dragover`/`drop` on each row; `computeReorder(store.nodes, …)` in `nodeTreeDnd.ts` operates on the **full** nodes array, not the DOM).
- There is **no `.focus()` / `scrollIntoView` anywhere** today; selecting an off-screen node does not scroll to it (a latent gap windowing would worsen).
- `NodeTreePanel.spec.ts` asserts all visible rows are mounted (`findAllComponents(NodeTreeRow)` count). jsdom has **no layout** (`clientHeight === 0`).
- No virtualization library is installed.

## Approach (chosen: bespoke fixed-height windowing)

- **A — bespoke fixed-height window. ✅ chosen.** Rows are a fixed 30px, so windowing is simple arithmetic; no new dependency; full control over the jsdom test-degrade and DnD edge behavior. The core math is a pure function (testable without layout).
- **B — `@tanstack/vue-virtual`.** Battle-tested but built for variable heights we don't have; adds a runtime dep + API surface and we'd still hand-write the jsdom-degrade + DnD glue. Rejected (overkill).
- **C — Element Plus virtualized list/table.** Table/slot-oriented; would force rewriting the custom `NodeTreeRow` (checkbox, chips, drag, drop-hints) into a slot API. Rejected (heavy rewrite, poor fit).

## Components & changes

### 1. New composable — `frontend/src/composables/useVirtualRows.ts`

Two **pure exported functions** (unit-testable, no DOM):

```ts
export const ROW_H = 30
export const OVERSCAN = 8
export const MIN_TO_VIRTUALIZE = 60

export interface Window { start: number; end: number; padTop: number; padBottom: number }

// Degrades to render-all when the viewport is unmeasured (height 0) or the list is small.
export function computeWindow(
  scrollTop: number, viewportH: number, total: number,
  rowH = ROW_H, overscan = OVERSCAN, minToVirtualize = MIN_TO_VIRTUALIZE,
): Window {
  if (viewportH <= 0 || total <= minToVirtualize) {
    return { start: 0, end: total, padTop: 0, padBottom: 0 }
  }
  const first = Math.floor(scrollTop / rowH)
  const visible = Math.ceil(viewportH / rowH)
  const start = Math.max(0, first - overscan)
  const end = Math.min(total, first + visible + overscan)
  return { start, end, padTop: start * rowH, padBottom: (total - end) * rowH }
}

// Returns the scrollTop needed to bring `index` into view, or null if already visible.
export function scrollOffsetFor(
  index: number, scrollTop: number, viewportH: number, total: number, rowH = ROW_H,
): number | null {
  if (index < 0 || viewportH <= 0) return null
  const top = index * rowH
  const bottom = top + rowH
  if (top < scrollTop) return top                              // above viewport → align to top
  if (bottom > scrollTop + viewportH) return bottom - viewportH // below → align to bottom
  return null                                                  // already visible
}
```

The composable wires DOM to the pure functions:

```ts
export function useVirtualRows(
  containerRef: Ref<HTMLElement | null>,
  total: () => number,
): {
  start: ComputedRef<number>; end: ComputedRef<number>
  padTop: ComputedRef<number>; padBottom: ComputedRef<number>; totalHeight: ComputedRef<number>
  scrollToIndex: (index: number) => void
}
```

(`start`/`end`/`padTop`/`padBottom`/`totalHeight` are all `computed` → `ComputedRef`; `scrollTop`/`viewportH` are internal writable `ref`s the composable owns.)

- `scrollTop` ref ← a `scroll` listener on the container; `viewportH` ref ← a `ResizeObserver` on the container (initial measure in `onMounted`).
- `start`/`end`/`padTop`/`padBottom` are `computed` from `computeWindow(scrollTop, viewportH, total())`.
- `totalHeight = computed(() => total() * ROW_H)`.
- `scrollToIndex(i)`: `const next = scrollOffsetFor(i, scrollTop, viewportH, total()); if (next != null && container) container.scrollTop = next` (the resulting scroll event recomputes the window so the row mounts).
- Listeners/observer removed in `onUnmounted`.

### 2. `NodeTreePanel.vue`

- Add `const rowsEl = ref<HTMLElement | null>(null)` bound to `.np-rows`; `const { start, end, padTop, padBottom, totalHeight, scrollToIndex } = useVirtualRows(rowsEl, () => store.rows.length)`.
- Template — wrap the list in a sizer with spacers (keeps the scrollbar height correct while only the window is in the DOM):

```html
<div class="np-rows" ref="rowsEl">
  <div class="np-sizer" :style="{ height: totalHeight + 'px' }">
    <div :style="{ height: padTop + 'px' }" />
    <NodeTreeRow
      v-for="row in store.rows.slice(start, end)"
      :key="row.node.id"
      ... (all existing props + handlers unchanged) ...
    />
    <div :style="{ height: padBottom + 'px' }" />
  </div>
  <el-empty v-if="!store.rows.length" description="暂无节点" />
</div>
```

- Add `watch(() => store.selectedId, (id) => { if (!id) return; const i = store.rows.findIndex(r => r.node.id === id); if (i >= 0) nextTick(() => scrollToIndex(i)) })` so create/undo/keyboard selection of an off-window node scrolls it into view. The guard `i >= 0` means a selection filtered out by search won't fight the filter.
- All existing handlers (`onSelect`/`onCheck`/`onChip`/`onIndent`/drag/`@toggle`/`@remove`) and `checkStates`/`hintFor` are unchanged.

### 3. `NodeTreeRow.vue` — no change

Rows still render at 30px with identical markup. DnD, tri-state checkbox, Tab-indent (`tabindex=-1` + `@keydown`) keep working because rendering is identical; only fewer rows mount. Drag still fires on mounted (visible) rows; `computeReorder` uses the full `store.nodes`.

### 4. Bonus — make `visibleRows()` O(N) (`frontend/src/utils/nodeTree.ts`)

Today `visibleRows` calls the O(N) `hasChildren(nodes, id)` per row → O(N²), recomputed by the `rows` getter on every selection/keystroke. Precompute a `Set` of parent-ids once at the top of `visibleRows` and use `parentIds.has(id)` for the per-row child check. The exported `hasChildren` stays for any other callers. Pure refactor; output identical. Serves the same "large procedure performant" goal (compute cost, complementary to DOM windowing).

## Data flow

```
store.rows (reactive, fixed 30px each)
  └─ NodeTreePanel
       ├─ useVirtualRows(rowsEl, () => rows.length)
       │     scroll listener → scrollTop ; ResizeObserver → viewportH
       │     computeWindow(...) → { start, end, padTop, padBottom }
       └─ template: sizer(totalHeight) ▸ spacer(padTop) ▸ rows.slice(start,end) ▸ spacer(padBottom)
  watch(selectedId) → scrollOffsetFor → container.scrollTop → scroll event → window recompute → row mounts
```

## Error handling / edge cases

- **Unmeasured container** (height 0, jsdom, pre-mount): `computeWindow` returns render-all — safe default, keeps existing tests green.
- **Small list** (`≤ MIN_TO_VIRTUALIZE`): render-all, no windowing math, no visual jitter.
- **Row count shrinks** (delete/collapse/filter): `end` is clamped to `total`; `padBottom ≥ 0`; the browser clamps over-scroll; the next scroll/resize recomputes.
- **Selected node filtered out** by search: `findIndex` returns -1 → no scroll (don't fight the filter).
- **DnD to an off-screen target**: relies on the browser's native HTML5 drag-edge auto-scroll; no custom auto-scroller. Accepted limitation.

## Testing

- **New `frontend/tests/unit/composables/useVirtualRows.spec.ts`** (pure functions):
  - `computeWindow`: mid-list window (start/end/padTop/padBottom), top (start clamped to 0), bottom (end clamped to total, padBottom 0), height-0 → render-all, `total ≤ minToVirtualize` → render-all, overscan applied.
  - `scrollOffsetFor`: already-visible → null; above → aligns to top; below → aligns to bottom; viewport 0 → null.
- **`frontend/tests/unit/nodeTree.spec.ts`**: add a `hasChildren`-equivalence case proving the O(N) `visibleRows` refactor renders identical caret/child flags.
- **`frontend/tests/unit/NodeTreePanel.spec.ts`**: existing assertions stay green via the height-0 degrade (all rows mount in jsdom). Add one test that stubs the container `clientHeight` (e.g. `Object.defineProperty`) + a populated row list, dispatches a `scroll` event, and asserts only the windowed subset of `NodeTreeRow`s mount and `padTop` is set.
- vue-tsc clean; full frontend suite green.
- **Browser smoke** (orchestrator, best-effort): a large procedure — confirm DOM `NodeTreeRow` count ≪ total, smooth scroll, selecting/creating an off-window node scrolls it into view, and drag-drop / checkbox / Tab-indent still work.

## Non-goals (YAGNI)

- Variable row heights (rows are fixed 30px).
- Custom drag auto-scroll (use the browser's native edge auto-scroll).
- Horizontal virtualization.
- Arrow-key row-to-row navigation (out of scope, as in E3).
- Changing the backend, the row markup, or any E1–E4 behavior.
