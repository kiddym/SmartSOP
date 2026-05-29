# E15 — Arbitrary Two-Version Compare — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Follow-up to E10 (version diff/compare viewer).
**Status:** Design approved; ready for implementation plan.

## Goal

Let a user pick **any two** versions in `VersionListPanel` and compare them (older → newer), beyond E10's one-click `对比当前` (a row vs the current version). A version **picker** — the `VersionCompareDialog` and the host already accept an arbitrary pair, so this is one component.

## Background (present today)

`VersionListPanel.vue` lists a group's versions; each row has `查看` / `对比当前` (E10) / `回退` / a notes preview+toggle. It emits `compare({ oldId, oldVersion, newId, newVersion })` (line 14); the host (`ProcedureDetailView`) handler `(p) => { comparePair = p; compareVisible = true }` opens `VersionCompareDialog v-bind` with whatever pair it receives. `对比当前` emits `{ old: the row, new: the group's is_current }`. **No host/dialog change is needed** — they already handle an arbitrary pair.

## Changes — `VersionListPanel.vue` only

### Script
- `const selectedIds = ref<string[]>([])` — picked version ids, **ordered, capped at 2 (FIFO)**.
- `function toggleSelect(id)`: if present → remove; else append, and if length > 2 drop the front (`shift`).
- `function clearSel()`: `selectedIds.value = []`.
- `function compareSelected()`: require exactly 2; resolve the two `VersionListItem`s; the **lower `version` is old, higher is new**; `emit('compare', { oldId: older.id, oldVersion: older.version, newId: newer.id, newVersion: newer.version })`; then `clearSel()`.
- `对比当前` (`emitCompare`) and everything else unchanged.

### Template
- A **selection bar** below the card `#header`, shown when `selectedIds.length > 0`:
  ```html
  <div v-if="selectedIds.length" class="vsel-bar">
    <span>已选 {{ selectedIds.length }} / 2</span>
    <el-button size="small" type="primary" :disabled="selectedIds.length !== 2" @click="compareSelected">对比所选</el-button>
    <el-button size="small" text @click="clearSel">清空</el-button>
  </div>
  ```
- A **per-row checkbox** as the first child of each `.line` (before `<span class="ver">`):
  ```html
  <el-checkbox class="vrow-check" :model-value="selectedIds.includes(v.id)" @change="() => toggleSelect(v.id)" />
  ```

### CSS
`.vsel-bar { display:flex; align-items:center; gap:8px; padding:6px 8px; margin-bottom:6px; font-size:13px; background:var(--el-color-primary-light-9,#fbf1ee); border-radius:4px }`; `.vrow-check { flex:none }`.

## Data flow

```
check ≤2 rows → selectedIds (FIFO cap 2)
对比所选 (enabled at exactly 2) → order by version# (old=lower, new=higher)
  → emit('compare', {oldId,oldVersion,newId,newVersion}) → clearSel()
  → host comparePair = p; compareVisible = true  (existing) → VersionCompareDialog (existing)
```

## Error handling / edge cases

- Cap 2 FIFO: checking a 3rd version silently drops the earliest pick — no error state.
- `对比所选` disabled unless exactly 2 selected.
- `compareSelected` re-checks `length === 2` and that both items resolve (guards against a stale id after a reload).
- Selection order doesn't matter — the pair is always ordered by `version` (older→newer), so the diff reads chronologically.
- Selecting the current version + an older one via checkboxes yields the same pair `对比当前` would (consistent).

## Testing

- **`frontend/tests/unit/VersionListPanel.spec.ts`** (extend): checking two rows **out of order** (e.g. v3 then v1) + `对比所选` emits the **version-ordered** pair `{ oldId:'v1', oldVersion:1, newId:'v3', newVersion:3 }`; `对比所选` is `disabled` with 0 or 1 selected; the **FIFO cap** (check v3, v2, v1 → selection keeps the last two → `对比所选` emits `{old:v1,new:v2}`); existing `对比当前` / `查看` / `回退` tests stay green.
- **Browser smoke**: in the `a5b865ed` 2-version group, check v1 + v2 → `对比所选` opens `VersionCompareDialog` for v1 → v2.
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Comparing >2 versions, cross-group compare, persisting the selection, a dedicated compare route, any change to `VersionCompareDialog` or the host (both already take an arbitrary pair).
