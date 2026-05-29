# E8 — Publish-Flow Feedback Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a loading state to the publish-confirm button during `transitionProcedure` (also blocks double-submit) and a clearer `已发布 v{n}` success toast. Publish-only — discard/copy/upgrade already confirm + show loading.

**Architecture:** Follow the existing `versionBusy`/`downloading` pattern — a `ref(false)` toggled around the async call, bound to an Element Plus button's `:loading`. `PublishChecklistDialog` gains a `loading?` prop; `ProcedureEditorView` owns the flag. Spec: `docs/superpowers/specs/2026-05-29-editor-e8-publish-feedback-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, vitest + @vue/test-utils, vue-tsc. No new dependency.

---

## File Structure

- **Modify** `frontend/src/components/editor/PublishChecklistDialog.vue` — add `loading?` prop + `:loading` on the confirm button.
- **Modify** `frontend/tests/unit/PublishChecklistDialog.spec.ts` — extend `setup` with a `loading` arg + add a loading-state test.
- **Modify** `frontend/src/views/procedures/ProcedureEditorView.vue` — `publishing` ref, rewritten `onPublishConfirm`, dialog `:loading` wiring.

No backend change.

---

## Task 1: `PublishChecklistDialog` loading prop

**Files:**
- Modify: `frontend/src/components/editor/PublishChecklistDialog.vue:8` (props) and the confirm button (lines 62-64)
- Test: `frontend/tests/unit/PublishChecklistDialog.spec.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/tests/unit/PublishChecklistDialog.spec.ts`, extend the `setup` helper to accept a `loading` arg. Change its signature line:
```ts
function setup(reviewCount: number, nodeCount = reviewCount + 1, loading = false) {
```
and its mount `props` line:
```ts
    props: { modelValue: true, loading },
```
Then append this test inside the `describe('PublishChecklistDialog 待确认拦截', ...)` block (after the "所有检查通过" test):
```ts
  it('loading prop → 确认发布 button shows the loading state and is click-blocked', async () => {
    setup(0, 1, true) // all checks pass + loading
    await nextTick()
    await flushPromises()
    const confirm = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('确认发布'),
    )
    expect(confirm?.classList.contains('is-loading')).toBe(true)
    expect(confirm?.disabled).toBe(true) // Element Plus disables a loading button → no double-submit
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/PublishChecklistDialog.spec.ts`
Expected: the new test FAILS (the confirm button has no `is-loading` class — the prop isn't wired yet). The four existing tests still pass.

- [ ] **Step 3: Add the prop + button binding**

In `frontend/src/components/editor/PublishChecklistDialog.vue`, change the props line (line 8) from:
```ts
const props = defineProps<{ modelValue: boolean }>()
```
to:
```ts
const props = defineProps<{ modelValue: boolean; loading?: boolean }>()
```
Then change the confirm button (lines 62-64) to add `:loading="props.loading"`:
```html
      <el-button type="primary" :loading="props.loading" :disabled="!canConfirm" @click="emit('confirm')">
        确认发布 v{{ store.procedure?.version }}
      </el-button>
```
(Nothing else changes — `emit('confirm')` stays; the parent owns the async call.)

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/PublishChecklistDialog.spec.ts`
Expected: all 5 tests PASS (4 existing + the new loading test). The "所有检查通过 → 确认按钮可用" test still passes because `loading` defaults to `false` there.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/PublishChecklistDialog.vue frontend/tests/unit/PublishChecklistDialog.spec.ts
git commit -m "feat(editor): PublishChecklistDialog loading prop on confirm button (E8 Task 1)"
```

---

## Task 2: `ProcedureEditorView` publishing flag + version toast

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue` (flags ~lines 37-40, `onPublishConfirm` ~lines 52-63, dialog wiring ~line 244)

Verified by vue-tsc + the full vitest suite staying green (including `ProcedureEditorView.switch.spec.ts`, which mounts the View). The user-visible loading effect is already covered by Task 1's dialog test; this task is the plumbing that supplies the flag.

- [ ] **Step 1: Read the file and locate the three anchors**

Open `frontend/src/views/procedures/ProcedureEditorView.vue`. Confirm these exist:
- the flag block: `const publishVisible = ref(false)` … `const versionBusy = ref(false)`
- the current `onPublishConfirm` (below)
- the dialog line: `<PublishChecklistDialog v-model="publishVisible" @confirm="onPublishConfirm" />`

- [ ] **Step 2: Add the `publishing` flag**

Right after `const publishVisible = ref(false)`, add:
```ts
const publishing = ref(false)
```

- [ ] **Step 3: Rewrite `onPublishConfirm`**

Replace the current handler:
```ts
async function onPublishConfirm(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)
    publishVisible.value = false
    ElMessage.success('已发布')
    await store.reload()
  } catch {
    /* 拦截器已提示 */
  }
}
```
with:
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

- [ ] **Step 4: Wire the flag into the dialog**

Change the dialog line from:
```html
        <PublishChecklistDialog v-model="publishVisible" @confirm="onPublishConfirm" />
```
to:
```html
        <PublishChecklistDialog v-model="publishVisible" :loading="publishing" @confirm="onPublishConfirm" />
```

- [ ] **Step 5: Type check**

Run: `cd frontend && npm run typecheck`
Expected: vue-tsc no errors.

- [ ] **Step 6: Full suite — green**

Run: `cd frontend && npm test`
Expected: 0 failures (the 5 PublishChecklistDialog tests + the View `switch.spec` + everything else). The View change is additive plumbing; no test mounts the publish *flow*, so nothing breaks.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/procedures/ProcedureEditorView.vue
git commit -m "feat(editor): publishing loading flag + version success toast in ProcedureEditorView (E8 Task 2)"
```

---

## Self-Review

**Spec coverage:**
- `loading?` prop on dialog + `:loading` on confirm button → Task 1. ✓
- `publishing` ref toggled around `transitionProcedure` (try/finally) + double-submit guard (`if publishing.value return` + EP loading blocks click) → Task 2 Steps 2-3. ✓
- `已发布 v{version}` toast (version captured pre-call) → Task 2 Step 3. ✓
- Failure keeps dialog open (only `publishVisible=false` on success) → preserved in the rewrite. ✓
- Dialog `:loading="publishing"` wiring → Task 2 Step 4. ✓
- No discard/copy/upgrade/top-bar/store changes → no task touches them. ✓

**Placeholder scan:** none — full before/after code for every edit.

**Type consistency:** `loading?: boolean` prop matches `:loading="publishing"` (a `ref<boolean>`). `props.loading` used in the dialog template. `publishing` declared with `ref` (already imported in the View). The existing all-pass dialog test stays valid because `loading` defaults to `false`.
