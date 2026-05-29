# E7 — PDF Preview Chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zoom, page navigation + indicator, and a clearer download label to the in-browser PDF preview (`PdfPreviewDialog`).

**Architecture:** Pure arithmetic in a new `pdfChrome.ts` (unit-tested); thin DOM glue (CSS `zoom`, `@scroll`, `scrollIntoView`) in `PdfPreviewDialog.vue` (browser-verified). Spec: `docs/superpowers/specs/2026-05-29-editor-e7-pdf-preview-chrome-design.md`.

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, vitest, vue-tsc. No new dependency.

---

## File Structure

- **Create** `frontend/src/components/PdfPreview/pdfChrome.ts` — `clampZoom`, `stepZoom`, `fitZoom`, `activePageIndex` + zoom constants.
- **Create** `frontend/tests/unit/pdfChrome.spec.ts` — pure-function tests (flat, matching `tests/unit/pdfModel.spec.ts`).
- **Modify** `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` — toolbar controls, `zoom`/page-nav state, refs, CSS `zoom`, print reset.

No backend change. `PdfPreviewDialog` has no unit test (it fetches on open + needs layout); its behavior is verified by the orchestrator browser smoke.

---

## Task 1: Pure `pdfChrome.ts`

**Files:**
- Create: `frontend/src/components/PdfPreview/pdfChrome.ts`
- Test: `frontend/tests/unit/pdfChrome.spec.ts`

- [ ] **Step 1: Write the failing test — CREATE `frontend/tests/unit/pdfChrome.spec.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { clampZoom, stepZoom, fitZoom, activePageIndex, ZOOM_MIN, ZOOM_MAX } from '@/components/PdfPreview/pdfChrome'

describe('clampZoom', () => {
  it('clamps below min and above max', () => {
    expect(clampZoom(0.3)).toBe(ZOOM_MIN)
    expect(clampZoom(3)).toBe(ZOOM_MAX)
  })
  it('rounds to 2 decimals and passes valid values', () => {
    expect(clampZoom(1.234)).toBe(1.23)
    expect(clampZoom(0.7)).toBe(0.7)
  })
})

describe('stepZoom', () => {
  it('steps in/out by 0.1', () => {
    expect(stepZoom(1, 1)).toBe(1.1)
    expect(stepZoom(1, -1)).toBe(0.9)
  })
  it('clamps at the bounds', () => {
    expect(stepZoom(0.5, -1)).toBe(0.5)
    expect(stepZoom(2, 1)).toBe(2)
    expect(stepZoom(1.95, 1)).toBe(2)
  })
})

describe('fitZoom', () => {
  it('fits page width into the container minus padding', () => {
    expect(fitZoom(1048, 1000)).toBe(1)     // (1048-48)/1000
    expect(fitZoom(548, 1000)).toBe(0.5)    // (548-48)/1000
  })
  it('clamps and handles unmeasured page width', () => {
    expect(fitZoom(2048, 1000)).toBe(2)     // (2048-48)/1000 = 2.0
    expect(fitZoom(100, 1000)).toBe(0.5)    // tiny → clamp to min
    expect(fitZoom(1000, 0)).toBe(1)        // unmeasured → 1
  })
})

describe('activePageIndex', () => {
  it('returns 0 for empty', () => {
    expect(activePageIndex(123, [])).toBe(0)
  })
  it('tracks the last page whose top is <= scrollTop', () => {
    const tops = [0, 300, 600]
    expect(activePageIndex(0, tops)).toBe(0)
    expect(activePageIndex(350, tops)).toBe(1)
    expect(activePageIndex(300, tops)).toBe(1)   // exact boundary → that page
    expect(activePageIndex(10000, tops)).toBe(2) // past last → last
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement — CREATE `frontend/src/components/PdfPreview/pdfChrome.ts`**

```ts
// Pure chrome math for the PDF preview dialog (E7): zoom + page-index. DOM glue lives in PdfPreviewDialog.vue.

export const ZOOM_MIN = 0.5
export const ZOOM_MAX = 2
export const ZOOM_STEP = 0.1

/** Clamp to [MIN,MAX] and round to 2 decimals (avoids float drift). */
export function clampZoom(z: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 100) / 100))
}

/** One zoom step in/out (dir = +1 / -1), clamped. */
export function stepZoom(z: number, dir: 1 | -1): number {
  return clampZoom(z + dir * ZOOM_STEP)
}

