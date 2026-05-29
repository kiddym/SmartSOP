# E4 — Node-Editor 409 Conflict Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When another tab/user changes a node first, node-body/form saves recover automatically (reload-wins) with a clear node-specific notice instead of getting stuck in a permanent 409 loop — and fix the E1 stale-undo caveat as a side effect.

**Architecture:** The only two store actions that send `If-Match` and can 409 are `updateBody` and `updateForm`. Put recovery inside them via one shared `_recoverFromConflict` helper (refetch + clear undo/redo + warn). Undo/redo inherit the fix because their inverses call those same two actions. No global interceptor change. Spec: `docs/superpowers/specs/2026-05-29-editor-e4-conflict-409-recovery-design.md`.

**Tech Stack:** Vue 3 / Pinia options store, axios, Element Plus `ElMessage`, vitest + @vue/test-utils, vue-tsc.

---

## File Structure

- **Modify** `frontend/src/api/http.ts` — add `isVersionConflict(err)` + `errorMessage(err)` exported helpers.
- **Modify** `frontend/src/api/nodes.ts` — `patchNode` sends `skipErrorToast: true` (store owns all messaging for patch).
- **Modify** `frontend/src/store/nodeEditor.ts` — add `_recoverFromConflict`; wrap `updateBody`/`updateForm` patch in try/catch.
- **Create** `frontend/tests/unit/api/http.spec.ts` — unit-test `isVersionConflict` / `errorMessage`.
- **Modify** `frontend/tests/unit/store/nodeEditor.spec.ts` — mock `element-plus` `ElMessage`; add the E4 recovery + E1-fix regression tests.

No backend change (the backend already returns 409 `VERSION_CONFLICT` correctly).

---

## Task 1: Conflict-detection helpers + skip global toast for patch

**Files:**
- Modify: `frontend/src/api/http.ts`
- Modify: `frontend/src/api/nodes.ts:10-19`
- Test: `frontend/tests/unit/api/http.spec.ts` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/api/http.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { isVersionConflict, errorMessage } from '@/api/http'

describe('isVersionConflict', () => {
  it('true on HTTP 409', () => {
    expect(isVersionConflict({ response: { status: 409 } })).toBe(true)
  })
  it('true on VERSION_CONFLICT code even without 409 status', () => {
    expect(isVersionConflict({ response: { data: { detail: { code: 'VERSION_CONFLICT' } } } })).toBe(true)
  })
  it('false on 412 (missing If-Match — a programming error, not a race)', () => {
    expect(isVersionConflict({ response: { status: 412, data: { detail: { code: 'IF_MATCH_REQUIRED' } } } })).toBe(false)
  })
  it('false on unrelated errors / undefined', () => {
    expect(isVersionConflict({ response: { status: 500 } })).toBe(false)
    expect(isVersionConflict(undefined)).toBe(false)
  })
})

