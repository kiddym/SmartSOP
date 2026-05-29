# Editor E1 — Undo/Redo + Keyboard Shortcuts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add redo to the `nodeEditor` store, fix the silent undo-failure bug, and add focus-aware keyboard shortcuts (undo/redo + heading-level keys) to the node editor.

**Architecture:** Frontend-only. (1) `nodeEditor` store: replace the `_suppressUndo` boolean with a 3-mode recorder so running an inverse routes its own inverse to the opposite stack (redo); robust failure handling. (2) New `useEditorShortcuts` composable, focus-guarded, wired into `ProcedureEditorView`. (3) Topbar redo button. Spec: `docs/superpowers/specs/2026-05-29-editor-e1-undo-redo-keyboard-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, Pinia (options store), Element Plus, vitest + @vue/test-utils. Frontend tooling from `frontend/`: type-check `npx vue-tsc --noEmit`; tests `npm test`.

**Conventions:** all commits end with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer (omitted below for brevity); `git add` explicit paths only (never `git add -A` — worktree has gitignored symlinks).

---

## Task 1: Redo + robust undo (`nodeEditor` store)

**Files:**
- Modify: `frontend/src/store/nodeEditor.ts`
- Test: `frontend/tests/unit/store/nodeEditor.spec.ts`

- [ ] **Step 1: Write failing redo tests.** Append to `frontend/tests/unit/store/nodeEditor.spec.ts` (reuses the file's existing `n()` factory + `listSpy`/`batchSpy` hoisted mocks):

```ts
describe('nodeEditor store — redo + robust undo (E1)', () => {
  it('redo replays setLevel after undo (round-trip)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>x</p>' })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    expect(store.canRedo).toBe(false)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    await store.undo()
    expect(store.canUndo).toBe(false)
    expect(store.canRedo).toBe(true)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>x</p>' })])
    await store.redo()
    expect(store.nodeMap.get('a')?.heading_level).toBe(1)
    expect(store.canUndo).toBe(true)
    expect(store.canRedo).toBe(false)
  })

  it('a new op after undo clears the redo stack', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 1 })])
    await store.setLevel('a', 1)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null })])
    await store.undo()
    expect(store.canRedo).toBe(true)
    batchSpy.mockResolvedValueOnce([n({ id: 'a', kind: 'step' })])
    await store.setKind('a', 'step')
    expect(store.canRedo).toBe(false)
  })

  it('failed undo re-pushes the entry and refetches (no silent loss)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null })])
    const store = useNodeEditorStore()
    await store.load('p1')
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1 })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    batchSpy.mockRejectedValueOnce(new Error('conflict'))
    listSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1 })]) // refetch
    await store.undo()
    expect(store.canUndo).toBe(true) // re-pushed, not lost
    expect(listSpy).toHaveBeenCalledTimes(2) // initial load + refetch
  })
})
```

- [ ] **Step 2: Run; verify it fails.**
Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: FAIL — `store.redo`/`store.canRedo` are undefined.

- [ ] **Step 3: Implement.** In `frontend/src/store/nodeEditor.ts`:

(a) In the `State` interface, replace the `_suppressUndo: boolean` field + its comment with:
```ts
  _recordMode: 'normal' | 'undoing' | 'redoing' // 撤销/重做录制模式：决定逆操作入哪个栈
```
(b) In `state()`, replace `_suppressUndo: false,` with `_recordMode: 'normal',`.

(c) Add a `canRedo` getter next to `canUndo`:
```ts
    canRedo(state): boolean {
      return state.redoStack.length > 0
    },
```
(d) Replace the `_pushUndo` action body with mode routing (keep the name + signature; all per-action `this._pushUndo(...)` calls stay unchanged):
```ts
    _pushUndo(inverse: InverseOp): void {
      if (this._recordMode === 'normal') {
        this.undoStack.push(inverse)
        this.redoStack = [] // 新用户操作令 redo 失效
      } else if (this._recordMode === 'undoing') {
        this.redoStack.push(inverse) // 撤销时捕获 redo
      } else {
        this.undoStack.push(inverse) // 重做时捕获 re-undo（不清 redo）
      }
      if (this.undoStack.length > 100) this.undoStack.shift()
      if (this.redoStack.length > 100) this.redoStack.shift()
    },
```
(e) Replace the `undo()` action and add `redo()`:
```ts
    async undo(): Promise<void> {
      const inverse = this.undoStack.pop()
      if (!inverse) return
      this._recordMode = 'undoing'
      try {
        await inverse()
      } catch {
        this.undoStack.push(inverse) // 失败不静默丢弃：重新入栈
        await this._refetch().catch(() => {}) // 与服务端真态对齐（拦截器已提示错误）
      } finally {
        this._recordMode = 'normal'
      }
    },

    async redo(): Promise<void> {
      const inverse = this.redoStack.pop()
      if (!inverse) return
      this._recordMode = 'redoing'
      try {
        await inverse()
      } catch {
        this.redoStack.push(inverse)
        await this._refetch().catch(() => {})
      } finally {
        this._recordMode = 'normal'
      }
    },
