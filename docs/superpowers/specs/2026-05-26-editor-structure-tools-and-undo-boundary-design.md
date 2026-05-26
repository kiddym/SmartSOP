# Editor Structure-Tools Grouping & Undo Boundary (Tier 1)

Date: 2026-05-26
Status: Approved (pending user spec review)

## Context

The procedure editor today has three controls whose placement and behavior trigger
a recurring source of UX confusion:

- **标记模式** (`markMode`) sits in `EditorTopBar.vue` (lines 49–53) alongside
  document-scoped actions (PDF 预览 / 保存 / 发布).
- **层级标定** (`layerMode`) sits in `ChapterTreePanel.vue` (lines 321–325) under
  the root add-buttons in the left panel.
- **撤销 / 重做** sits in `EditorTopBar.vue` (lines 43–46), covering snapshot-based
  local edits — but NOT delete-of-persisted-node, cross-parent move, type
  conversions on persisted nodes, or 标记应用. Those go straight to the backend
  (`store/procedureEditor.ts:668-725, 815-820`) and reload, so `Ctrl+Z` silently
  reverses some user actions and not others.

Two observations make a clean fix possible:

1. **标记模式 and 层级标定 are both mutually-exclusive tree-restructuring modes**
   (`store/procedureEditor.ts:728-735`). They belong together, near the tree.
2. **The codebase is mid-migration toward a unified local-draft model.**
   `applyLayerRoles` was recently moved fully local + undoable (commit
   `250bde7`); the save payload already carries `deleted_chapter_ids` /
   `deleted_step_ids` slots (`store/procedureEditor.ts:905-906`); the backend
   batch save already cascade-deletes a chapter's subtree
   (`backend/app/services/editor_service.py:49-102`); and the DnD layer already
   enforces cycle / depth-cap / Q25 sibling-type rules client-side before
   calling the store (`frontend/src/utils/treeDnd.ts:58-85`).

This spec covers two changes that finish that direction for the everyday cases.

## Goals

1. Co-locate 标记模式 and 层级标定 in the left panel, in their own row, so
   tree-restructuring tools are in one place near the tree they act on.
2. Make `Ctrl+Z` reliably reverse the everyday structural operations:
   add / delete / reorder / reparent / title edits / 层级应用. After this change,
   the boundary becomes:
   - **Top-toolbar undo** = the document's *structure* (add/remove/reorder/
     reparent/title/层级应用).
   - **In-panel rich-text undo** = text *inside* one node body (unchanged).
3. Keep the change frontend-only, leaning on payload slots, backend cascade, and
   client-side validation that already exist.

## Non-goals

- Persisted type conversions (章节↔步骤) remain immediate backend ops; folding
  them into undo needs a backend change to the batch-save contract and is
  deferred (Tier 2).
- 标记应用 (`applyMarks`) remains an immediate server-side resolution pass;
  folding it local would mean reimplementing the mark→structure resolution on
  the client. Deferred (Tier 2).
- Program metadata edits (name, description, etc.) stay out of the undo stack by
  design — the existing comment at `store/procedureEditor.ts:822` is correct:
  undo is tree-focused.
- No change to the rich-text editor's own undo. It remains the source of truth
  for content-inside-a-node.

## Part 1 — Group 标记模式 with 层级标定

### UI changes

**`frontend/src/components/editor/EditorTopBar.vue`**
- Remove the 标记模式 button at lines 49–53 (and its surrounding spacing) from
  the right-side toolbar group.
- Remove the now-unused `markMode`-related computed (if any) from this file.

**`frontend/src/components/editor/ChapterTreePanel.vue`**
- Below the existing root add-buttons row (+章节 / +内容 / +步骤), add a
  **结构工具** row that holds two toggle buttons in this order:
  `[标记模式] [层级标定]`.
- Each button reflects its store mode as `type="primary"` when active (mirror
  the existing 标记模式 active styling from `EditorTopBar.vue:50`).
- The existing `.layer-entry` div (lines 321–325) is folded into the new row;
  remove the standalone "层级标定" wrapper.
