# E15 — Arbitrary Two-Version Compare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pick any two versions in `VersionListPanel` (checkboxes, cap 2 FIFO) + a `对比所选` action that emits the existing `compare` event ordered older→newer. Dialog + host unchanged. Spec: `docs/superpowers/specs/2026-05-29-editor-e15-arbitrary-version-compare-design.md`.

**Tech Stack:** Vue 3, Element Plus, vitest + @vue/test-utils, vue-tsc. No new dependency.

---

## File Structure

- **Modify** `frontend/src/components/version/VersionListPanel.vue` — selection state, row checkbox, selection bar, `compareSelected`.
- **Modify** `frontend/tests/unit/VersionListPanel.spec.ts` — picker tests.

No `VersionCompareDialog` / host / backend change.

---

## Task 1: Two-version picker in `VersionListPanel`

**Files:**
- Modify: `frontend/src/components/version/VersionListPanel.vue`
- Test: `frontend/tests/unit/VersionListPanel.spec.ts`

- [ ] **Step 1: Write the failing tests — append to `frontend/tests/unit/VersionListPanel.spec.ts`**

Add inside the `describe('VersionListPanel', …)` block (reuses `mountPanel`, `item`):
```ts
  it('对比所选: pick two out of order → emits the version-ordered pair (old=lower)', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v3')
    const checks = w.findAllComponents({ name: 'ElCheckbox' }) // one per row, in item order
    checks[0].vm.$emit('change', true) // v3
    checks[2].vm.$emit('change', true) // v1
    await w.vm.$nextTick()
    const btn = w.findAll('button').find((b) => b.text().includes('对比所选'))
    expect(btn?.attributes('disabled')).toBeUndefined() // enabled at exactly 2
    await btn!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([
      { oldId: 'v1', oldVersion: 1, newId: 'v3', newVersion: 3 },
    ])
  })

  it('对比所选 is disabled unless exactly two are selected', async () => {
    const w = await mountPanel([
      item({ id: 'v2', version: 2, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v2')
    // none selected → no bar / no 对比所选 button
    expect(w.findAll('button').some((b) => b.text().includes('对比所选'))).toBe(false)
    w.findAllComponents({ name: 'ElCheckbox' })[0].vm.$emit('change', true) // 1 selected
    await w.vm.$nextTick()
    const btn = w.findAll('button').find((b) => b.text().includes('对比所选'))
    expect(btn?.attributes('disabled')).toBeDefined() // present but disabled
  })

  it('selection caps at two (FIFO drops the earliest pick)', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ], 'v3')
    const checks = w.findAllComponents({ name: 'ElCheckbox' })
    checks[0].vm.$emit('change', true) // v3
    checks[1].vm.$emit('change', true) // v2
    checks[2].vm.$emit('change', true) // v1 → drops v3 (FIFO) → [v2, v1]
    await w.vm.$nextTick()
    await w.findAll('button').find((b) => b.text().includes('对比所选'))!.trigger('click')
    expect(w.emitted('compare')?.[0]).toEqual([
      { oldId: 'v1', oldVersion: 1, newId: 'v2', newVersion: 2 },
    ])
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts`
Expected: the 3 new tests FAIL (no checkbox / `对比所选`); existing tests still pass.

- [ ] **Step 3: Script — selection state + handlers (`frontend/src/components/version/VersionListPanel.vue`)**

After `const expanded = ref<Set<string>>(new Set())` (line 19), add:
```ts
const selectedIds = ref<string[]>([])
function toggleSelect(id: string): void {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  } else {
    const next = [...selectedIds.value, id]
    if (next.length > 2) next.shift() // cap 2, FIFO
    selectedIds.value = next
  }
}
function clearSel(): void {
  selectedIds.value = []
}
function compareSelected(): void {
  if (selectedIds.value.length !== 2) return
  const picked = selectedIds.value
    .map((id) => items.value.find((v) => v.id === id))
    .filter((v): v is VersionListItem => !!v)
  if (picked.length !== 2) return
  const [a, b] = picked
  const older = a.version <= b.version ? a : b
  const newer = a.version <= b.version ? b : a
  emit('compare', { oldId: older.id, oldVersion: older.version, newId: newer.id, newVersion: newer.version })
  clearSel()
}
```
(`VersionListItem` is already imported; `items`/`emit`/`ref` already in scope.)

- [ ] **Step 4: Template — selection bar + row checkbox**

(a) Add the selection bar right after the `</template>` that closes the card `#header` (after line 67, before the `<div v-for="v in items" …>`):
```html
    <div v-if="selectedIds.length" class="vsel-bar">
      <span>已选 {{ selectedIds.length }} / 2</span>
      <el-button size="small" type="primary" :disabled="selectedIds.length !== 2" @click="compareSelected">对比所选</el-button>
      <el-button size="small" text @click="clearSel">清空</el-button>
    </div>
```
(b) Add the checkbox as the first child of `.line` (before `<span class="ver">`, line 71):
```html
        <el-checkbox class="vrow-check" :model-value="selectedIds.includes(v.id)" @change="() => toggleSelect(v.id)" />
```

- [ ] **Step 5: CSS** (in `<style scoped>`)

```css
.vsel-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 6px;
  font-size: 13px;
  background: var(--el-color-primary-light-9, #fbf1ee);
  border-radius: 4px;
}
.vrow-check {
  flex: none;
}
```

- [ ] **Step 6: Run the dialog suite — green**

Run: `cd frontend && npm test -- tests/unit/VersionListPanel.spec.ts`
Expected: all pass (existing + 3 new).

- [ ] **Step 7: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/version/VersionListPanel.vue frontend/tests/unit/VersionListPanel.spec.ts
git commit -m "feat(version): pick any two versions to compare in VersionListPanel (E15)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 1, before merge)

Launch the worktree dev servers; open the `a5b865ed` 2-version group's current (v2) detail page → in 版本列表, check **v1** and **v2** → the selection bar shows `已选 2 / 2` → click `对比所选` → `VersionCompareDialog` opens for **v1 → v2** (older→newer). Confirm `对比当前` still works, and checking a 3rd version (if a 3-version group is staged) drops the earliest. If staging is impractical, note it — the picker logic is unit-tested.

---

## Self-Review

**Spec coverage:**
- Row checkbox + `selectedIds` cap-2 FIFO → Step 3-4. ✓
- Selection bar (`已选 N / 2` + `对比所选` enabled at exactly 2 + `清空`) → Step 4(a). ✓
- `compareSelected` orders by version (old=lower) + emits the existing `compare` + clears → Step 3. ✓
- `对比当前` / dialog / host unchanged → no task touches them. ✓
- Non-goals (>2, cross-group, persist, route, dialog/host change) → untouched. ✓

**Placeholder scan:** none — full code for script, template, CSS, and tests.

**Type consistency:** `selectedIds: ref<string[]>`; `compareSelected` emits the exact `compare` payload shape `{ oldId, oldVersion, newId, newVersion }` already declared in `defineEmits` (line 14) and consumed by the host. `el-checkbox` `@change` handler ignores its boolean arg (`() => toggleSelect(v.id)`). Tests emit `change` on the `ElCheckbox` components in row order.
