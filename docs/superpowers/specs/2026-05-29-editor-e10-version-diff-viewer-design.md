# E10 — Version Diff / Compare Viewer (MVP) — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. First **feature** (not polish) after the E1–E9 enhancement series.
**Status:** Design approved; ready for implementation plan.

## Goal

Let a user compare an older version of a procedure against the group's current version and see, at the node level, what changed — added / removed / modified / unchanged — with modified nodes showing their old vs new body side by side. Frontend-only; no backend or schema change.

## Feasibility findings (from exploration)

- Each version is its **own `Procedure` row** (same `procedure_group_id`, distinct `id`) owning its **own full `ProcedureNode` tree**. Any version's tree is readable today via `GET /procedures/{id}/nodes` (`listNodes`) and `GET /procedures/{id}` — **no status gate** (archived versions read fine).
- **Nodes are cloned with new UUIDs** on version fork (`version_flow_service._clone_tree` → `id=new_uuid()`), so **node ids cannot match across versions**. Matching must use a content/position signature.
- Dev data has many identically-titled "未命名章节" nodes, and content nodes have empty `code`, so neither title-alone nor code-alone is a reliable key — a **sequence diff (LCS) over a `code || title` signature** is the pragmatic choice.
- No diff library exists in the repo; scale is trivial (tens–low-hundreds of nodes), so diffing happens **in the browser** with a small pure module — no dependency added.

## Components

### 1. Pure module — `frontend/src/components/version/versionDiff.ts`

```ts
import type { Node } from '@/types/node'
import { nodeTitle } from '@/utils/nodeTree'

export type DiffStatus = 'unchanged' | 'modified' | 'added' | 'removed'
export interface DiffRow {
  status: DiffStatus
  old: Node | null
  new: Node | null
  changedFields: string[] // human labels, only for 'modified'
}

// Match signature: stable heading numbering when present, else first-line text.
export function nodeSignature(n: Node): string { /* return n.code.trim() || nodeTitle(n) */ }

// Which persistent fields differ between a matched pair (labels: 正文/层级/类型/跳号/执行表单/附件).
export function changedFields(a: Node, b: Node): string[]

// Pure: LCS over signatures of two sort_order-ordered trees → DiffRow[] in new-version order
// (removed rows interleaved at their old position). O(n·m), trivial at this scale.
export function diffVersions(oldNodes: Node[], newNodes: Node[]): DiffRow[]
```

- `changedFields` compares `body`, `heading_level`, `kind`, `skip_numbering`, and (via stable JSON compare) `input_schema` + `attachment_marks`. `code` is part of the signature so it's equal within a matched pair.
- `diffVersions`: build signature arrays; LCS DP + backtrack to a keep/delete/insert script; emit `DiffRow`s — `keep` pairs → `unchanged` (empty `changedFields`) or `modified` (non-empty); `delete` → `removed`; `insert` → `added`.

### 2. `frontend/src/components/version/VersionCompareDialog.vue` (glue)

- Props: `{ modelValue: boolean; oldId: string; newId: string; oldVersion: number; newVersion: number }`; emits `update:modelValue`.
- `watch(modelValue → true)`: `loading=true`; `Promise.all([listNodes(oldId), listNodes(newId)])`; `rows = diffVersions(old, new)`; `loading=false` (errors → close; interceptor toasts).
- State: `onlyChanges = ref(true)`; `visibleRows = computed(() => onlyChanges.value ? rows.filter(r => r.status !== 'unchanged') : rows)`; `summary = computed` → counts of added/removed/modified.
- Template (fullscreen `el-dialog`, `append-to-body`, like `PdfPreviewDialog`):
  - Header: `版本对比 · v{oldVersion} → v{newVersion}`, summary chips `+{added} · −{removed} · ~{modified}`, a 「只看变更」 `el-switch`, 关闭.
  - Body (`v-loading`): one row per `visibleRows` item — a status glyph (`= ~ + −`) with a status class, the node `code`, its `nodeTitle`, and `changedFields` chips. A `modified` row is expandable → two columns `旧 v{old}` | `新 v{new}` each rendering the body via `v-html` (body HTML is trusted app-wide). `added` shows the new body; `removed` shows the old body.
  - Empty: when `visibleRows` is empty under 只看变更 → `el-empty` "两个版本内容一致".

### 3. Entry — `frontend/src/components/version/VersionListPanel.vue`

- Add `(e: 'compare', payload: { oldId: string; oldVersion: number; newId: string; newVersion: number }): void` to `defineEmits`.
- `const current = computed(() => items.value.find((i) => i.is_current))`.
- On each row where `!v.is_current && current`, add a 「对比当前」 `el-button` (text, small) → `emit('compare', { oldId: v.id, oldVersion: v.version, newId: current.value!.id, newVersion: current.value!.version })`.

### 4. Host — `frontend/src/views/procedures/ProcedureEditorView.vue`

- Add `const compareVisible = ref(false)` + `const comparePair = ref<{ oldId: string; oldVersion: number; newId: string; newVersion: number } | null>(null)`.
- Where `VersionListPanel` is rendered (history tab), bind `@compare="(p) => { comparePair = p; compareVisible = true }"`.
- Render `<VersionCompareDialog v-if="comparePair" v-model="compareVisible" v-bind="comparePair" />`.

## Data flow

```
VersionListPanel 「对比当前」 → @compare{oldId,newId,oldVersion,newVersion}
  → ProcedureEditorView sets comparePair + compareVisible=true
  → VersionCompareDialog open → listNodes(oldId)+listNodes(newId) → diffVersions() → DiffRow[]
  → unified list (filterable 只看变更); click a ~ row → 旧正文 | 新正文 (v-html)
```

## Error handling / edge cases

- Either `listNodes` rejects → dialog closes, interceptor toasts; `loading` cleared in `finally`.
- A version with 0 nodes → all rows added/removed; summary reflects it.
- `input_schema`/`attachment_marks` compared via stable stringify (key order is stable from the API); a false "modified" from key-order drift is acceptable and rare.
- **Accepted caveat:** a first-line/title edit on a content node (or a heading renumbered by a structural change) changes its signature → shows as `removed` + `added` rather than `modified`. Its content did change, so the diff still reads correctly; a rename/move detector is a non-goal.

## Testing

- **Unit `frontend/tests/unit/version/versionDiff.spec.ts`** (pure): `nodeSignature` (code present → code; empty code → title); `changedFields` (each field); `diffVersions` — identical trees → all `unchanged`; an added node; a removed node; a body-modified node → `modified` + `changedFields:['正文']`; duplicate-title content matched positionally; empty old or new.
- **`frontend/tests/unit/VersionCompareDialog.spec.ts`**: mock `@/api/nodes` `listNodes` to return two trees → on open, rows render with the right markers + summary counts; 「只看变更」 hides `unchanged`. (Mount in jsdom like existing dialog specs; mock `listNodes` via `vi.hoisted`.)
- **`frontend/tests/unit/VersionListPanel.spec.ts`**: a non-current row shows 「对比当前」 and clicking it emits `compare` with the correct `{oldId,newId,...}`; the current row does not show it.
- **Browser smoke: best-effort** — needs a group with ≥2 versions. Dev data is mostly single-version drafts; if practical, stage a v2 via the upgrade flow and compare; otherwise rely on the pure + dialog unit coverage and note it. (The diff is pure-tested; the dialog is jsdom-tested.)
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Char-level text highlighting inside bodies (deferred fork); arbitrary two-version selection (deferred fork — MVP is older-vs-current); rename/move detection; side-by-side full-tree rendering; a backend diff endpoint; any schema change; attachment-binary diff.