- Both buttons hide when `!editable` (same gate the root add-buttons already
  use).
- When `markMode` is on, the mark-bar (lines 326–335) continues to render below
  this row, exactly as today. When `layerMode` is on, `EditorLayerMarking`
  continues to replace the tree, exactly as today.

### Store changes

None. `toggleMarkMode` / `toggleLayerMode` already enforce mutual exclusion.

### Tests

- Update any existing test that asserts 标记模式 lives in `EditorTopBar` to
  assert its new location in `ChapterTreePanel`.
- Add: clicking 标记模式 while 层级标定 is on exits layer mode and enters mark
  mode (and vice versa). This already works in the store; the test pins the
  behavior in the new UI layout.

## Part 2 — Tier 1 undo boundary: defer delete + cross-parent move to save

### Snapshot changes

`store/procedureEditor.ts:53-59` — extend `Snapshot`:

```ts
interface Snapshot {
  chapters: EditorChapter[]
  steps: EditorStep[]
  dirtyChapters: string[]
  dirtySteps: string[]
  deletedChapterIds: string[]   // NEW
  deletedStepIds: string[]      // NEW
  metaDirty: boolean
}
```

Add corresponding state to the store:

```ts
deletedChapterIds: Set<string>
deletedStepIds: Set<string>
```

Initialize empty in state init, in `resetEditState`, and in `importDraft`
(also include them in `exportDraft` so sessionStorage drafts survive a reload
mid-edit). Clear them on `load` (alongside the existing undo/redo stack clear).

Update `snapshot()` and `restore(snap)` (lines 423–442) to copy these sets
in/out so undo/redo correctly reverses a deletion or a deletion-of-a-deletion.

### `deleteNode` (lines 668–679) — deferred local

New behavior, for both temp and persisted nodes:

```
deleteNode(id):
  pushUndo()
  for each persisted (real-id) chapter in collectSubtree(id):
    deletedChapterIds.add(realId)
  for each persisted (real-id) step orphaned by that subtree:
    deletedStepIds.add(realId)
  removeNodeLocal(id)
```

Notes:
- Temp-id descendants are dropped locally and NOT added to the deletion sets
  (they never existed on the server).
- `removeNodeLocal` (lines 633–650) already handles local removal + dirty-set
  cleanup + selection relocation; reuse it unchanged.
- We record top-level + all persisted descendants in the deletion sets even
  though the backend cascades on its own. Reasoning: the snapshot must be able
  to fully reverse the change, which means knowing exactly which ids were
  marked deleted. Recording all of them keeps undo/restore symmetric and
  defends against any future backend that no longer cascades.
- `ensureSaved()` is no longer needed in this path — the deletion travels via
  the batch save like any other dirty edit, and `applyIdMap` already handles
  temp→real id translation for surviving nodes.

### `moveCrossParent` (lines 715–725) — local

New behavior:

```
moveCrossParent(id, targetParentId, targetIndex):
  pushUndo()
  if id is a chapter:
    update chapter.parent_id = targetParentId
    recompute sort_order in source group and target group
    dirtyChapters.add(id) + all siblings whose sort_order changed
  else (step):
    update step.chapter_id = targetParentId
    recompute sort_order in source group and target group
    dirtySteps.add(id) + all siblings whose sort_order changed
```

Notes:
- Sort-order recomputation mirrors what `reorderWithin` (lines 610–630) already
  does for same-parent moves; factor a shared helper if it tightens the code,
  otherwise inline.
- The DnD handler (`treeDnd.ts:58-85` validation; `ChapterTreePanel.vue:195-218`
  drop dispatch) already prevents cycles, depth-cap violations, and Q25
  sibling-type violations BEFORE calling the store. The store does not need to
  re-validate; an invalid call is a programmer error.
- The confirmation dialog currently shown before `moveCrossParent` calls
  (`ChapterTreePanel.vue:205-217`) stays — it's a UX guard against accidental
  cross-parent drops, not a transactional safety net.

### `buildPayload` (lines 868–908) — wire up the deletion sets

