import { ref, watch, type Ref } from 'vue'
import { useStorage, useEventListener } from '@vueuse/core'
import {
  dragDelta,
  resizePanel,
  sanitizePanel,
  type PanelConfig,
  type PanelState,
} from '@/utils/collapsiblePanel'

export interface CollapsiblePanelApi {
  state: Ref<PanelState>
  everShown: Ref<boolean>
  onDragStart: (e: PointerEvent) => void
  resetWidth: () => void
  collapse: () => void
  expand: () => void
}

export function useCollapsiblePanel(
  storageKey: string,
  cfg: PanelConfig,
  side: 'left' | 'right',
): CollapsiblePanelApi {
  const state = useStorage<PanelState>(storageKey, { collapsed: false, width: cfg.defaultWidth })
  state.value = sanitizePanel(state.value, cfg)

  // 首次展开后才挂载内容（懒挂载重型子组件，沿用预览既有行为）。
  const everShown = ref(!state.value.collapsed)
  watch(
    () => state.value.collapsed,
    (c) => {
      if (!c) everShown.value = true
    },
  )

  // 拖拽调宽
  const drag = ref<{ startX: number; startW: number } | null>(null)
  function onDragStart(e: PointerEvent): void {
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    drag.value = { startX: e.clientX, startW: state.value.width }
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
  }
  function endDrag(): void {
    if (!drag.value) return
    drag.value = null
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
  }
  useEventListener(window, 'pointermove', (e: PointerEvent) => {
    if (!drag.value) return
    state.value = resizePanel(
      { collapsed: false, width: drag.value.startW },
      dragDelta(side, e.clientX, drag.value.startX),
      cfg,
    )
  })
  useEventListener(window, 'pointerup', endDrag)
  useEventListener(window, 'pointercancel', endDrag)

  function collapse(): void {
    state.value = { ...state.value, collapsed: true }
  }
  function expand(): void {
    state.value = { ...state.value, collapsed: false }
  }
  function resetWidth(): void {
    state.value = { collapsed: false, width: cfg.defaultWidth }
  }

  return { state, everShown, onDragStart, resetWidth, collapse, expand }
}
