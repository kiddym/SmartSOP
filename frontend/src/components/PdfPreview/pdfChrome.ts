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

/** Parse a 1-based page input to a clamped 0-based index, or null if not a positive integer
 *  (or no pages). e.g. ('3', 12) → 2 ; ('0', 12) → 0 ; ('99', 12) → 11 ; ('abc', 12) → null. */
export function clampPageInput(raw: string | number, count: number): number | null {
  const num = typeof raw === 'number' ? raw : parseInt(String(raw).trim(), 10)
  if (!Number.isInteger(num) || count <= 0) return null
  return Math.min(count - 1, Math.max(0, num - 1))
}

/** Outline label for a preview .page element: 封面 for the cover; else the first section
 *  heading (.sec-title / .chapter-title / .step-title) text; fallback `第 N 页`.
 *  Ignores the running page-header (.ph-title, the repeated procedure name). */
export function pageLabel(el: HTMLElement, index: number): string {
  if (el.classList.contains('cover')) return '封面'
  const h = el.querySelector('.sec-title, .chapter-title, .step-title')
  const text = h?.textContent?.trim() ?? ''
  return text || `第 ${index + 1} 页`
}
