# E7 — PDF Preview Chrome (zoom + page nav + download label) — Design

**Date:** 2026-05-29
**Track:** Post-migration editor enhancements (follows E1 undo/redo, E2 cascading multi-select, E3 Tab indent, E4 409 conflict recovery, E5 virtual list, E6 markdown autoformat).
**Status:** Design approved; ready for implementation plan.

## Goal

Add real "chrome" controls around the in-browser PDF preview: a zoom control, page navigation with a current-page indicator, and a clearer label on the (already-loading) download button. First slice of the larger "publish / version / PDF chrome polish" backlog item — the publish-flow and version-history surfaces are deferred to their own specs.

## Background (current state)

- `frontend/src/components/PdfPreview/PdfPreviewDialog.vue` is a fullscreen `el-dialog` showing an **in-browser HTML preview** (not a real PDF). Structure: a scroll container `.pv-scroll` → `.pv-doc` → a series of `<section class="page">` (cover, TOC, revision-record, content pages aligned to the backend layout, attachments).
- Toolbar `.pv-toolbar.no-print` already has: `下载 PDF` (`<el-button :loading="downloading">` → backend ReportLab `downloadPdf`), `打印` (`window.print()`), `关闭`.
- `@media print` already hides `.no-print` and resets the canvas.
- There is **no zoom, no page navigation, no page indicator**. jsdom has no layout and the dialog fetches detail/nodes/layout on open, so its DOM behavior is not unit-testable.

## Approach (pure-vs-glue, as in E5/E6)

- **New pure module `frontend/src/components/PdfPreview/pdfChrome.ts`** (unit-tested) holds the arithmetic.
- **`PdfPreviewDialog.vue`** holds the thin DOM glue (CSS `zoom`, scroll listener, `scrollIntoView`), browser-verified.

Rejected alternative for zoom: `transform: scale()` — it doesn't reflow the scroll box (extra whitespace when zooming out, horizontal clipping when zooming in) without extra wrapper-sizing math. CSS `zoom` reflows correctly and is supported in Chromium (this app's target) and current Firefox; it is reset under `@media print`.

## Components & changes

### New module — `frontend/src/components/PdfPreview/pdfChrome.ts`

```ts
export const ZOOM_MIN = 0.5
export const ZOOM_MAX = 2
export const ZOOM_STEP = 0.1

/** Clamp to [MIN,MAX] and round to 2 decimals (avoids float drift like 0.7000000001). */
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

/** Active page index from scroll position: the last page whose top offset is <= scrollTop.
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

### `PdfPreviewDialog.vue`

**Script:**
- Import the pure helpers + the constants.
- `const zoom = ref(1)`; `const scrollEl = ref<HTMLElement | null>(null)` (bind to `.pv-scroll`); `const docEl = ref<HTMLElement | null>(null)` (bind to `.pv-doc`); `const pageCount = ref(0)`; `const currentPage = ref(0)`.
- `zoomIn()/zoomOut()` = `zoom.value = stepZoom(zoom.value, +1 / -1)`.
- `fit()` = measure `scrollEl.clientWidth` and the first `.page` `offsetWidth`, `zoom.value = fitZoom(...)`.
- `zoomPct = computed(() => Math.round(zoom.value * 100))`.
- `pageEls()` helper = `Array.from(docEl.value?.querySelectorAll<HTMLElement>('.page') ?? [])`.
- `onScroll()` (passive listener on `.pv-scroll`): `const tops = pageEls().map(el => el.offsetTop); pageCount.value = tops.length; currentPage.value = activePageIndex(scrollEl.value!.scrollTop, tops)`.
- `goPage(i)`: clamp `i` to `[0, pageCount-1]`; `pageEls()[i]?.scrollIntoView({ block: 'start' })`; `currentPage.value = i`.
- `prevPage()/nextPage()` = `goPage(currentPage.value -/+ 1)`.
- After the model loads (in the existing `watch(visible)` success path, `await nextTick()`), reset `zoom=1`, measure `pageCount` via `pageEls().length`, set `currentPage=0`, and attach the scroll listener; detach on close. (Reset on each open.)

**Template (toolbar `.pv-actions`, before the existing buttons):**
```html
<div class="pv-zoom" v-if="model">
  <el-button size="small" @click="zoomOut" :disabled="zoom <= ZOOM_MIN">−</el-button>
  <span class="pv-zoom-pct">{{ zoomPct }}%</span>
  <el-button size="small" @click="zoomIn" :disabled="zoom >= ZOOM_MAX">＋</el-button>
  <el-button size="small" @click="fit">适应</el-button>
