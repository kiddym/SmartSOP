# E11 — Arrow-Key Row Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Up/Down move selection+focus between visible tree rows; Left/Right collapse-or-jump-to-parent / expand-or-jump-to-first-child. Coexists with E3 Tab-indent + E5 virtualization.

**Architecture:** Pure `arrowNav(rows, currentId, dir)` in `nodeTree.ts`; `NodeTreeRow.onKeydown` emits `nav(dir)`; `NodeTreePanel.onNav` applies it (select+focus via `data-node-id`, or `toggleExpand`). Spec: `docs/superpowers/specs/2026-05-29-editor-e11-arrow-key-tree-nav-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, vitest + @vue/test-utils, vue-tsc. No new dependency.

---

## File Structure

- **Modify** `frontend/src/utils/nodeTree.ts` — add `NavAction` + `arrowNav`.
- **Modify** `frontend/tests/unit/utils/nodeTree.spec.ts` — `arrowNav` tests.
- **Modify** `frontend/src/components/editor/NodeTreeRow.vue` — `data-node-id`, `nav` emit, arrows in `onKeydown`.
- **Modify** `frontend/tests/unit/NodeTreeRow.spec.ts` — arrow-emit tests.
- **Modify** `frontend/src/components/editor/NodeTreePanel.vue` — `@nav` + `onNav`.

No backend change. The select+focus DOM behavior is verified by the orchestrator browser smoke (single-step targets are within E5 overscan; jsdom has no layout).

---

## Task 1: Pure `arrowNav` in `nodeTree.ts`

**Files:**
- Modify: `frontend/src/utils/nodeTree.ts`
- Test: `frontend/tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/utils/nodeTree.spec.ts`**

Add `arrowNav` to the existing import from `@/utils/nodeTree` (the top line currently imports `nodeTitle, hasChildren, visibleRows, descendantIds, subtreeIds, checkStates, indentLevel`). Then append:
```ts
import type { TreeRow } from '@/utils/nodeTree'

function row(over: Partial<Node>, rowOver: Partial<TreeRow> = {}): TreeRow {
  return { node: n(over), title: '', hasChildren: false, expanded: true, ...rowOver }
}

