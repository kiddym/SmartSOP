# E11 — Arrow-Key Row Navigation (Node-Editor Tree) — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Feature; the arrow-key nav deferred from E3 (Tab indent). Builds on E3 (row focus) and E5 (virtualization + scroll-into-view).
**Status:** Design approved; ready for implementation plan.

## Goal

Keyboard navigation of the node tree: **Up/Down** move selection (and focus) between visible rows; **Left/Right** collapse/expand or jump to parent/first-child (standard ARIA tree pattern). Coexists with E3 Tab-indent and E5 windowing; frontend-only.

## Background (how E3 + E5 already work)

- **E3 focus model:** rows (`NodeTreeRow`) are `tabindex="-1"` (click-focusable, not in page Tab order). `onKeydown` handles `Tab`/`Shift+Tab` → `emit('indent', …)`, guarded by `ev.target === ev.currentTarget` (so inner checkbox/chip don't trigger) and `props.readonly`.
- **E5 selection→scroll:** `NodeTreePanel` renders the windowed slice `store.rows.slice(start, end)`; `watch(store.selectedId)` → `nextTick(scrollToIndex(i))` already scrolls a (re)selected node into the window. A single arrow step always lands within E5's 8-row overscan, so the target row is already in the DOM; calling `.focus()` on it also natively scrolls it into view.
- **Selection:** `store.select(id)` sets `selectedId`; the row's `:selected` binding highlights it; the detail panel follows `selectedId`.
- **Rows model:** `store.rows: TreeRow[]` (flat, tree-ordered) — each `TreeRow` has `node`, `hasChildren`, `expanded`; `node.parent_id` gives the parent. `store.toggleExpand(id)` flips collapse state.

## Approach (Model A — extend the row; preserve E3 + E5)

Arrow handling lives in the **row's existing `onKeydown`** (not window-level), so it only fires when a tree row is focused — never while typing in the body editor / form inputs. The row emits a `nav` direction; the panel computes the action via a **pure function** and applies it (select + focus, or toggle-expand).

## Components & changes

### 1. Pure `arrowNav` — `frontend/src/utils/nodeTree.ts`

```ts
export type NavAction = { type: 'select' | 'expand' | 'collapse'; id: string }

/** Pure: given the visible rows, the currently-focused row id, and a direction,
 *  return the navigation action (or null for a no-op at a boundary/leaf).
 *  rows are tree-ordered; each carries hasChildren/expanded; node.parent_id gives the parent. */
export function arrowNav(
  rows: TreeRow[],
  currentId: string | null,
  dir: 'up' | 'down' | 'left' | 'right',
): NavAction | null {
  const idx = rows.findIndex((r) => r.node.id === currentId)
  if (idx < 0) {
    // No anchor (shouldn't happen — focus follows selection): up/down picks the first row.
    return (dir === 'up' || dir === 'down') && rows.length ? { type: 'select', id: rows[0].node.id } : null
  }
  const row = rows[idx]
  if (dir === 'up') return idx > 0 ? { type: 'select', id: rows[idx - 1].node.id } : null
  if (dir === 'down') return idx < rows.length - 1 ? { type: 'select', id: rows[idx + 1].node.id } : null
  if (dir === 'right') {
    if (row.hasChildren && !row.expanded) return { type: 'expand', id: row.node.id }
    if (row.hasChildren && row.expanded) {
      const child = rows.find((r, j) => j > idx && r.node.parent_id === row.node.id)
      return child ? { type: 'select', id: child.node.id } : null
    }
    return null // leaf
  }
  // left
  if (row.hasChildren && row.expanded) return { type: 'collapse', id: row.node.id }
  const pid = row.node.parent_id
  return pid && rows.some((r) => r.node.id === pid) ? { type: 'select', id: pid } : null
}
```

### 2. `NodeTreeRow.vue`

- Add `:data-node-id="n.id"` to the row root (so the panel can focus a specific row's DOM element under virtualization).
- Add `(e: 'nav', dir: 'up' | 'down' | 'left' | 'right'): void` to `defineEmits`.
- Extend `onKeydown` (keeping the `readonly` + `ev.target === ev.currentTarget` guards) to also map the four arrows:
```ts
const NAV_KEYS: Record<string, 'up' | 'down' | 'left' | 'right'> = {
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
}
function onKeydown(ev: KeyboardEvent): void {
  if (props.readonly) return
  if (ev.target !== ev.currentTarget) return // row itself, not inner checkbox/chip
  if (ev.key === 'Tab') {
    ev.preventDefault()
    emit('indent', ev.shiftKey ? 'out' : 'in')
    return
  }
  const dir = NAV_KEYS[ev.key]
  if (dir) {
    ev.preventDefault()
    emit('nav', dir)
  }
}
```

### 3. `NodeTreePanel.vue`

- Import `arrowNav` from `@/utils/nodeTree`.
- Bind `@nav="(dir) => onNav(row.node.id, dir)"` on `<NodeTreeRow>`.
- Handler:
```ts
function onNav(currentId: string, dir: 'up' | 'down' | 'left' | 'right'): void {
  const action = arrowNav(store.rows, currentId, dir)
  if (!action) return
  if (action.type === 'select') {
    store.select(action.id)
    void nextTick(() => {
      rowsEl.value?.querySelector<HTMLElement>(`[data-node-id="${action.id}"]`)?.focus()
    })
  } else {
    store.toggleExpand(action.id) // expand or collapse; focus stays on the current row
  }
}
```
(`store.toggleExpand` flips collapse state, so both `expand` (row was collapsed) and `collapse` (row was expanded) map to it correctly. `nextTick` lets the selected row render — it's within E5's overscan — before `.focus()`, which also natively scrolls it into view; E5's `selectedId` watcher is a belt-and-suspenders scroll.)

## Data flow

```
focused row keydown(Arrow) → emit('nav', dir) → NodeTreePanel.onNav(rowId, dir)
  → arrowNav(rows, rowId, dir) → action
     select → store.select(id) + nextTick focus [data-node-id] (native scroll-in; E5 watcher too)
     expand/collapse → store.toggleExpand(id)
```

## Error handling / edge cases

- Boundaries: Up on the first row / Down on the last → `null` (no-op). Right on a leaf → `null`. Left on a root with no children → `null`.
- `currentId` not found (shouldn't happen — focus follows selection): Up/Down selects the first row; Left/Right no-op.
- Readonly (`/view`): rows have no `tabindex` (E3) → no keydown → no nav.
- Inner controls: the `ev.target === ev.currentTarget` guard means arrows inside the checkbox/chip don't navigate (same as Tab).
- Virtualization: single-step targets are within the 8-row overscan (rendered); `.focus()` natively scrolls into view; the E5 `selectedId` watcher also scrolls. (No Home/End/PageUp/Down → no large off-window jumps to special-case.)

## Testing

- **Unit `frontend/tests/unit/utils/nodeTree.spec.ts`** (pure `arrowNav`): up/down select prev/next + clamp at both ends; right expands a collapsed parent, jumps to first child when expanded, no-ops on a leaf; left collapses an expanded parent, jumps to parent, no-ops at a childless root; `currentId` not found → up/down picks first row.
- **`frontend/tests/unit/NodeTreeRow.spec.ts`**: each arrow on the row root emits `nav` with the right dir; an arrow from an inner control (`.ntr-check`) emits nothing (target≠currentTarget); the row root has `data-node-id`; readonly row emits no `nav`. Existing Tab-indent/tabindex tests stay green.
- **Browser smoke:** focus a row; Up/Down moves selection + focus (+ scrolls when needed); Right expands a collapsed chapter then steps into its first child; Left collapses then jumps to parent; confirm arrows while typing in the body editor do NOT navigate the tree.
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Home/End/PageUp/PageDown, type-ahead search, Shift+Arrow range multi-select, moving focus into the detail pane, `role="tree"`/`aria-activedescendant` a11y rework. Does not change E3 Tab-indent or E5 windowing semantics.
