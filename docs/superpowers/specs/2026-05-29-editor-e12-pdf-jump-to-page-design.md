# E12 — PDF Preview Jump-to-Page — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Small feature extending E7 (PDF preview chrome: zoom + prev/next page nav + `n/N` indicator).
**Status:** Design approved; ready for implementation plan.

## Goal

Make E7's read-only `n / N` page indicator an **editable page-number input**: type a page + Enter/blur → jump there (clamped). Reuses E7's `goPage(i)`. Thumbnails are explicitly deferred (the preview is in-browser HTML, so real thumbnails are disproportionately heavy).

## Background (E7 machinery, present today)

`PdfPreviewDialog.vue` renders all `.page` sections; E7 added:
- `pageEls()`, `currentPage`/`pageCount` refs, `onScroll()` → `activePageIndex` keeps `currentPage` synced to scroll.
- `goPage(i)` — clamps `i` to `[0, pageCount-1]`, `pageEls()[i].scrollIntoView({block:'start'})`, sets `currentPage` (zoom intact).
- Toolbar `.pv-pagenav` (inside `.pv-toolbar.no-print`): `[‹ 上一页]` + `<span class="pv-pageind">{{ currentPage + 1 }} / {{ pageCount }}</span>` + `[下一页 ›]`.
- `pdfChrome.ts` holds the pure chrome helpers (`clampZoom`/`stepZoom`/`fitZoom`/`activePageIndex`); tested in `tests/unit/pdfChrome.spec.ts`.

## Components & changes

### 1. Pure `clampPageInput` — `frontend/src/components/PdfPreview/pdfChrome.ts`

```ts
/** Parse a 1-based page input to a clamped 0-based index, or null if not a positive integer
 *  (or no pages). e.g. ('3', 12) → 2 ; ('0', 12) → 0 ; ('99', 12) → 11 ; ('abc', 12) → null. */
export function clampPageInput(raw: string | number, count: number): number | null {
  const num = typeof raw === 'number' ? raw : parseInt(String(raw).trim(), 10)
  if (!Number.isInteger(num) || count <= 0) return null
  return Math.min(count - 1, Math.max(0, num - 1))
}
```

### 2. `PdfPreviewDialog.vue`

- Add `clampPageInput` to the existing `./pdfChrome` import.
- Add the handler (near `goPage`/`prevPage`/`nextPage`):
  ```ts
  function onPageInput(e: Event): void {
    const el = e.target as HTMLInputElement
    const i = clampPageInput(el.value, pageCount.value)
    if (i !== null) goPage(i)
    el.value = String(currentPage.value + 1) // re-sync after a jump or an invalid entry
  }
  ```
- Replace the `.pv-pageind` span (line 172) with a one-way-bound input (so it tracks scrolling) + the `/ N` label:
  ```html
  <input
    class="pv-pageind pv-pageinput"
    type="text"
    inputmode="numeric"
    :value="currentPage + 1"
    aria-label="跳转到页"
    @change="onPageInput"
    @keyup.enter="onPageInput"
  />
  <span class="pv-pagetotal">/ {{ pageCount }}</span>
  ```
- Style `.pv-pageinput` (narrow, centered, e.g. `width: 34px; text-align: center`); keep it inside `.pv-pagenav` (which is in the `.no-print` toolbar).

## Behaviour / edge cases

- Valid page → `goPage` (clamps + scrolls + sets `currentPage`; E7 zoom unaffected). Out-of-range (`0`, `99`) → clamps to first/last. Non-numeric / empty → no-op; the input value resets to the current page.
- One-way `:value="currentPage + 1"` keeps the number live as the user scrolls (E7's `onScroll`); on commit, `onPageInput` jumps and force-resyncs `el.value`.
- Never prints (toolbar is `.no-print`).

## Testing

- **Unit `frontend/tests/unit/pdfChrome.spec.ts`**: `clampPageInput` — `'3'/12→2`, `'0'/12→0`, `'99'/12→11`, `'abc'/12→null`, `''/12→null`, `('5', 0)→null`.
- **Browser smoke** (reuse E7-style servers): in the preview, type `5`+Enter → scrolls to page 5, indicator shows `5`; an out-of-range entry clamps to first/last; the number tracks while scrolling. (PdfPreviewDialog has no unit test; the dialog needs layout, so the wiring is browser-verified — the decision logic is the pure test.)
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Thumbnails / page-list rail (deferred — heavy for an HTML preview), PageUp/PageDown keys, deep-link/URL-to-page, an `el-input-number` spinner.
