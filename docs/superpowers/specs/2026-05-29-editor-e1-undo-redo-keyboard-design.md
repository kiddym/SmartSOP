# Editor Enhancement E1 — Undo/Redo + Keyboard Shortcuts (Design)

> First of the deferred node-editor enhancements (post unified-node-model migration, main @ `930c2a7`). Frontend-only.

**Date:** 2026-05-29
**Status:** Design (approved for spec write)

## 1. Goal

Add **redo** to the `nodeEditor` store (the `redoStack` field exists but is unused), fix the known **silent undo-failure** bug, and add **focus-aware keyboard shortcuts** (undo/redo + heading-level keys) to the node editor.

## 2. Decisions (from brainstorming)

1. **Focus-aware undo:** when focus is inside the body rich-text editor (or any input), `Ctrl/Cmd+Z` does the editor's **native text undo**; when focus is in the tree/shell, it does **node-store structural undo**. Achieved by a focus guard in the keyboard handler — we simply don't act when focus is in an editable field, letting wangeditor/inputs own their history. The toolbar Undo/Redo buttons are always structural.
2. **Shortcut set:** `Ctrl/Cmd+Z` undo · `Ctrl/Cmd+Shift+Z` and `Ctrl+Y` redo · `Ctrl/Cmd+1/2/3` set selected node heading level 1/2/3 · `Ctrl/Cmd+0` set to content (`heading_level=null`). (Tab indent/outdent deferred.)
3. **Failure handling:** undo/redo no longer silently drop the entry on inverse failure — see §3.3.

## 3. Component 1 — Redo + robust undo (`frontend/src/store/nodeEditor.ts`)

### 3.1 Recorder mode
Replace the `_suppressUndo: boolean` state field with **`_recordMode: 'normal' | 'undoing' | 'redoing'`** (default `'normal'`). Keep `undoStack` / `redoStack` / the per-action `this._pushUndo(inverse)` calls **unchanged** — only `_pushUndo`'s routing changes:

```ts
_pushUndo(inverse: InverseOp): void {
  if (this._recordMode === 'normal') {
    this.undoStack.push(inverse)
    this.redoStack = []                 // any new user op invalidates redo
  } else if (this._recordMode === 'undoing') {
    this.redoStack.push(inverse)        // capture the redo op
  } else {                              // 'redoing'
    this.undoStack.push(inverse)        // capture the re-undo op (do NOT clear redo)
  }
  if (this.undoStack.length > 100) this.undoStack.shift()
  if (this.redoStack.length > 100) this.redoStack.shift()
}
```

This works because each inverse op is an **action call that recomputes `prev` from current state** (e.g. `setLevel(id, prev)`); running an inverse therefore produces *its own* inverse, which is exactly the redo (or re-undo) op. No per-action changes are needed.

### 3.2 `redo()` + `canRedo`
```ts
canRedo(state): boolean { return state.redoStack.length > 0 }   // getter
```
`undo()` and `redo()` become symmetric: pop from the source stack, set `_recordMode`, await the inverse (which routes its own inverse to the *other* stack), reset mode in `finally`.

### 3.3 Failure handling (fixes the silent-loss bug)
Today `undo()` pops *then* awaits; if the inverse throws (412 conflict, node deleted, network), the entry is silently lost and no error is shown. New behavior for **both** `undo()` and `redo()`:

```ts
async undo(): Promise<void> {
  const inverse = this.undoStack.pop()
  if (!inverse) return
  this._recordMode = 'undoing'
  try {
    await inverse()                     // on success, routes redo op to redoStack
  } catch {
    this.undoStack.push(inverse)        // re-push: do NOT silently drop it
    await this._refetch().catch(() => {})  // resync optimistic view to server truth
  } finally {
    this._recordMode = 'normal'
  }
}
```
- The failing api call already surfaces a toast via the global http interceptor (codebase convention), so the store does **not** import `ElMessage` (keeps it unit-testable, no double-toast).
- `redo()` is identical with `redoStack` / `'redoing'`.
- **Known v1 limitations (documented, not fixed here):** (a) after a real 412 *conflict* the re-pushed entry's captured `prev` is stale, so retrying it will fail again — acceptable (no data loss, view is resynced, user can stop); (b) a *batch* inverse (multi-select level/kind) that fails mid-loop may leave a partial redo entry — rare, accepted for v1.

## 4. Component 2 — Keyboard shortcuts (`frontend/src/composables/useEditorShortcuts.ts`, NEW)