describe('arrowNav', () => {
  // c1 (expanded parent) > a, b ; c2 (collapsed parent)
  const rows: TreeRow[] = [
    row({ id: 'c1', heading_level: 1 }, { hasChildren: true, expanded: true }),
    row({ id: 'a', parent_id: 'c1' }),
    row({ id: 'b', parent_id: 'c1' }),
    row({ id: 'c2', heading_level: 1 }, { hasChildren: true, expanded: false }),
  ]
  it('down/up select next/prev, clamped at the ends', () => {
    expect(arrowNav(rows, 'c1', 'down')).toEqual({ type: 'select', id: 'a' })
    expect(arrowNav(rows, 'a', 'up')).toEqual({ type: 'select', id: 'c1' })
    expect(arrowNav(rows, 'c1', 'up')).toBeNull()
    expect(arrowNav(rows, 'c2', 'down')).toBeNull()
  })
  it('right: expand collapsed, step into first child when expanded, no-op on a leaf', () => {
    expect(arrowNav(rows, 'c2', 'right')).toEqual({ type: 'expand', id: 'c2' })
    expect(arrowNav(rows, 'c1', 'right')).toEqual({ type: 'select', id: 'a' })
    expect(arrowNav(rows, 'a', 'right')).toBeNull()
  })
  it('left: collapse expanded, jump to parent, no-op at a childless root', () => {
    expect(arrowNav(rows, 'c1', 'left')).toEqual({ type: 'collapse', id: 'c1' })
    expect(arrowNav(rows, 'a', 'left')).toEqual({ type: 'select', id: 'c1' })
    expect(arrowNav(rows, 'c2', 'left')).toBeNull()
  })
  it('unknown/null currentId → up/down picks the first row; left/right null', () => {
    expect(arrowNav(rows, 'zzz', 'down')).toEqual({ type: 'select', id: 'c1' })
    expect(arrowNav(rows, null, 'right')).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/utils/nodeTree.spec.ts`
Expected: FAIL — `arrowNav` not exported.

- [ ] **Step 3: Implement — append to `frontend/src/utils/nodeTree.ts`**

```ts
export type NavAction = { type: 'select' | 'expand' | 'collapse'; id: string }

/** Pure arrow-key navigation over the visible rows (tree-ordered; rows carry hasChildren/expanded;
 *  node.parent_id gives the parent). Returns the action, or null for a no-op (boundary/leaf/root). */
export function arrowNav(
  rows: TreeRow[],
  currentId: string | null,
  dir: 'up' | 'down' | 'left' | 'right',
): NavAction | null {
  const idx = rows.findIndex((r) => r.node.id === currentId)
  if (idx < 0) {
    return (dir === 'up' || dir === 'down') && rows.length
      ? { type: 'select', id: rows[0].node.id }
      : null
  }
  const r = rows[idx]
  if (dir === 'up') return idx > 0 ? { type: 'select', id: rows[idx - 1].node.id } : null
  if (dir === 'down') return idx < rows.length - 1 ? { type: 'select', id: rows[idx + 1].node.id } : null
  if (dir === 'right') {
    if (r.hasChildren && !r.expanded) return { type: 'expand', id: r.node.id }
    if (r.hasChildren && r.expanded) {
      const child = rows.find((x, j) => j > idx && x.node.parent_id === r.node.id)
      return child ? { type: 'select', id: child.node.id } : null
    }
    return null
  }
  // left
  if (r.hasChildren && r.expanded) return { type: 'collapse', id: r.node.id }
  const pid = r.node.parent_id
  return pid && rows.some((x) => x.node.id === pid) ? { type: 'select', id: pid } : null
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/utils/nodeTree.spec.ts` → expect all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/nodeTree.ts frontend/tests/unit/utils/nodeTree.spec.ts
git commit -m "feat(editor): pure arrowNav for tree row navigation (E11 Task 1)"
```

---

## Task 2: `NodeTreeRow` — data-node-id + nav emit

**Files:**
- Modify: `frontend/src/components/editor/NodeTreeRow.vue`
- Test: `frontend/tests/unit/NodeTreeRow.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/NodeTreeRow.spec.ts`**

Append a new describe block (reuses the file's `mountRow`/`treeRow` helpers):
```ts
describe('NodeTreeRow — arrow nav', () => {
  it('arrows on the row root emit nav with direction', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr').trigger('keydown', { key: 'ArrowDown' })
    await w.find('.ntr').trigger('keydown', { key: 'ArrowUp' })
    await w.find('.ntr').trigger('keydown', { key: 'ArrowLeft' })
    await w.find('.ntr').trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('nav')).toEqual([['down'], ['up'], ['left'], ['right']])
  })
  it('arrow from an inner control (checkbox) does not emit nav', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr-check').trigger('keydown', { key: 'ArrowDown' })
    expect(w.emitted('nav')).toBeFalsy()
  })
  it('row root carries data-node-id', () => {
    const w = mountRow(treeRow({ id: 'xyz' }))
    expect(w.find('.ntr').attributes('data-node-id')).toBe('xyz')
  })
  it('readonly row emits no nav', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }), { readonly: true })
    await w.find('.ntr').trigger('keydown', { key: 'ArrowDown' })
    expect(w.emitted('nav')).toBeFalsy()
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/NodeTreeRow.spec.ts`
Expected: the 4 new tests FAIL (no `nav` emit, no `data-node-id`); existing Tab/tabindex tests pass.

- [ ] **Step 3: Implement in `frontend/src/components/editor/NodeTreeRow.vue`**

(a) Add `nav` to `defineEmits` (after the existing `indent` line, line 25):
```ts
  (e: 'indent', dir: 'in' | 'out'): void
  (e: 'nav', dir: 'up' | 'down' | 'left' | 'right'): void
```
(b) Replace `onKeydown` (lines 39-44) with a version that keeps Tab and adds the arrows:
```ts
const NAV_KEYS: Record<string, 'up' | 'down' | 'left' | 'right'> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
}
function onKeydown(ev: KeyboardEvent): void {
  if (props.readonly) return
  if (ev.target !== ev.currentTarget) return // 仅行本身聚焦（非内部 checkbox/chip）
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
(c) Add `:data-node-id="n.id"` to the row root `<div class="ntr" …>` (add it as an attribute, e.g. right after the `class`/`:class` bindings, line ~50):
```html
  <div
    class="ntr"
    :class="[{ 'ntr--selected': selected }, dropHint ? `ntr--drop-${dropHint}` : '']"
    :data-node-id="n.id"
    :style="{ boxSizing: 'border-box', paddingLeft: `${n.depth * 16 + 6}px` }"
    ...
```
Change nothing else.

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/NodeTreeRow.spec.ts` → expect all PASS (existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/NodeTreeRow.vue frontend/tests/unit/NodeTreeRow.spec.ts
git commit -m "feat(editor): NodeTreeRow emits nav on arrows + data-node-id (E11 Task 2)"
```

---

## Task 3: `NodeTreePanel` — wire `@nav` → `onNav`

**Files:**
- Modify: `frontend/src/components/editor/NodeTreePanel.vue`

No new unit test (the panel's select+focus-by-`data-node-id` needs layout/focus, verified by the browser smoke; the decision logic is Task 1's pure tests). Verified here by vue-tsc + full suite green.

- [ ] **Step 1: Import `arrowNav`**

The panel already imports from `@/utils/nodeTree` (e.g. `import { subtreeIds, checkStates, indentLevel, type TreeRow } from '@/utils/nodeTree'`). Add `arrowNav`:
```ts
import { subtreeIds, checkStates, indentLevel, arrowNav, type TreeRow } from '@/utils/nodeTree'
```
(`nextTick` and `rowsEl` already exist from E5 — confirm `nextTick` is in the `vue` import; it is.)

- [ ] **Step 2: Add `onNav`**

Add near the other row handlers (e.g. after `onIndent`):
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
    store.toggleExpand(action.id) // expand (was collapsed) or collapse (was expanded)
  }
}
```

- [ ] **Step 3: Bind `@nav` on `NodeTreeRow`**

In the `<NodeTreeRow … />` block, add (next to the existing `@indent`):
```html
          @indent="(dir: 'in' | 'out') => onIndent(row.node.id, dir)"
          @nav="(dir: 'up' | 'down' | 'left' | 'right') => onNav(row.node.id, dir)"
```

- [ ] **Step 4: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures (Task 1 arrowNav tests + Task 2 row tests + everything else).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/NodeTreePanel.vue
git commit -m "feat(editor): NodeTreePanel wires arrow nav (select+focus / toggle) (E11 Task 3)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 3, before merge)

Launch the worktree dev servers (bootstrap backend), open a procedure editor (`/procedures/<id>/edit`), click a tree row to focus it, then:
1. ArrowDown/ArrowUp move the selection highlight + focus to the adjacent row (and scroll when needed).
2. ArrowRight on a collapsed chapter expands it; ArrowRight again steps into its first child; ArrowLeft collapses an expanded chapter; ArrowLeft on a leaf jumps to its parent.
3. Click into the node body editor and press arrows — the tree selection does NOT move (focus guard: arrows only act on a focused row).
(Reuse a procedure with nested chapters, e.g. the 37-node `356e353c…`. If staging is impractical, note it — the pure logic is unit-tested and the row emit is unit-tested.)

---

## Self-Review

**Spec coverage:**
- Pure `arrowNav` (up/down select+clamp; right expand/first-child/leaf-noop; left collapse/parent/root-noop; unknown id) → Task 1. ✓
- Row `onKeydown` adds arrows (guarded by readonly + `target===currentTarget`), emits `nav`; `data-node-id` on root → Task 2. ✓
- Panel `onNav` → select+focus-by-`data-node-id` (E5 overscan keeps it rendered; native focus + E5 watcher scroll) / `toggleExpand` → Task 3. ✓
- Coexists with E3 (same guarded `onKeydown`, Tab path intact) + E5 (windowing untouched; focus via `data-node-id`) → Tasks 2-3. ✓
- Non-goals (Home/End/PageUp-Down, type-ahead, Shift+Arrow, a11y roles) → untouched. ✓

**Placeholder scan:** none — full code for the function, the row, and the panel.

**Type consistency:** `NavAction`/`arrowNav` defined in Task 1, used in Task 3. `nav` emit `dir: 'up'|'down'|'left'|'right'` matches `onNav`'s param and `arrowNav`'s `dir`. `data-node-id` attribute (Task 2) matches the panel's `querySelector('[data-node-id="…"]')` (Task 3). `rowsEl`/`nextTick`/`store` already in the panel from E5.