describe('errorMessage', () => {
  it('extracts detail.message', () => {
    expect(errorMessage({ response: { data: { detail: { message: 'boom' } } } })).toBe('boom')
  })
  it('undefined when absent', () => {
    expect(errorMessage(new Error('x'))).toBeUndefined()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/unit/api/http.spec.ts`
Expected: FAIL — `isVersionConflict`/`errorMessage` are not exported.

- [ ] **Step 3: Add the helpers to `http.ts`**

Append to `frontend/src/api/http.ts` (after the interceptor, end of file). Use structural casts (matches the existing `SettingsView.vue` pattern — no extra axios type import):

```ts
/**
 * 真正的跨标签冲突：后端 If-Match 校验通过但 revision 已变（409 VERSION_CONFLICT）。
 * 注意：412 仅表示缺/坏 If-Match 标头（编程错误），不算冲突，故返回 false。
 */
export function isVersionConflict(err: unknown): boolean {
  const r = (err as { response?: { status?: number; data?: { detail?: { code?: string } } } })?.response
  return r?.status === 409 || r?.data?.detail?.code === 'VERSION_CONFLICT'
}

/** 取后端错误信封里的 message（供调用方自管 toast 的场景使用）。 */
export function errorMessage(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail?.message
}
```

- [ ] **Step 4: Make `patchNode` skip the global toast**

Edit `frontend/src/api/nodes.ts` — the `patchNode` request config. Change:

```ts
export const patchNode = async (
  nodeId: string,
  patch: NodePatch,
  revision: number,
): Promise<Node> =>
  (
    await http.patch<Node>(`/nodes/${nodeId}`, patch, {
      headers: { 'If-Match': String(revision) },
      skipErrorToast: true, // 冲突/校验错误由 nodeEditor store 自管提示（reload-wins）
    })
  ).data
```

(`skipErrorToast` is already declared on `AxiosRequestConfig` in `http.ts` and honored by the interceptor. `patchNode`'s only callers are `updateBody`/`updateForm`, which fully own messaging in Task 2.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/unit/api/http.spec.ts`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/http.ts frontend/src/api/nodes.ts frontend/tests/unit/api/http.spec.ts
git commit -m "feat(editor): add isVersionConflict/errorMessage helpers; patchNode skips global toast (E4 Task 1)"
```

---

## Task 2: Store reload-wins recovery + undo/redo inheritance (E1 fix)

**Files:**
- Modify: `frontend/src/store/nodeEditor.ts` (imports; new `_recoverFromConflict`; `updateBody:230-238`; `updateForm:240-256`)
- Test: `frontend/tests/unit/store/nodeEditor.spec.ts`

- [ ] **Step 1: Write the failing tests**

First, add an `element-plus` mock at the top of `frontend/tests/unit/store/nodeEditor.spec.ts`, right after the existing `vi.mock('@/api/nodes', ...)` block (around line 11):

```ts
const { warnSpy, errorSpy } = vi.hoisted(() => ({ warnSpy: vi.fn(), errorSpy: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { warning: warnSpy, error: errorSpy } }))
```

Then append a new `describe` block at the end of the file (before the final closing — it's top-level, so after the last `})`):

```ts
const conflict409 = { response: { status: 409, data: { detail: { code: 'VERSION_CONFLICT' } } } }

describe('nodeEditor store — 409 conflict recovery (E4)', () => {
  it('updateBody 409: reload-wins — refetch, clear undo+redo, warn, no undo push', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 4 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    // seed an undo entry so we can prove the conflict clears history
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>old</p>', revision: 4 })])
    await store.setLevel('a', 1)
    expect(store.canUndo).toBe(true)
    // a concurrent change makes the body save conflict
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>server</p>', revision: 9 })]) // refetch
    await store.updateBody('a', '<p>mine</p>')
    expect(store.nodeMap.get('a')?.body).toBe('<p>server</p>')
    expect(store.nodeMap.get('a')?.revision).toBe(9)
    expect(store.canUndo).toBe(false) // history cleared (inverses now reference a dead state)
    expect(store.canRedo).toBe(false)
    expect(warnSpy).toHaveBeenCalled()
  })

  it('updateBody non-409 error: toasts and rethrows (transient path intact)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 1 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockRejectedValueOnce({ response: { status: 500, data: { detail: { message: '服务器错误' } } } })
    await expect(store.updateBody('a', '<p>new</p>')).rejects.toBeTruthy()
    expect(errorSpy).toHaveBeenCalled()
    expect(store.canUndo).toBe(false) // nothing recorded on failure
  })

  it('updateForm 409: same reload-wins recovery', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', kind: 'step', revision: 2 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', kind: 'step', revision: 7 })]) // refetch
    await store.updateForm('a', { type: 'NOTE' }, [])
    expect(store.nodeMap.get('a')?.revision).toBe(7)
    expect(warnSpy).toHaveBeenCalled()
  })

  it('E1 fix: undo whose inverse updateBody 409s clears history (no stale re-push)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>v1</p>', revision: 1 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>v2</p>', revision: 2 })) // do
    await store.updateBody('a', '<p>v2</p>')
    expect(store.canUndo).toBe(true)
    // undo's inverse re-applies v1, but a concurrent change makes it 409
    patchSpy.mockRejectedValueOnce(conflict409)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>server</p>', revision: 9 })]) // refetch
    await store.undo()
    expect(store.canUndo).toBe(false) // NOT re-pushed (the old inverse is stale)
    expect(store.canRedo).toBe(false)
    expect(store.nodeMap.get('a')?.body).toBe('<p>server</p>')
    expect(warnSpy).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- tests/unit/store/nodeEditor.spec.ts`
Expected: FAIL — the four new tests fail (no recovery yet; `updateBody`/`updateForm` currently let the rejection propagate, so the 409 cases reject instead of recovering).

- [ ] **Step 3: Add imports + `_recoverFromConflict` to the store**

Edit `frontend/src/store/nodeEditor.ts`. Imports — add `nodeTitle` to the existing `nodeTree` import (line 4) and add the two new imports:

```ts
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import * as api from '@/api/nodes'
import { isVersionConflict, errorMessage } from '@/api/http'
import type { Node } from '@/types/node'
import { visibleRows, nodeTitle, type TreeRow } from '@/utils/nodeTree'
```

Add the helper action inside `actions` (place it right after `_refetch`, around line 98):

```ts
/**
 * 跨标签 409 冲突的 reload-wins 恢复：全量 re-GET、清空撤销/重做历史、提示用户。
 * 全量 refetch 因为并发修改可能重排兄弟编号；历史里的逆操作引用已失效旧态，必须清空。
 */
async _recoverFromConflict(id: string): Promise<void> {
  await this._refetch().catch(() => {})
  this.undoStack = []
  this.redoStack = []
  const node = this.nodeMap.get(id)
  const label = node ? nodeTitle(node) : '该节点'
  ElMessage.warning(`「${label}」已被他人修改，已加载最新版本，你刚才的未保存改动已丢弃`)
},
```

- [ ] **Step 4: Wrap `updateBody` and `updateForm` patch calls**

Replace `updateBody` (lines 230-238) with:

```ts
async updateBody(id: string, body: string): Promise<void> {
  const node = this.nodeMap.get(id)
  if (!node) return
  if (body === node.body) return // 无变化（挂载初始回发 / 空保存 / 防抖重复）不写库、不入撤销栈
  const prevBody = node.body
  let updated: Node
  try {
    updated = await api.patchNode(id, { body }, node.revision)
  } catch (err) {
    if (isVersionConflict(err)) {
      await this._recoverFromConflict(id) // reload-wins
      return
    }
    ElMessage.error(errorMessage(err) ?? '保存失败，请重试')
    throw err // 非冲突瞬时错误：抛出，让 undo()/redo() 重新入栈
  }
  this._replaceNode(updated)
  this._pushUndo(() => this.updateBody(id, prevBody))
},
```

Replace `updateForm` (lines 240-256) with:

```ts
async updateForm(
  id: string,
  inputSchema: import('@/types/node').InputSchema,
  attachmentMarks: import('@/types/node').AttachmentMark[],
): Promise<void> {
  const node = this.nodeMap.get(id)
  if (!node) return
  const prevSchema = node.input_schema as import('@/types/node').InputSchema
  const prevMarks = node.attachment_marks
  let updated: Node
  try {
    updated = await api.patchNode(
      id,
      { input_schema: inputSchema, attachment_marks: attachmentMarks },
      node.revision,
    )
  } catch (err) {
    if (isVersionConflict(err)) {
      await this._recoverFromConflict(id) // reload-wins
      return
    }
    ElMessage.error(errorMessage(err) ?? '保存失败，请重试')
    throw err // 非冲突瞬时错误：抛出，让 undo()/redo() 重新入栈
  }
  this._replaceNode(updated)
  this._pushUndo(() => this.updateForm(id, prevSchema, prevMarks))
},
```

(`undo()`/`redo()` are unchanged. A real 409 no longer reaches their catch: the inverse self-recovers and returns normally, having cleared the stacks. Their existing re-push path still handles genuine transient/non-409 inverse failures — e.g. a batch-based inverse like `setLevel` rejecting — exactly as the existing "failed undo re-pushes" test asserts.)

- [ ] **Step 5: Run the store tests to verify they pass**

Run: `cd frontend && npm test -- tests/unit/store/nodeEditor.spec.ts`
Expected: PASS — the four new tests pass AND all pre-existing tests (including `updateBody PATCHes with the node revision`, `undo of updateBody restores the previous body`, `failed undo re-pushes the entry and refetches`, the no-op-guard pair) stay green.

- [ ] **Step 6: Full frontend suite + type check**

Run: `cd frontend && npm test && npm run type-check`
(Type-check script is `vue-tsc`; if the script name differs, use `npx vue-tsc --noEmit`.)
Expected: all tests pass; vue-tsc reports no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/store/nodeEditor.ts frontend/tests/unit/store/nodeEditor.spec.ts
git commit -m "feat(editor): reload-wins 409 recovery in updateBody/updateForm; fixes E1 stale-undo (E4 Task 2)"
```

---

## Self-Review

**Spec coverage:**
- "Reframe as 409, not 412" → `isVersionConflict` explicitly excludes 412 (Task 1 test `false on 412`). ✓
- "Recovery inside the two patch actions + `_recoverFromConflict`" → Task 2 Steps 3-4. ✓
- "reload-wins: refetch + clear undo/redo + node-specific warning" → `_recoverFromConflict` + Task 2 test 1. ✓
- "skipErrorToast so store owns messaging; non-409 still toasts + rethrows" → Task 1 Step 4 + Task 2 test 2. ✓
- "E1 stale-undo fixed as a side effect" → Task 2 test 4 (undo inverse 409 → history cleared, not re-pushed). ✓
- "label via existing body→title helper" → `nodeTitle` from `nodeTree.ts:6`. ✓
- Non-goals (batch last-write-wins, proc-meta, settings 409, merge/force, realtime) → no tasks touch them. ✓

**Placeholder scan:** none — every code step has complete code and exact paths.

**Type consistency:** `isVersionConflict`/`errorMessage` signatures match between Task 1 (definition) and Task 2 (use). `_recoverFromConflict(id: string)` consistent. `updated: Node` typed to satisfy vue-tsc after moving the assignment out of the `const` (the `let` declaration is required because the assignment now happens in a `try`).
