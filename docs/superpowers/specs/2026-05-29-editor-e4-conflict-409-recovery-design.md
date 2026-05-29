# E4 — Cross-tab 409 Conflict Recovery (Node Editor) — Design

**Date:** 2026-05-29
**Track:** Post-migration node-editor enhancements (see `editor-enhancements` memory; follows E1 undo/redo, E2 cascading multi-select, E3 Tab indent/outdent).
**Status:** Design approved; ready for implementation plan.

## Goal

When another tab or user changes a node first, a node-body/form save currently gets stuck in a permanent 409 loop and the undo/redo history can clobber the concurrent change with stale data. Make node-editor optimistic-concurrency conflicts **recover automatically (reload-wins)** with a clear, node-specific notice, and fix the E1 stale-undo caveat as a side effect.

## Reframing: it's 409, not 412

In this codebase the two status codes mean different things (`backend/app/services/optimistic_lock.py`):

- **412 `IF_MATCH_REQUIRED`** — the request omitted/`malformed` the `If-Match` header. This is a *client programming error*, not a cross-tab race. It should never happen from the real UI (the frontend always sends `If-Match`).
- **409 `VERSION_CONFLICT`** — `If-Match` was sent but the stored `revision` no longer matches ("远程版本已变更，请加载最新版本后重试"). **This is the real cross-tab conflict** and the thing we are refining.

The backlog item historically called "cross-tab 412" is therefore really **409 recovery**.

## Current behavior (the two gaps)

Revision is **per-node** (`ProcedureNode.revision`, default 1, bumped on each successful `PATCH /api/v1/nodes/{id}`). Only two store actions send `If-Match` and can therefore receive a 409:

- `nodeEditor.updateBody(id, body)` — `api.patchNode(id, { body }, node.revision)`
- `nodeEditor.updateForm(id, schema, marks)` — `api.patchNode(id, { input_schema, attachment_marks }, node.revision)`

Every other mutating action (`setLevel`, `setKind`, `batchSetKind`, `reorder`, `createNode`, `removeNode`) goes through the **batch / reorder / create / delete** endpoints, which do **not** require `If-Match` and **cannot** 409 (last-write-wins by design).

**Gap 1 — direct edits get stuck.** On 409, `updateBody`/`updateForm` let the exception propagate; the global axios interceptor (`frontend/src/api/http.ts`) shows the generic backend message but the store **never refetches**. `node.revision` stays stale, so every subsequent autosave PATCH re-fails 409 forever until a full page reload.

**Gap 2 — E1 stale-undo caveat.** `undo()`/`redo()` (`nodeEditor.ts`) catch an inverse failure, **re-push** the entry and `_refetch()`. The re-pushed inverse still holds the value captured at original-action time. After a concurrent change that value is stale; on retry it would either re-fail 409 or clobber the concurrent change with old data.

## Approach (chosen: A)

Put recovery **inside the only two actions that can 409**, via one shared store helper. No global interceptor change.

- **A — recovery in `updateBody`/`updateForm` + `_recoverFromConflict` helper. ✅ chosen.** Local blast radius; undo/redo inherit the fix for free because their inverse ops call these same two actions.
- **B — suppress 409 globally in the http interceptor.** Fewest LOC but wrongly silences 409 on procedure publish/transition and settings, where there is *no* auto-reload → regressions. Rejected.
- **C — per-action inline try/catch everywhere.** DRY violation; most actions cannot even 409. Rejected.

**Recovery UX (decided): reload-wins (auto).** On 409 the affected node is refetched, its revision refreshed, the now-untrustworthy undo/redo history is cleared, and a node-specific warning toast is shown. The user's unsaved local change is discarded (server content wins). Appropriate for a low-conflict internal tool; never clobbers another editor's work.

## Components & changes

### 1. Detection + toast-suppression — `frontend/src/api/http.ts`
- Export `isVersionConflict(err: unknown): boolean` → true when `err.response?.status === 409` **or** `err.response?.data?.detail?.code === 'VERSION_CONFLICT'`.
- (Optional helper, only if convenient) `errorMessage(err): string | undefined` → `err.response?.data?.detail?.message`, reused by the non-conflict branch.

### 2. API layer — `frontend/src/api/nodes.ts`
- `patchNode` adds `skipErrorToast: true` to its request config (alongside the existing `If-Match` header) so the global interceptor stays silent for both patch calls; the store owns **all** messaging for these two actions. `skipErrorToast` is already honored by the interceptor.