</div>
<div class="pv-pagenav" v-if="model && pageCount">
  <el-button size="small" @click="prevPage" :disabled="currentPage <= 0">‹ 上一页</el-button>
  <span class="pv-pageind">{{ currentPage + 1 }} / {{ pageCount }}</span>
  <el-button size="small" @click="nextPage" :disabled="currentPage >= pageCount - 1">下一页 ›</el-button>
</div>
```
- Download button label: `{{ downloading ? '生成中…' : '下载 PDF' }}` (keeps `:loading`).
- Bind `ref="scrollEl"` on `.pv-scroll` and `ref="docEl"` on `.pv-doc`.
- Apply zoom: `<div class="pv-doc" :style="{ zoom }" …>`.

**Style:**
- `.pv-doc { /* existing */ }` — zoom applied inline.
- Add to the existing `@media print` block: `.pv-doc { zoom: 1 !important; }` so print/PDF download ignore the on-screen zoom.
- Minor flex styling for `.pv-zoom` / `.pv-pagenav` (gap, align-items center). All inside the `.no-print` toolbar.

## Data flow

```
open dialog → fetch detail/nodes/layout → model set → nextTick
  → measure .page offsetTops → pageCount; currentPage=0; zoom=1; attach scroll listener
user scrolls .pv-scroll → onScroll → activePageIndex(scrollTop, tops) → currentPage
click +/−/适应 → zoom ref → CSS zoom on .pv-doc (offsetTop/scrollTop stay consistent under zoom)
click ‹/› → goPage → .page.scrollIntoView → currentPage
```

## Error handling / edge cases

- Controls render only when `model` is set (hidden during `v-loading`); page-nav also requires `pageCount > 0`.
- `pageTops` recomputed every scroll, so a zoom change can't stale the indicator.
- Bounds: prev disabled at page 0, next disabled at last page; `goPage` clamps.
- `fit()` with an unmeasured page (offsetWidth 0) → `fitZoom` returns 1 (safe).
- CSS `zoom` keeps `offsetTop`/`scrollTop` in the same (scaled) coordinate space in Chromium, so `activePageIndex` stays correct at any zoom.
- Zoom never leaks to print/PDF (reset in `@media print`; download hits the backend independently).

## Testing

- **Unit — `frontend/tests/unit/PdfPreview/pdfChrome.spec.ts`** (pure): `clampZoom` (below min, above max, rounding), `stepZoom` (in/out + clamp at bounds), `fitZoom` (normal fit, clamp, `pageW<=0` → 1), `activePageIndex` (empty → 0, before first, between pages, past last → last, exact boundary).
- **Browser smoke** (dev servers, as in E6): open a procedure's PDF preview → click `＋`/`−`/`适应` and confirm the pages scale and `%` updates; scroll and confirm `n / N` tracks; click `下一页`/`上一页` and confirm it scrolls + the indicator follows; confirm `window.print()` preview shows no toolbar and unscaled pages; confirm `下载 PDF` still downloads.
- Existing suite stays green (the pure module is additive; `PdfPreviewDialog` has no unit test to break; `pdfModel.spec` untouched). vue-tsc clean.

## Non-goals (YAGNI)

Jump-to-page number input, thumbnail rail, in-preview text search, real download-progress percentage, annotations/markup, cover-layout customization, print-margin/page-size tuning. The publish-flow and version-history polish are separate specs.
