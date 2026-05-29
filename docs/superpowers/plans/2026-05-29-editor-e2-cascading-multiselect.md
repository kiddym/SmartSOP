# Editor E2 — Cascading Multi-Select Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. (Design approved in conversation; captured here — no separate spec doc.)

**Goal:** Checking a heading node's checkbox selects/deselects its whole subtree (the heading + all descendants); the checkbox is tri-state (checked/indeterminate/unchecked); the γ batch bar applies to everything selected.

**Architecture (approved decisions):** Frontend-only. A uniform "subtree toggle" — a leaf's subtree is just itself, so leaves behave exactly as today; headings cascade to their whole subtree (incl. the heading, incl. collapsed descendants, since it operates on `store.nodes`). Shift+click range-select (existing `buildSelection`, same-parent) is unchanged. Per-heading tri-state is computed from the selection. The γ bar ops are unchanged (apply to all selected; reversible via E1 undo).

**Tech Stack:** Vue 3 `<script setup>`, Pinia, Element Plus (`el-checkbox` `indeterminate`), vitest + @vue/test-utils. From `frontend/`: `npx vitest run <path>`, `npx vue-tsc --noEmit`, `npm test`.

**Conventions:** commits end with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer (omitted below); `git add` explicit paths only.

---

## Task 1: Pure logic — `buildCascadeSelection` refactor + `nodeTree` helpers