### 3. Store helper + action changes — `frontend/src/store/nodeEditor.ts`
- New private action:
  ```ts
  async _recoverFromConflict(id: string): Promise<void> {
    await this._refetch().catch(() => {})   // full list — a concurrent edit may renumber siblings
    this.undoStack = []                      // captured inverses now reference a dead state
    this.redoStack = []
    const label = nodeLabel(this.nodeMap.get(id))   // server's latest, or fallback
    ElMessage.warning(`「${label}」已被他人修改，已加载最新版本，你刚才的未保存改动已丢弃`)
  }
  ```
  `nodeLabel(node)` derives a short human label (reuse the existing body→title helper used by the tree/PDF if present; otherwise node `code`, otherwise "该节点"). The exact helper is identified during planning.
- `updateBody` / `updateForm` wrap the patch:
  ```ts
  try {
    updated = await api.patchNode(/* ... */)
  } catch (err) {
    if (isVersionConflict(err)) { await this._recoverFromConflict(id); return }  // reload-wins
    ElMessage.error(errorMessage(err) ?? '保存失败，请重试')                       // transient
    throw err                                                                     // let undo()/redo() re-push
  }
  this._replaceNode(updated)
  this._pushUndo(/* ... */)
  ```
  The existing no-op guard (`if (body === node.body) return`) stays.

### 4. Undo/redo — `frontend/src/store/nodeEditor.ts` (no structural change)
`undo()`/`redo()` keep their existing transient-failure path (re-push entry + `_refetch()`). A real 409 no longer reaches that catch: the inverse (`updateBody`/`updateForm`) self-recovers via `_recoverFromConflict`, which clears both stacks and returns normally. The popped entry is intentionally not re-pushed (history is invalid after a concurrent change). This fixes the E1 caveat without touching the undo/redo control flow.

## Data flow (conflict case)

```
user edits body ─▶ debounced updateBody(id, body)
   └─▶ api.patchNode(id,{body},staleRev)  ── 409 VERSION_CONFLICT ──┐
                                                                     ▼
   isVersionConflict(err) === true ─▶ _recoverFromConflict(id)
                                         ├─ _refetch()            (node + siblings ← server)
                                         ├─ undoStack = []        (history invalidated)
                                         ├─ redoStack = []
                                         └─ ElMessage.warning(「label」已被他人修改…)
   return (no _pushUndo)
```

Undo path is identical: `undo()` pops an inverse, calls `updateBody`/`updateForm`, which 409s and self-recovers; `undo()` sees no error and does not re-push.

## Error handling

- **409 (`VERSION_CONFLICT`)** → reload-wins recovery + node-specific warning. Never rethrown.
- **Non-409 transient/validation error on patch** → store shows `detail.message` (or "保存失败，请重试") and **rethrows**, preserving E1's re-push-on-transient-failure behavior for undo/redo.
- **`_refetch()` failure inside recovery** → swallowed (`.catch(() => {})`); the warning still fires so the user knows to reload manually. (Matches the existing `_refetch().catch(() => {})` pattern.)

## Testing — `frontend/tests/unit/store/nodeEditor.spec.ts`

1. `updateBody` on 409 → `_refetch` called, `undoStack` and `redoStack` both emptied, warning toast shown, **no** undo entry pushed.
2. `updateBody` on a non-409 error → error toast shown and the error **rethrown** (transient path intact).
3. `undo()` whose inverse `updateBody` hits 409 → stacks cleared (entry **not** re-pushed), node refetched. (Direct E1-caveat regression test.)
4. `updateForm` on 409 → same recovery as (1).
5. Existing redo / robust-undo / no-op-guard tests stay green.
6. (Optional) unit test for `isVersionConflict` truth table (409 status, `VERSION_CONFLICT` code, neither).

vue-tsc must stay clean; full frontend suite green.

## Non-goals (YAGNI)

- Batch/reorder last-write-wins (no optimistic lock by design) — unchanged.
- Procedure-metadata `_flushMeta` — already silently reloads on error; only the message differs. Out of scope.
- Settings view 409 — its handler branches only on `412`; a real concurrent settings change returns 409 and shows the generic toast. Documented here as a separate latent gap, **not** fixed in E4.
- Merge / force-overwrite / "keep my version" — explicitly rejected in favor of reload-wins.
- Realtime conflict indicators (websockets, presence, lock icons).

## Accepted caveat

If a conflict lands mid-typing, reload-wins will replace the editor body out from under the user. Acceptable for a rare-conflict internal tool; the warning toast explains what happened.
