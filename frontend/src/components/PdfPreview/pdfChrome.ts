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
