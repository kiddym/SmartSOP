# E9 — Version-History Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the unused `version_update_notes_preview` inline (collapsed rows) in `VersionListPanel`, and give the 刷新 button per-click feedback (button spinner + `已刷新` toast).

**Architecture:** Single component change + tests. Frontend-only (backend already returns `_preview`). Spec: `docs/superpowers/specs/2026-05-29-editor-e9-version-history-polish-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, vitest + @vue/test-utils, vue-tsc.

---

## File Structure

- **Modify** `frontend/src/components/version/VersionListPanel.vue` — inline preview snippet, `manualRefresh` + button `:loading`, `ElMessage` import, CSS.
- **Modify** `frontend/tests/unit/VersionListPanel.spec.ts` — preview + refresh tests.

No backend change.

---

## Task 1: Inline notes preview + refresh feedback

**Files:**
- Modify: `frontend/src/components/version/VersionListPanel.vue`
- Test: `frontend/tests/unit/VersionListPanel.spec.ts`

- [ ] **Step 1: Write the failing tests**

In `frontend/tests/unit/VersionListPanel.spec.ts`, add an `ElMessage` import at the top (after the existing imports, ~line 9):
```ts
import { ElMessage } from 'element-plus'
```
Then append these tests inside the `describe('VersionListPanel', ...)` block (after the last test):
```ts
  it('有 notes 且折叠 → 渲染预览片段（version_update_notes_preview）', async () => {
    const w = await mountPanel(
      [item({ id: 'v2', version: 2, version_update_notes: '完整说明文本', version_update_notes_preview: '完整说明…' })],
      'v3',
    )
    const preview = w.find('.notes-preview')
    expect(preview.exists()).toBe(true)
    expect(preview.text()).toContain('完整说明…')
  })

  it('无 notes → 不渲染预览片段', async () => {
    const w = await mountPanel([item({ id: 'v2', version: 2 })], 'v3') // notes 默认 ''
    expect(w.find('.notes-preview').exists()).toBe(false)
  })

  it('展开后隐藏预览、显示完整说明', async () => {
    const w = await mountPanel(
      [item({ id: 'v2', version: 2, version_update_notes: '完整说明文本', version_update_notes_preview: '完整说明…' })],
      'v3',
    )
    const toggle = w.findAll('button').find((b) => b.text().includes('更新说明'))
    await toggle!.trigger('click')
    expect(w.find('.notes-preview').exists()).toBe(false)
    expect(w.find('.notes').text()).toContain('完整说明文本')
  })

  it('点击刷新 → 重新拉取并提示「已刷新」', async () => {
    const w = await mountPanel([item({ id: 'v1', version: 1 })])
    const successSpy = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
    fetchGroupVersions.mockResolvedValue({ count: 1, items: [item({ id: 'v1', version: 1 })] })
    const refreshBtn = w.findAll('button').find((b) => b.text().trim() === '刷新')
    await refreshBtn!.trigger('click')
    await flushPromises()
    expect(fetchGroupVersions).toHaveBeenCalledTimes(2) // mount + 手动刷新
    expect(successSpy).toHaveBeenCalledWith('已刷新')
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts`
Expected: the 4 new tests FAIL (no `.notes-preview` element; refresh doesn't toast). The 4 existing tests still pass.

- [ ] **Step 3: Implement in `frontend/src/components/version/VersionListPanel.vue`**

(a) Add the `ElMessage` import after the `vue` import (line 2):
```ts
import { ElMessage } from 'element-plus'
```
(b) Add `manualRefresh` after the `defineExpose({ reload })` line (~line 33):
```ts
async function manualRefresh(): Promise<void> {
  try {
    await reload()
    ElMessage.success('已刷新')
  } catch {
    /* http 拦截器已提示错误 */
  }
}
```
(c) Change the 刷新 button (line 48) from:
```html
        <el-button text size="small" @click="reload">刷新</el-button>
```
to:
```html
        <el-button text size="small" :loading="loading" @click="manualRefresh">刷新</el-button>
```
(d) Add the preview snippet in the row — insert it **immediately before** the existing expanded-notes `<div v-if="expanded.has(v.id)" class="notes">` block (~line 80):
```html
      <div
        v-if="v.version_update_notes && !expanded.has(v.id)"
        class="notes-preview"
        @click="toggleNotes(v.id)"
      >
        {{ v.version_update_notes_preview || v.version_update_notes }}
      </div>
```
(e) Add the CSS to `<style scoped>` (after the `.notes` rule, ~line 130):
```css
.notes-preview {
  margin: 4px 0 2px 46px;
  font-size: 12px;
  color: #909399;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```
Change nothing else (the 「更新说明」 toggle button, the expanded `.notes` div, view/rollback, and `reload`/`onMounted`/`defineExpose` all stay).

- [ ] **Step 4: Run to verify PASS + full suite + type check**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts` → expect all 8 PASS (4 existing + 4 new).
Run: `cd frontend && npm test` → expect 0 failures across the suite.
Run: `cd frontend && npm run typecheck` → expect vue-tsc no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/VersionListPanel.vue frontend/tests/unit/VersionListPanel.spec.ts
git commit -m "feat(version): inline notes preview + refresh feedback in VersionListPanel (E9)"
```

---

## Self-Review

**Spec coverage:**
- Inline `version_update_notes_preview` snippet (collapsed, clickable, fallback to full notes) → Step 3(d) + CSS 3(e). ✓
- Hidden when expanded; full notes unchanged → `!expanded.has(v.id)` guard. ✓
- No notes → no snippet/toggle → guard `v.version_update_notes && …`. ✓
- Refresh button `:loading` + `已刷新` toast via `manualRefresh`, mount load stays silent → Step 3(a-c). ✓
- Failure swallowed (interceptor toasts) → `manualRefresh` catch. ✓
- No backend / no rollback-view / no diff changes → no task touches them. ✓

**Placeholder scan:** none — full before/after code + tests.

**Type consistency:** `version_update_notes_preview` already on `VersionListItem` (and the spec's `item()` factory). `manualRefresh(): Promise<void>` matches the `@click`. `ElMessage` imported. `loading` ref already exists (bound to `:loading`). Tests use the existing `mountPanel`/`item` helpers + the already-hoisted `fetchGroupVersions` mock + `vi.spyOn(ElMessage,'success')` (same pattern as `NodeTreePanel.spec`).