**Files:**
- Modify: `frontend/src/utils/batchMark.ts`, `frontend/src/utils/nodeTree.ts`
- Test: `frontend/tests/unit/utils/batchMark.spec.ts`, `frontend/tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: Update the failing tests.**

(a) In `frontend/tests/unit/utils/batchMark.spec.ts`, replace the entire `describe('buildCascadeSelection', () => { ... })` block with (new "whole subtree incl. root" semantics — caller passes `ids` which already includes the root):
```ts
describe('buildCascadeSelection', () => {
  it('select: adds all ids (incl. root), anchor=rootId', () => {
    const r = buildCascadeSelection({
      current: new Set(),
      rootId: 'c1',
      ids: ['c1', 'a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 'c1', 's1'])
    expect(r.anchor).toBe('c1')
    expect(r.warnings).toEqual([])
  })

  it('deselect: removes exactly the passed ids (incl. root), leaves others', () => {
    const r = buildCascadeSelection({
      current: new Set(['c1', 'a', 'b', 's1', 'other']),
      rootId: 'c1',
      ids: ['c1', 'a', 'b', 's1'],
      action: 'deselect',
    })
    expect([...r.selection].sort()).toEqual(['other'])
    expect(r.anchor).toBe('c1')
  })

  it('select: partial pre-selection is completed', () => {
    const r = buildCascadeSelection({
      current: new Set(['a']),
      rootId: 'c1',
      ids: ['c1', 'a', 'b', 's1'],
      action: 'select',
    })
    expect([...r.selection].sort()).toEqual(['a', 'b', 'c1', 's1'])
  })

  it('over 100: trims to first 100 (insertion order) + warns; anchor=rootId', () => {
    const ids = ['root', ...Array.from({ length: 150 }, (_, i) => `d${i}`)]
    const r = buildCascadeSelection({ current: new Set(), rootId: 'root', ids, action: 'select' })
    expect(r.selection.size).toBe(MAX_BATCH_MARK)
    expect(r.warnings.some((w) => w.includes('最多标记'))).toBe(true)
    expect(r.selection.has('root')).toBe(true) // root now included
    expect(r.anchor).toBe('root')
  })
})
```

(b) In `frontend/tests/unit/utils/nodeTree.spec.ts`, append (reuse the file's existing `Node` factory if present — if it imports a helper named differently, mirror it; otherwise add a local `n()` like other specs):
```ts
import { descendantIds, subtreeIds, checkStates } from '@/utils/nodeTree'

describe('descendantIds / subtreeIds', () => {
  // tree: c1 > (a, c2 > (b)), c3
  const nodes = [
    n({ id: 'c1', heading_level: 1, sort_order: 0 }),
    n({ id: 'a', parent_id: 'c1', sort_order: 1000 }),
    n({ id: 'c2', heading_level: 2, parent_id: 'c1', sort_order: 2000 }),
    n({ id: 'b', parent_id: 'c2', sort_order: 3000 }),
    n({ id: 'c3', heading_level: 1, sort_order: 4000 }),
  ]
  it('descendantIds: all transitive descendants (excl. self)', () => {
    expect(descendantIds(nodes, 'c1').sort()).toEqual(['a', 'b', 'c2'])
    expect(descendantIds(nodes, 'a')).toEqual([]) // leaf
    expect(descendantIds(nodes, 'c3')).toEqual([])
  })
  it('subtreeIds: self + descendants', () => {
    expect(subtreeIds(nodes, 'c2').sort()).toEqual(['b', 'c2'])
    expect(subtreeIds(nodes, 'a')).toEqual(['a'])
  })
})

describe('checkStates', () => {
  const nodes = [
    n({ id: 'c1', heading_level: 1, sort_order: 0 }),
    n({ id: 'a', parent_id: 'c1', sort_order: 1000 }),
    n({ id: 'b', parent_id: 'c1', sort_order: 2000 }),
  ]
  it('heading checked when whole subtree selected', () => {
    const s = checkStates(nodes, new Set(['c1', 'a', 'b']))
    expect(s.get('c1')).toBe('checked')
  })
  it('heading indeterminate when partially selected', () => {
    const s = checkStates(nodes, new Set(['a']))
    expect(s.get('c1')).toBe('indeterminate')
    expect(s.get('a')).toBe('checked')
    expect(s.get('b')).toBe('unchecked')
  })
  it('heading unchecked when nothing selected', () => {
    const s = checkStates(nodes, new Set())
    expect(s.get('c1')).toBe('unchecked')
  })
})
```
(If `nodeTree.spec.ts` has no `n()`/`Node` factory, add at the top: `import type { Node } from '@/types/node'` and a local `function n(over: Partial<Node>): Node { return { id:'x', procedure_id:'p1', sort_order:0, heading_level:null, kind:'node', body:'', code:'', skip_numbering:false, input_schema:{}, attachment_marks:[], mark_status:'unmarked', revision:1, parent_id:null, depth:0, ...over } }`.)

- [ ] **Step 2: Run; verify fail.**
Run: `cd frontend && npx vitest run tests/unit/utils/batchMark.spec.ts tests/unit/utils/nodeTree.spec.ts`
Expected: FAIL — `buildCascadeSelection` still excludes root / `descendantIds`/`subtreeIds`/`checkStates` undefined.

- [ ] **Step 3: Implement `batchMark.ts`.** Replace the `CascadeParams` interface + `buildCascadeSelection` function (lines ~77-102) with:
```ts
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
```

- [ ] **Step 4: Implement `nodeTree.ts` helpers.** Append:
```ts
/** 沿 parent_id 反向闭包，返回 id 的所有后代（不含自身）。 */
export function descendantIds(nodes: Node[], id: string): string[] {
  const childrenByParent = new Map<string | null, string[]>()
  for (const x of nodes) {
    const arr = childrenByParent.get(x.parent_id)
    if (arr) arr.push(x.id)
    else childrenByParent.set(x.parent_id, [x.id])
  }
  const out: string[] = []
  const stack = [...(childrenByParent.get(id) ?? [])]
  while (stack.length) {
    const cur = stack.pop() as string
    out.push(cur)
    const kids = childrenByParent.get(cur)
    if (kids) stack.push(...kids)
  }
  return out
}

/** 子树 = 自身 + 所有后代。 */
export function subtreeIds(nodes: Node[], id: string): string[] {
  return [id, ...descendantIds(nodes, id)]
}

export type CheckState = 'checked' | 'indeterminate' | 'unchecked'

/** 每个节点的三态：其子树（含自身）全选=checked，部分=indeterminate，皆未选=unchecked。O(N)。 */
export function checkStates(nodes: Node[], selection: ReadonlySet<string>): Map<string, CheckState> {
  const childrenByParent = new Map<string | null, Node[]>()
  for (const x of nodes) {
    const arr = childrenByParent.get(x.parent_id)
    if (arr) arr.push(x)
    else childrenByParent.set(x.parent_id, [x])
  }
  const memo = new Map<string, { sel: number; total: number }>()
  const visit = (node: Node): { sel: number; total: number } => {
    const cached = memo.get(node.id)
    if (cached) return cached
    let sel = selection.has(node.id) ? 1 : 0
    let total = 1
    for (const c of childrenByParent.get(node.id) ?? []) {
      const r = visit(c)
      sel += r.sel
      total += r.total
    }
    const r = { sel, total }
    memo.set(node.id, r)
    return r
  }
  const out = new Map<string, CheckState>()
  for (const node of nodes) {
    const { sel, total } = visit(node)
    out.set(node.id, sel === 0 ? 'unchecked' : sel === total ? 'checked' : 'indeterminate')
  }
  return out
}
```

- [ ] **Step 5: Run; verify pass.**
Run: `cd frontend && npx vitest run tests/unit/utils/batchMark.spec.ts tests/unit/utils/nodeTree.spec.ts` → PASS.
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/utils/batchMark.ts frontend/src/utils/nodeTree.ts frontend/tests/unit/utils/batchMark.spec.ts frontend/tests/unit/utils/nodeTree.spec.ts
git commit -m "feat(fe): cascade selection logic — buildCascadeSelection incl. root + nodeTree descendant/subtree/checkStates helpers (E2)"
```

---

## Task 2: Components — `NodeTreePanel` cascade + `NodeTreeRow` tri-state

**Files:**
- Modify: `frontend/src/components/editor/NodeTreeRow.vue`, `frontend/src/components/editor/NodeTreePanel.vue`
- Test: `frontend/tests/unit/NodeTreeRow.spec.ts`, `frontend/tests/unit/NodeTreePanel.spec.ts`

- [ ] **Step 1: Write the failing tests.**

(a) Append to `frontend/tests/unit/NodeTreeRow.spec.ts`:
```ts
  it('passes indeterminate to the checkbox', () => {
    const w = mountRow(treeRow({ heading_level: 1 }, { hasChildren: true }), { indeterminate: true })
    expect(w.find('.ntr-check').classes()).toContain('is-indeterminate')
  })
```

(b) Append to `frontend/tests/unit/NodeTreePanel.spec.ts`:
```ts
  it('checking a heading cascades to its whole subtree (incl. heading)', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'a', parent_id: 'c1', sort_order: 1000, depth: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'c1', sort_order: 2000, depth: 1, body: '<p>B</p>' }),
    ])
    const rowC1 = w.findAllComponents({ name: 'NodeTreeRow' })[0]
    rowC1.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect([...store.selection].sort()).toEqual(['a', 'b', 'c1'])
    // checking again deselects the whole subtree
    rowC1.vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(store.selection.size).toBe(0)
  })

  it('heading row gets indeterminate when only some descendants are selected', async () => {
    const { w, store } = setup([
      n({ id: 'c1', heading_level: 1, body: '<p>C1</p>' }),
      n({ id: 'a', parent_id: 'c1', sort_order: 1000, depth: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'c1', sort_order: 2000, depth: 1, body: '<p>B</p>' }),
    ])
    store.selection = new Set(['a'])
    await w.vm.$nextTick()
    const rowC1 = w.findAllComponents({ name: 'NodeTreeRow' })[0]
    expect(rowC1.props('indeterminate')).toBe(true)
    expect(rowC1.props('selectedForMark')).toBe(false)
  })
```

- [ ] **Step 2: Run; verify fail.**
Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts tests/unit/NodeTreePanel.spec.ts`
Expected: FAIL — no `indeterminate` prop / heading check does not cascade.

- [ ] **Step 3: Implement `NodeTreeRow.vue`.**
- Add `indeterminate?: boolean` to `Props` (after `selectedForMark`): `indeterminate?: boolean`. (Keep `selectedForMark`.)
- On the `<el-checkbox>` add `:indeterminate="indeterminate"`:
```html
    <el-checkbox
      v-if="!readonly"
      :model-value="selectedForMark"
      :indeterminate="indeterminate"
      class="ntr-check"
      @click.stop="onCheck"
    />
```

- [ ] **Step 4: Implement `NodeTreePanel.vue`.**
- Imports: add `buildCascadeSelection` to the `@/utils/batchMark` import; add `import { subtreeIds, checkStates } from '@/utils/nodeTree'`.
- Add a computed map (after `const search = ...`):
```ts
const states = computed(() => checkStates(store.nodes, store.selection))
```
- Replace `onCheck` with cascade-on-normal-click, range-on-shift:
```ts
function onCheck(id: string, shift: boolean): void {
  if (shift && anchor.value) {
    const rows = store.rows.map((r) => ({ id: r.node.id, parent_id: r.node.parent_id, kind: r.node.kind }))
    const res = buildSelection({ current: store.selection, anchor: anchor.value, rows, rowId: id, shift: true })
    store.selection = res.selection
    anchor.value = res.anchor
    for (const wmsg of res.warnings) ElMessage.warning(wmsg)
    return
  }
  const ids = subtreeIds(store.nodes, id)
  const allSelected = ids.every((x) => store.selection.has(x))
  const res = buildCascadeSelection({
    current: store.selection,
    rootId: id,
    ids,
    action: allSelected ? 'deselect' : 'select',
  })
  store.selection = res.selection
  anchor.value = res.anchor
  for (const wmsg of res.warnings) ElMessage.warning(wmsg)
}
```
- In the `<NodeTreeRow>` template, replace `:selected-for-mark="store.selection.has(row.node.id)"` with:
```html
        :selected-for-mark="states.get(row.node.id) === 'checked'"
        :indeterminate="states.get(row.node.id) === 'indeterminate'"
```

- [ ] **Step 5: Run; verify pass + type-check.**
Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts tests/unit/NodeTreePanel.spec.ts` → PASS.
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/components/editor/NodeTreeRow.vue frontend/src/components/editor/NodeTreePanel.vue frontend/tests/unit/NodeTreeRow.spec.ts frontend/tests/unit/NodeTreePanel.spec.ts
git commit -m "feat(fe/editor): cascading subtree multi-select + tri-state heading checkbox (E2)"
```

---

## Task 3: Verify + browser smoke + finish

- [ ] **Step 1: Full suite + type-check.**
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0; `npm test` → all green (0 failures; expect the prior count + the new tests).

- [ ] **Step 2: Browser smoke** (per `.claude/skills/running-smartsop-dev`). Launch backend + frontend, open a DRAFT procedure `/edit` with at least one heading that has descendants (e.g. proc `356e353c-f3ea-49e1-8e97-674dbefb0e48`, "职责" has 3.x children). With chrome-devtools MCP:
  - Click the checkbox of a heading with children → the γ bar shows "已选 N" where N = subtree size (heading + descendants); the heading's checkbox is **checked**; descendant checkboxes are checked too.
  - Deselect one descendant → the heading checkbox becomes **indeterminate** (has the `is-indeterminate` class).
  - Click the heading checkbox again → whole subtree cleared (bar gone).
  - Re-select the subtree, click "设为步骤" → confirm (via `GET /nodes`) the descendant leaves became `kind:'step'`; then `Ctrl+Z` (E1) reverts.
  - Zero console errors (the pre-existing asset 404 is unrelated).

- [ ] **Step 3: Finish the branch.** Use superpowers:finishing-a-development-branch (merge `--no-ff` to main).

---

## Self-Review Notes
- **Uniform rule:** `subtreeIds(leaf)` = `[leaf]`, so leaf checkboxes toggle exactly as before; only headings cascade. `checkStates` counts the node itself, so leaves are never `indeterminate` (sel ∈ {0, total=1}).
- **Collapsed descendants** are included (cascade + `checkStates` use `store.nodes`, not visible rows) — intended.
- **`buildCascadeSelection` signature changed** (`descendantIds`→`ids`, dropped `anchor`); the only references are its tests (updated in T1) — no production caller today (T2 adds the first).
- **Shift-range** path is byte-for-byte the existing `buildSelection` call — unchanged behavior.
- **el-checkbox indeterminate**: Element Plus renders `is-indeterminate` class when `:indeterminate` is true (asserted in the row test).
