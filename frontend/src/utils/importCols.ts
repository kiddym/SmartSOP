/** Column widths as percentages of the 3-column import layout. `right` is derived. */
export interface ColWidths {
  left: number
  mid: number
}

/** Default split: left 38% / mid 28% / right 34%. */
export const COL_DEFAULTS: Readonly<ColWidths> = { left: 38, mid: 28 }

/** Minimum width any single column may occupy, in percent. */
export const COL_MIN = 18

function clamp(v: number, lo: number, hi: number): number {
  if (!Number.isFinite(v)) return lo // NaN / ±Infinity → lower bound
  return Math.min(Math.max(v, lo), hi)
}

/** Derived right-column width. */
export function rightOf(c: ColWidths): number {
  return 100 - c.left - c.mid
}

/**
 * Drag the left|mid boundary by `deltaPct` (percent of container width).
 * Left grows, mid shrinks by the same amount; right is untouched.
 * Both left and mid stay >= COL_MIN.
 */
export function resizeLeftMid(start: ColWidths, deltaPct: number): ColWidths {
  const pair = start.left + start.mid
  const left = clamp(start.left + deltaPct, COL_MIN, pair - COL_MIN)
  return { left, mid: pair - left }
}

/**
 * Drag the mid|right boundary by `deltaPct`.
 * Mid grows, right shrinks; left is untouched.
 * Both mid and right stay >= COL_MIN.
 */
export function resizeMidRight(start: ColWidths, deltaPct: number): ColWidths {
  const maxMid = 100 - start.left - COL_MIN
  const mid = clamp(start.mid + deltaPct, COL_MIN, maxMid)
  return { left: start.left, mid }
}

/** Validate a persisted value; fall back to defaults if missing/dirty/out-of-bounds. */
export function sanitizeCols(v: unknown): ColWidths {
  if (
    typeof v === 'object' &&
    v !== null &&
    typeof (v as ColWidths).left === 'number' &&
    typeof (v as ColWidths).mid === 'number'
  ) {
    const { left, mid } = v as ColWidths
    if (left >= COL_MIN && mid >= COL_MIN && left + mid <= 100 - COL_MIN) {
      return { left, mid }
    }
  }
  return { ...COL_DEFAULTS }
}

/** Width of a collapsed column's rail, in pixels. */
export const RAIL_PX = 32

/** Collapse state of the left/right columns (mid is never collapsible). */
export interface CollapseState {
  left: boolean
  right: boolean
}

/** Per-column CSS flex values plus splitter visibility. */
export interface ColFlex {
  left: string
  mid: string
  right: string
  showLM: boolean
  showMR: boolean
}

/**
 * Derives each column's flex value and splitter visibility from widths + collapse state.
 * Visible columns use `"<pct> 1 0%"` (flex-grow weighted to share remaining space);
 * a collapsed column uses `"0 0 ${RAIL_PX}px"`; the splitter on a collapsed side is hidden.
 */
export function colFlex(c: ColWidths, s: CollapseState): ColFlex {
  const rail = `0 0 ${RAIL_PX}px`
  const grow = (n: number): string => `${n} 1 0%`
  return {
    left: s.left ? rail : grow(c.left),
    mid: grow(c.mid),
    right: s.right ? rail : grow(rightOf(c)),
    showLM: !s.left,
    showMR: !s.right,
  }
}

/** Validate a persisted collapse value; any non-boolean field becomes false, a non-object falls back to all-expanded. */
export function sanitizeCollapsed(v: unknown): CollapseState {
  if (typeof v !== 'object' || v === null) return { left: false, right: false }
  const o = v as Record<string, unknown>
  return {
    left: o.left === true,
    right: o.right === true,
  }
}