Replaces the deleted `useEditorKeyboard`, node-model-aware. A composable that attaches a `keydown` listener on `window` on mount and removes it on unmount.

**Signature:** `useEditorShortcuts(opts: { editable: () => boolean })` — reads the `nodeEditor` store internally via `useNodeEditorStore()`.

**Focus guard** (the core of "focus-aware"):
```ts
const el = e.target as HTMLElement | null
if (!el) return
if (el.isContentEditable || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
  return  // let the field / wangeditor own its keys (incl. native text undo)
}
```
`isContentEditable` is true for any element inside the wangeditor body, so no editor-specific class is needed.

**Mappings** (`mod = e.metaKey || e.ctrlKey`; only when `opts.editable()` is true):
| Keys | Action |
|---|---|
| `mod+Z` (no shift) | `store.undo()` |
| `mod+Shift+Z` or `mod+Y` | `store.redo()` |
| `mod+1` / `mod+2` / `mod+3` | `store.setLevel(store.selectedId, 1/2/3)` (only if `selectedId`) |
| `mod+0` | `store.setLevel(store.selectedId, null)` |

Each handled key calls `e.preventDefault()`. When `opts.editable()` is false (`/view`) the handler is a no-op.

**Caveat (documented):** on macOS Chrome `Cmd+1..3` switches browser tabs; our `preventDefault()` overrides it only when our handler is active (focus outside an editable field). When focus is in a field we defer entirely, so `Cmd+1..3` may hit the browser there — acceptable for v1.

**Wiring:** call `useEditorShortcuts({ editable: () => store.editable })` at the top of `ProcedureEditorView.vue`'s `<script setup>` (alongside the existing store setup). The composable handles its own add/removeEventListener lifecycle.

## 5. Component 3 — Topbar redo button (`frontend/src/components/editor/EditorTopBar.vue`)

- Add a Redo button immediately after the existing Undo button (line ~60), mirroring it: `:disabled="!node.canRedo"`, `@click="node.redo()"`, label `↷ 重做`, class `etb-redo`.
- Add `'redo'` to the `MUTATING` set (line ~33) so the autosave indicator counts it.

## 6. Error handling
- Inverse-op api failures: surfaced by the global http interceptor (existing). Store re-syncs via `_refetch()` (§3.3).
- Readonly (`/view`): no shortcuts fire; topbar buttons already hidden (the `v-if="store.editable"` block).

## 7. Testing
- **`tests/unit/store/nodeEditor.*.spec.ts`** (extend/add): with `@/api/nodes` mocked —
  - do → undo → redo round-trips for `setLevel`, `setKind`, `toggleSkip`, `createNode`, `removeNode`, `reorder`, `updateBody` (state matches original after redo).
  - a new mutating op after undo **clears** `redoStack` (`canRedo` false).
  - undo/redo with the api mock rejecting → entry **re-pushed** (`canUndo`/`canRedo` still true) and `listNodes` (refetch) called; no silent loss.
  - `canRedo` getter.
- **`tests/unit/composables/useEditorShortcuts.spec.ts`** (NEW): mount a tiny harness (or call the handler directly) —
  - guard: `keydown` with target `INPUT`/`contenteditable` → no store action, no `preventDefault`.
  - `mod+Z`→`undo`, `mod+Shift+Z`/`mod+Y`→`redo`, `mod+1/2/3`→`setLevel(selectedId, n)`, `mod+0`→`setLevel(selectedId, null)`; `preventDefault` called.
  - `editable=false` → all no-ops.
- **`tests/unit/EditorTopBar.spec.ts`** (extend): redo button disabled when `!canRedo`, enabled + emits `redo` on click.

## 8. Files
| File | Change |
|---|---|
| `frontend/src/store/nodeEditor.ts` | `_recordMode` (replaces `_suppressUndo`); `_pushUndo` routing; `redo()`; `canRedo`; undo/redo failure re-push + refetch |
| `frontend/src/composables/useEditorShortcuts.ts` | **new** — focus-guarded keydown → undo/redo/level |
| `frontend/src/views/procedures/ProcedureEditorView.vue` | call `useEditorShortcuts({ editable: () => store.editable })` |
| `frontend/src/components/editor/EditorTopBar.vue` | redo button + add `'redo'` to `MUTATING` |
| 3 test files | as in §7 |

## 9. Out of scope
- `Tab`/`Shift+Tab` indent-outdent (deferred to a later enhancement).
- Other deferred items (virtual list, cascading multi-select, markdown, publish/version/PDF chrome, cross-tab 412) — separate specs.
- No backend change (purely frontend).