```

- [ ] **Step 4: Run; verify pass.**
Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: PASS (all existing + 3 new tests).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/store/nodeEditor.ts frontend/tests/unit/store/nodeEditor.spec.ts
git commit -m "feat(nodeEditor): redo via 3-mode recorder + re-push undo/redo on failure (E1)"
```

---

## Task 2: `useEditorShortcuts` composable

**Files:**
- Create: `frontend/src/composables/useEditorShortcuts.ts`
- Test: `frontend/tests/unit/composables/useEditorShortcuts.spec.ts`

- [ ] **Step 1: Write the failing test.** Create `frontend/tests/unit/composables/useEditorShortcuts.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'

vi.mock('@/api/nodes', () => ({
  listNodes: vi.fn(), patchNode: vi.fn(), createNode: vi.fn(),
  deleteNode: vi.fn(), batchUpdateNodes: vi.fn(), reorderNodes: vi.fn(),
}))

import { useEditorShortcuts } from '@/composables/useEditorShortcuts'
import { useNodeEditorStore } from '@/store/nodeEditor'

let editable = true
const Harness = defineComponent({
  setup() {
    useEditorShortcuts({ editable: () => editable })
    return () => h('div')
  },
})

function press(key: string, opts: Partial<KeyboardEventInit> = {}, target?: EventTarget): KeyboardEvent {
  const e = new KeyboardEvent('keydown', { key, ctrlKey: true, bubbles: true, cancelable: true, ...opts })
  ;(target ?? window).dispatchEvent(e)
  return e
}

beforeEach(() => { setActivePinia(createPinia()); editable = true })

describe('useEditorShortcuts (E1)', () => {
  it('Ctrl+Z → undo; Ctrl+Shift+Z and Ctrl+Y → redo', () => {
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    const redo = vi.spyOn(store, 'redo').mockResolvedValue()
    mount(Harness)
    press('z')
    expect(undo).toHaveBeenCalledOnce()
    press('z', { shiftKey: true })
    press('y')
    expect(redo).toHaveBeenCalledTimes(2)
  })

  it('Ctrl+1/2/3/0 set the selected node level', () => {
    const store = useNodeEditorStore()
    store.selectedId = 'a'
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    mount(Harness)
    press('1'); press('2'); press('3'); press('0')
    expect(setLevel.mock.calls).toEqual([['a', 1], ['a', 2], ['a', 3], ['a', null]])
  })

  it('ignores shortcuts when focus is in an input or contenteditable', () => {
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    mount(Harness)
    const input = document.createElement('input')
    document.body.appendChild(input)
    press('z', {}, input)
    const ce = document.createElement('div')
    ce.setAttribute('contenteditable', 'true')
    document.body.appendChild(ce)
    press('z', {}, ce)
    expect(undo).not.toHaveBeenCalled()
    input.remove(); ce.remove()
  })

  it('no-op when not editable', () => {
    editable = false
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    mount(Harness)
    press('z')
    expect(undo).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run; verify it fails.**
Run: `cd frontend && npx vitest run tests/unit/composables/useEditorShortcuts.spec.ts`
Expected: FAIL — module `@/composables/useEditorShortcuts` not found.

- [ ] **Step 3: Implement.** Create `frontend/src/composables/useEditorShortcuts.ts`:

```ts
import { onMounted, onUnmounted } from 'vue'
import { useNodeEditorStore } from '@/store/nodeEditor'

// 节点编辑器键盘快捷键（E1）：撤销/重做 + 设标题层级。
// 取代随旧编辑器删除的 useEditorKeyboard（节点模型版）。
// 聚焦守卫：焦点在 input/textarea/select 或 contenteditable（含 wangeditor 正文）内时
// 不接管，交还原生处理（含富文本自身的文本撤销）。
export function useEditorShortcuts(opts: { editable: () => boolean }): void {
  const store = useNodeEditorStore()

  function inEditableField(el: EventTarget | null): boolean {
    if (!(el instanceof HTMLElement)) return false
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return true
    if (el.isContentEditable) return true
    return el.closest('[contenteditable="true"]') !== null
  }

  function onKeydown(e: KeyboardEvent): void {
    if (!opts.editable()) return
    if (inEditableField(e.target)) return
    const mod = e.metaKey || e.ctrlKey
    if (!mod) return
    const key = e.key.toLowerCase()

    if (key === 'z' && !e.shiftKey) {
      e.preventDefault()
      void store.undo()
    } else if ((key === 'z' && e.shiftKey) || key === 'y') {
      e.preventDefault()
      void store.redo()
    } else if (key === '1' || key === '2' || key === '3' || key === '0') {
      if (!store.selectedId) return
      e.preventDefault()
      void store.setLevel(store.selectedId, key === '0' ? null : Number(key))
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))
}
```

- [ ] **Step 4: Run; verify pass.**
Run: `cd frontend && npx vitest run tests/unit/composables/useEditorShortcuts.spec.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/composables/useEditorShortcuts.ts frontend/tests/unit/composables/useEditorShortcuts.spec.ts
git commit -m "feat(fe): useEditorShortcuts composable (focus-guarded undo/redo + level keys) (E1)"
```

---

## Task 3: Wire composable + topbar redo button

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`
- Modify: `frontend/src/components/editor/EditorTopBar.vue`
- Test: `frontend/tests/unit/EditorTopBar.spec.ts`