Replace the two hardcoded empty arrays:

```ts
deleted_chapter_ids: [...this.deletedChapterIds],
deleted_step_ids:    [...this.deletedStepIds],
```

After `save()` succeeds, `resetEditState()` (lines 369–376) clears
`dirtyChapters` / `dirtySteps` / `metaDirty` / undo stacks. Extend it to also
clear `deletedChapterIds` and `deletedStepIds`.

### `isDirty` semantics

`isDirty` (lines 182–184) currently returns:

```ts
state.dirtyChapters.size > 0 || state.dirtySteps.size > 0 || state.metaDirty
```

Extend to include pending deletions so the 保存 button enables and
sessionStorage autosave fires:

```ts
state.dirtyChapters.size > 0
  || state.dirtySteps.size > 0
  || state.deletedChapterIds.size > 0
  || state.deletedStepIds.size > 0
  || state.metaDirty
```

### Tests

Unit (store):
- Deleting a persisted chapter pushes an undo snapshot, removes it locally,
  and adds its real id (and all persisted descendant ids) to
  `deletedChapterIds`. `undo()` restores both the chapters and the deletion
  set; `redo()` re-deletes.
- Deleting a temp chapter does NOT add anything to `deletedChapterIds`. Undo
  restores it.
- `moveCrossParent` updates `parent_id` (or `chapter_id` for steps),
  recomputes sort_order in both groups, and is undoable.
- `buildPayload` sends populated `deleted_chapter_ids` / `deleted_step_ids`
  after a delete; the arrays clear after `save()`.

Integration (already-existing DnD tests):
- Cross-parent drag drop no longer triggers an HTTP move call; the change
  appears as part of the next save's batch payload.
- Existing tests that assert `moveChapterApi` / `moveStepApi` get called on
  cross-parent drop must be rewritten to assert the local + dirty + save-batch
  path instead.

## Behavior changes & trade-offs

1. **Delete and cross-parent move are now pending until 保存.** A user who
   deletes a chapter and immediately navigates away (or closes the tab) leaves
   the chapter on the server. This is *consistent* with how every other edit
   already works (title edits, adds, reorders all wait for 保存), and
   sessionStorage autosave preserves the pending delete across reloads via
   `exportDraft`/`importDraft`. But it IS a semantics change for users used to
   "delete = gone instantly." The unsaved-changes indicator (the 未保存 chip in
   the top bar) already telegraphs this.

2. **Type conversions and 标记应用 still bypass undo.** That's the Tier 2
   honest gap. Document it in tooltips (e.g. the undo button tooltip becomes
   `撤销大纲结构改动 (类型转换 / 标记应用 不在范围内)` until Tier 2 lands).

3. **Backend `move_chapter` / `move_step` endpoints become unused by the editor.**
   Leave them in place — other callers (or future scripts) may use them. No
   dead-code removal in this change.

## Out of scope (Tier 2, separate spec)

- Make persisted type conversions (`convertToStep` / `convertRootToStep` /
  `convertToChapter`) local + undoable. Likely requires extending the batch
  save payload to express a type-change for a persisted id.
- Make `applyAllMarks` local + undoable, by porting the server-side mark→
  structure resolution to the client (similar in spirit to how `applyLayerRoles`
  already runs locally via `computeLayerUpdates`).

## Verified facts this design rests on

- `editor_service.py:49-102` — backend `_apply_deletes` cascade-walks `parent_id`
  to collect descendants, soft-deletes all chapters in the subtree, and
  soft-deletes every step in any deleted chapter.
- `treeDnd.ts:60-84` — client DnD validation blocks self-drop, subtree
  self-containment, inside-on-non-chapter, >3-level depth, and Q25 sibling-type
  violations.
- `procedureEditor.ts:905-906` — save payload already declares
  `deleted_chapter_ids` and `deleted_step_ids` (currently always empty).
- `procedureEditor.ts:736-775` — `applyLayerRoles` already operates fully local
  with snapshot-based undo (tag `'layer'`), establishing the pattern this spec
  extends to delete and cross-parent move.
