# E8 — Publish-Flow Feedback Polish — Design

**Date:** 2026-05-29
**Track:** Post-migration editor enhancements (follows E1–E7). Second slice of the decomposed "publish / version / PDF chrome polish" backlog item (PDF chrome shipped as E7; version-history polish remains).
**Status:** Design approved; ready for implementation plan.

## Goal

Give the publish action proper in-flight feedback: a loading state on the publish-confirm button during the `transitionProcedure` call (which also prevents double-submit), and a clearer success toast. Deliberately small.

## Background (current state)

- `EditorTopBar.vue` 发布 button only **opens** `PublishChecklistDialog` (`@publish="publishVisible = true"`) — instant, needs no loading.
- `PublishChecklistDialog.vue` shows a checklist; its 「确认发布 v{version}」 button binds `:disabled="!canConfirm"` and emits `confirm`. It has **no loading state**.
- `ProcedureEditorView.onPublishConfirm` (the gap): `await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)` then `publishVisible=false`, `ElMessage.success('已发布')`, `store.reload()` — **no loading flag**, so a slow publish gives no feedback and the confirm button can be clicked again.
- By contrast, **discard / copy / upgrade already have both a confirm and a loading flag**: `onDiscard` uses `ElMessageBox.prompt` (reason required) + `versionBusy`; `onCopyConfirm` uses `VersionActionDialog` (form + `:loading="versionBusy"`); `onUpgrade` uses `ElMessageBox.confirm` + `versionBusy`.

So this spec touches **only the publish path**.

## Approach

Follow the existing `versionBusy` / `downloading` pattern (a `ref(false)` toggled around the async call, bound to an Element Plus button's `:loading`). EP renders the spinner and blocks the click while `loading` is true, which doubles as the double-submit guard.

## Components & changes

### `frontend/src/components/editor/PublishChecklistDialog.vue`
- Add an optional prop: `const props = defineProps<{ modelValue: boolean; loading?: boolean }>()`.
- The confirm button (currently `<el-button type="primary" :disabled="!canConfirm" @click="emit('confirm')">确认发布 v{{ store.procedure?.version }}</el-button>`) gains `:loading="props.loading"`:
  ```html
  <el-button type="primary" :loading="props.loading" :disabled="!canConfirm" @click="emit('confirm')">
    确认发布 v{{ store.procedure?.version }}
  </el-button>
  ```
- No other change. (`emit('confirm')` stays; the parent owns the async call + the loading flag.)

### `frontend/src/views/procedures/ProcedureEditorView.vue`
- Add `const publishing = ref(false)` near the other flags (`publishVisible`, `versionBusy`, …).
- Rewrite `onPublishConfirm` to toggle it and include the version in the success toast:
  ```ts
  async function onPublishConfirm(): Promise<void> {
    const p = store.procedure
    if (!p || publishing.value) return
    publishing.value = true
    try {
      await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)
      publishVisible.value = false
      ElMessage.success(`已发布 v${p.version}`)
      await store.reload()
    } catch {
      /* 拦截器已提示；对话框保持打开以便重试 */
    } finally {
      publishing.value = false
    }
  }
  ```
- Pass the flag to the dialog: `<PublishChecklistDialog v-model="publishVisible" :loading="publishing" @confirm="onPublishConfirm" />`.

## Behaviour / error handling

- **Success:** confirm button spins → on resolve, dialog closes, toast `已发布 v{n}`, procedure reloads (status flips to PUBLISHED, editor becomes read-only via the existing `editable` getter).
- **Failure:** the http interceptor toasts the backend message (e.g. `REVIEW_PENDING`, `VERSION_CONFLICT`); the dialog **stays open** (we only set `publishVisible=false` on success) so the user can fix and retry; `publishing` resets in `finally`.
- **Double-submit:** `:loading` blocks the EP button click; the `if (publishing.value) return` guard is belt-and-suspenders.
- `p.version` is captured before the call (the toast reflects the version that was published, even though `reload()` will refresh `store.procedure` afterward).

## Testing

- **Unit — `frontend/tests/unit/PublishChecklistDialog.spec.ts`:** add a case — when mounted with `loading: true`, the 确认发布 button is in the loading state (Element Plus adds the `is-loading` class and sets the button disabled). Assert via the class or the button's disabled attribute. Existing checklist tests (review-pending blocks, required fields, node count, all-pass enables) stay green — note that the all-pass test asserts the button is *enabled*, which still holds when `loading` defaults to `undefined`/false.
- **No browser smoke** (à la E4): the publish *logic* is unchanged; this only adds an additive `publishing` flag, a `loading` prop binding, and a version string in the toast — all unit-covered or trivial. The publish flow itself is already exercised in the app.
- vue-tsc clean; full frontend suite green.

## Non-goals (YAGNI)

- No discard / copy / upgrade changes (each already confirms + shows loading).
- No loading on the EditorTopBar 发布 button (it only opens the dialog).
- No store-action refactor (publish stays in the View, consistent with discard/copy/upgrade).
- Version-history polish (the third backlog slice) is a separate spec.
