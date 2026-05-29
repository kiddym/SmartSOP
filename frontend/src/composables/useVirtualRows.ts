import { computed, onMounted, onUnmounted, ref, type ComputedRef, type Ref } from 'vue'

export const ROW_H = 30
export const OVERSCAN = 8
export const MIN_TO_VIRTUALIZE = 60

export interface RowWindow {
  start: number
  end: number
  padTop: number
  padBottom: number
}

/** Pure: which slice [start,end) of `total` fixed-height rows to render.
 *  Degrades to render-all when the viewport is unmeasured (height 0) or the list is small. */
export function computeWindow(
  scrollTop: number,
  viewportH: number,
  total: number,
  rowH = ROW_H,
  overscan = OVERSCAN,
  minToVirtualize = MIN_TO_VIRTUALIZE,
): RowWindow {
  if (viewportH <= 0 || total <= minToVirtualize) {
    return { start: 0, end: total, padTop: 0, padBottom: 0 }
  }
  const first = Math.floor(scrollTop / rowH)
  const visible = Math.ceil(viewportH / rowH)
  const start = Math.max(0, first - overscan)
  const end = Math.min(total, first + visible + overscan)
  return { start, end, padTop: start * rowH, padBottom: (total - end) * rowH }
}

/** Pure: the scrollTop needed to bring row `index` into view, or null if already visible. */
export function scrollOffsetFor(
  index: number,
  scrollTop: number,
  viewportH: number,
  rowH = ROW_H,
): number | null {
  if (index < 0 || viewportH <= 0) return null
  const top = index * rowH
  const bottom = top + rowH
  if (top < scrollTop) return top
  if (bottom > scrollTop + viewportH) return bottom - viewportH
  return null
}

export function useVirtualRows(
  containerRef: Ref<HTMLElement | null>,
  total: () => number,
): {
  start: ComputedRef<number>
  end: ComputedRef<number>
  padTop: ComputedRef<number>
  padBottom: ComputedRef<number>
  totalHeight: ComputedRef<number>
  scrollToIndex: (index: number) => void
} {
  const scrollTop = ref(0)
  const viewportH = ref(0)

  const measure = (): void => {
    const el = containerRef.value
    if (!el) return
    scrollTop.value = el.scrollTop
    viewportH.value = el.clientHeight
  }

  const win = computed(() => computeWindow(scrollTop.value, viewportH.value, total()))
  const start = computed(() => win.value.start)
  const end = computed(() => win.value.end)
  const padTop = computed(() => win.value.padTop)
  const padBottom = computed(() => win.value.padBottom)
  const totalHeight = computed(() => total() * ROW_H)

  function scrollToIndex(index: number): void {
    const el = containerRef.value
    if (!el) return
    const next = scrollOffsetFor(index, scrollTop.value, viewportH.value)
    if (next != null) {
      el.scrollTop = next
      scrollTop.value = next // jsdom won't fire scroll on programmatic set; keep state in sync
    }
  }

  let ro: ResizeObserver | null = null
  onMounted(() => {
    const el = containerRef.value
    if (!el) return
    measure()
    el.addEventListener('scroll', measure, { passive: true })
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => { viewportH.value = el.clientHeight })
      ro.observe(el)
    }
  })
  onUnmounted(() => {
    const el = containerRef.value
    if (el) el.removeEventListener('scroll', measure)
    ro?.disconnect()
    ro = null
  })

  return { start, end, padTop, padBottom, totalHeight, scrollToIndex }
}