- [ ] **Step 1: Write the failing topbar test.** Append to `frontend/tests/unit/EditorTopBar.spec.ts` (reuses its `setup()` + `flushPromises`):

```ts
  it('redo button: disabled when canRedo is false, triggers redo when enabled', async () => {
    const { w, node } = setup()
    const findRedo = () => w.findAll('button').find((b) => b.text().includes('重做'))
    expect(findRedo()).toBeTruthy()
    expect(findRedo()!.attributes('disabled')).toBeDefined()
    node.redoStack.push(async () => {})
    await flushPromises()
    const redo = vi.spyOn(node, 'redo').mockResolvedValue()
    await findRedo()!.trigger('click')
    expect(redo).toHaveBeenCalled()
  })
```

- [ ] **Step 2: Run; verify it fails.**
Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: FAIL — no button containing "重做".

- [ ] **Step 3: Implement the topbar.** In `frontend/src/components/editor/EditorTopBar.vue`:

(a) Add `'redo'` to the `MUTATING` set (so the autosave indicator counts it):
```ts
const MUTATING = new Set([
  'setLevel', 'setKind', 'toggleSkip', 'batchSetLevel', 'batchSetKind',
  'confirmReview', 'createNode', 'removeNode', 'reorder', 'updateBody', 'updateForm', 'undo', 'redo',
])
```
(b) Add the redo button immediately after the existing undo button (the `.etb-undo` `<el-button>`):
```html
      <el-button class="etb-redo" size="small" :disabled="!node.canRedo" title="重做 (节点编辑)" @click="node.redo()">↷ 重做</el-button>
```

- [ ] **Step 4: Wire the composable.** In `frontend/src/views/procedures/ProcedureEditorView.vue` `<script setup>`:

(a) Add the import (with the other `@/composables` imports):
```ts
import { useEditorShortcuts } from '@/composables/useEditorShortcuts'
```
(b) After the `const nodeStore = useNodeEditorStore()` line, add:
```ts
// 键盘快捷键（E1）：撤销/重做 + 设层级；仅可编辑时生效（/view 只读时 no-op）。
useEditorShortcuts({ editable: () => store.editable })
```

- [ ] **Step 5: Run; verify pass + type-check.**
Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts` → PASS.
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/views/procedures/ProcedureEditorView.vue frontend/src/components/editor/EditorTopBar.vue frontend/tests/unit/EditorTopBar.spec.ts
git commit -m "feat(fe/editor): wire useEditorShortcuts + add topbar redo button (E1)"
```

---

## Task 4: Final verification + browser smoke + finish

- [ ] **Step 1: Full frontend suite + type-check.**
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.
Run: `cd frontend && npm test` → all green (303 baseline + ~10 new tests; 0 failures).

- [ ] **Step 2: Browser smoke** (per `.claude/skills/running-smartsop-dev`). Launch backend + frontend, open a DRAFT procedure's `/edit`, and with chrome-devtools MCP verify:
  - Select a node, press `Ctrl+1` → its heading level becomes 1 (chapter); `Ctrl+0` → back to content.
  - Make a structural change (e.g. level), `Ctrl+Z` → undone; `Ctrl+Shift+Z` → redone. Topbar Undo/Redo buttons enable/disable to match.
  - Click into the body rich-text editor, type, `Ctrl+Z` → undoes **text** (not a structural undo) — confirms focus-aware guard.
  - Zero console errors.

- [ ] **Step 3: Finish the branch.** Use superpowers:finishing-a-development-branch (merge `--no-ff` to main).

---

## Self-Review Notes
- **Recorder correctness:** the inverse-of-inverse works because every undoable action recomputes `prev` from current state before pushing its inverse; running an inverse under `_recordMode='undoing'` routes its (freshly computed) inverse to `redoStack`. Verified by the Task 1 round-trip test.
- **No per-action edits:** only `_pushUndo`'s routing, `undo`, the new `redo`/`canRedo`, and the `_recordMode` field change — the 11 mutating actions' `this._pushUndo(...)` calls are untouched.
- **Focus guard** uses `instanceof HTMLElement` (so a `window`/`document` target doesn't throw on `.closest`) + `closest('[contenteditable="true"]')` (jsdom-testable; catches nested nodes inside the wangeditor body).
- **Caveats (documented in spec §3.3/§4):** stale re-pushed entry after a real 412 conflict; batch-partial-failure; macOS `Cmd+1..3` browser tab-switch when focus is in a field. Out of scope: Tab indent/outdent.