/** Fit a page of width pageW into a container of width containerW (minus padding), clamped.
 *  Returns 1 when pageW <= 0 (unmeasured). */
export function fitZoom(containerW: number, pageW: number, pad = 48): number {
  if (pageW <= 0) return 1
  return clampZoom((containerW - pad) / pageW)
}

/** Active page index from scroll: the last page whose top offset is <= scrollTop.
 *  pageTops must be ascending. Clamped to [0, len-1]; 0 when empty. */
export function activePageIndex(scrollTop: number, pageTops: number[]): number {
  if (pageTops.length === 0) return 0
  let idx = 0
  for (let i = 0; i < pageTops.length; i++) {
    if (pageTops[i] <= scrollTop + 1) idx = i
    else break
  }
  return idx
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/pdfChrome.spec.ts`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PdfPreview/pdfChrome.ts frontend/tests/unit/pdfChrome.spec.ts
git commit -m "feat(pdf): pure pdfChrome zoom/page-index helpers (E7 Task 1)"
```

---

## Task 2: Wire chrome into `PdfPreviewDialog.vue`

**Files:**
- Modify: `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` (script, template toolbar + `.pv-scroll`/`.pv-doc`, print style)

Verified by vue-tsc + the full vitest suite staying green; behavior by the orchestrator browser smoke (no unit test exists for this dialog).

- [ ] **Step 1: Script — add imports, state, and handlers**

In `<script setup>`:

(a) Change the vue import (line 2) to add `nextTick`:
```ts
import { computed, ref, watch, nextTick } from 'vue'
```

(b) Add the chrome import (after the `./pdfModel` import block, ~line 16):
```ts
import { clampZoom, stepZoom, fitZoom, activePageIndex, ZOOM_MIN, ZOOM_MAX } from './pdfChrome'
```

(c) After the existing `const model = ref<PreviewModel | null>(null)` (line 35), add:
```ts
const scrollEl = ref<HTMLElement | null>(null)
const docEl = ref<HTMLElement | null>(null)
const zoom = ref(1)
const pageCount = ref(0)
const currentPage = ref(0)
const zoomPct = computed(() => Math.round(zoom.value * 100))

function pageEls(): HTMLElement[] {
  return Array.from(docEl.value?.querySelectorAll<HTMLElement>('.page') ?? [])
}
function zoomIn(): void {
  zoom.value = stepZoom(zoom.value, 1)
}
function zoomOut(): void {
  zoom.value = stepZoom(zoom.value, -1)
}
function fit(): void {
  const cw = scrollEl.value?.clientWidth ?? 0
  const pw = pageEls()[0]?.offsetWidth ?? 0
  zoom.value = fitZoom(cw, pw)
}
function onScroll(): void {
  const tops = pageEls().map((el) => el.offsetTop)
  pageCount.value = tops.length
  currentPage.value = activePageIndex(scrollEl.value?.scrollTop ?? 0, tops)
}
function goPage(i: number): void {
  const n = pageEls().length
  if (n === 0) return
  const clamped = Math.min(n - 1, Math.max(0, i))
  pageEls()[clamped]?.scrollIntoView({ block: 'start' })
  currentPage.value = clamped
}
function prevPage(): void {
  goPage(currentPage.value - 1)
}
function nextPage(): void {
  goPage(currentPage.value + 1)
}
```

(d) In the existing `watch(visible, ...)` success branch, right after `model.value = buildModel(d, nodes, l)` (line 57), reset + measure once the DOM exists:
```ts
      await nextTick()
      zoom.value = 1
      currentPage.value = 0
      pageCount.value = pageEls().length
```
(Keep the rest of the `try/catch/finally` unchanged.)

- [ ] **Step 2: Template — toolbar controls**

In the `.pv-actions` div (line 118), add the zoom + page-nav groups **before** the existing `下载 PDF` button, and change the download label:
```html
        <div class="pv-actions">
          <div v-if="model" class="pv-zoom">
            <el-button size="small" :disabled="zoom <= ZOOM_MIN" @click="zoomOut">−</el-button>
            <span class="pv-zoom-pct">{{ zoomPct }}%</span>
            <el-button size="small" :disabled="zoom >= ZOOM_MAX" @click="zoomIn">＋</el-button>
            <el-button size="small" @click="fit">适应</el-button>
          </div>
          <div v-if="model && pageCount" class="pv-pagenav">
            <el-button size="small" :disabled="currentPage <= 0" @click="prevPage">‹ 上一页</el-button>
            <span class="pv-pageind">{{ currentPage + 1 }} / {{ pageCount }}</span>
            <el-button size="small" :disabled="currentPage >= pageCount - 1" @click="nextPage">下一页 ›</el-button>
          </div>
          <el-button :loading="downloading" @click="doDownload">{{ downloading ? '生成中…' : '下载 PDF' }}</el-button>
          <el-button type="primary" @click="doPrint">打印</el-button>
          <el-button @click="visible = false">关闭</el-button>
        </div>
```

- [ ] **Step 3: Template — bind refs + zoom + scroll**

Change the `.pv-scroll` open tag (line 126) to bind the ref + scroll handler, and the `.pv-doc` open tag (line 127) to bind its ref + the zoom style:
```html
    <div ref="scrollEl" v-loading="loading" class="pv-scroll" @scroll="onScroll">
      <div v-if="model && meta" ref="docEl" class="pv-doc" :style="{ zoom }" @click="onPreviewClick">
```
(Everything inside `.pv-doc` is unchanged.)

- [ ] **Step 4: Style — print reset + control styling**

Add `zoom: 1 !important;` to the existing print `.pv-doc` rule (lines 593-595):
```css
  .pv-doc {
    gap: 0 !important;
    zoom: 1 !important;
  }
```
And add control styles to the `<style scoped>` (e.g. after the `.pv-title` rule, ~line 294):
```css
.pv-zoom,
.pv-pagenav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pv-zoom-pct,
.pv-pageind {
  font-size: 12px;
  min-width: 44px;
  text-align: center;
}
```

- [ ] **Step 5: Type check**

Run: `cd frontend && npm run typecheck`
Expected: vue-tsc no errors. (`ZOOM_MIN`/`ZOOM_MAX` are used in the template, so keep them in the import.)

- [ ] **Step 6: Full suite — green**

Run: `cd frontend && npm test`
Expected: 0 failures (prior + the new `pdfChrome` tests). `pdfModel.spec` and all others stay green — the dialog change is additive and no test mounts it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PdfPreview/PdfPreviewDialog.vue
git commit -m "feat(pdf): zoom + page navigation + generating label in PdfPreviewDialog (E7 Task 2)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 2, before merge)

Bootstrap the worktree backend (symlink `.venv`, cp `.env`, cp `dev.db`, symlink `var/storage`) + launch backend + frontend; open a procedure editor (`/procedures/<id>/edit`), click `PDF 预览`, then:

1. `＋` / `−` scale the pages; the `%` updates; buttons disable at 50% / 200%.
2. `适应` fits a page to the width.
3. Scrolling updates `n / N`; `下一页` / `上一页` scroll and the indicator follows; disabled at first/last.
4. `打印` preview (or `@media print` emulation) shows no toolbar and unscaled pages.
5. `下载 PDF` still downloads (label shows `生成中…` while loading).

The smoke can reuse the E6 servers if still up; otherwise relaunch. If staging is impractical, smoke on parent `main` after merge and note it.

---

## Self-Review

**Spec coverage:**
- Pure `clampZoom`/`stepZoom`/`fitZoom`/`activePageIndex` → Task 1. ✓
- Zoom control `[−] % [+] [适应]` via CSS `zoom` on `.pv-doc`, reset under `@media print` → Task 2 Steps 2-4. ✓
- Page nav `[‹] n/N [›]` from `activePageIndex` + `scrollIntoView`, bounds-disabled → Task 2 Steps 1-2. ✓
- Download label `生成中…` reusing `:loading` → Task 2 Step 2. ✓
- Controls inside `.no-print` toolbar; render only when `model` loaded → Task 2 Step 2 (`v-if="model"`). ✓
- Browser smoke as the dialog's behavioral verification → orchestrator section. ✓
- Non-goals (jump input, thumbnails, search, real %, etc.) → no task touches them. ✓

**Placeholder scan:** none — full code for the module + every dialog edit with exact line anchors.

**Type consistency:** `pdfChrome` exports (`clampZoom/stepZoom/fitZoom/activePageIndex/ZOOM_MIN/ZOOM_MAX`) match the import in the dialog and the test. `stepZoom(z, dir: 1 | -1)` called with literals `1`/`-1`. Refs typed `HTMLElement | null`. `zoom` is a `number` ref → valid for CSS `zoom`.
