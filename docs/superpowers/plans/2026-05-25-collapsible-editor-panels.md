# 可折叠编辑器面板 + 导入自动折叠 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给编辑页加三处可折叠：全局侧边栏（图标轨）、右侧节点详情栏（对齐 Word 预览：折叠 rail + 拖拽调宽 + 持久化）；并在 Word 导入进入编辑页时自动折叠侧边栏、离开恢复。

**Architecture:** 把 Word 预览已验证的「折叠 + 调宽 + 持久化」逻辑抽成纯函数 `collapsiblePanel.ts` + composable `useCollapsiblePanel` + 展示组件 `CollapsiblePanel.vue`，预览与详情共用；预览本身重构到该组件（旧 util 改薄包装保持测试绿）。侧边栏折叠态用模块级单例 `useSidebar` 跨组件共享，`el-menu` 原生 `:collapse` 实现图标轨。自动折叠 = 给导入那次导航打 `?from=import`，编辑页 `onMounted` 据纯函数 `shouldAutoCollapse` 决定，`onUnmounted` 恢复。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Element Plus 2.7、`@vueuse/core`（`useStorage` / `useEventListener`）、Vitest + `@vue/test-utils`。

**Gate（每次「跑测试」与收尾，均在 `frontend/`）：** `npm run test`；收尾再加 `npm run lint && npm run typecheck && npm run build`（`--max-warnings 0`）。

**单条命令跑单文件：** `npx vitest run tests/unit/<file>.spec.ts`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `src/utils/collapsiblePanel.ts`（新） | 纯函数：宽度夹紧、调宽、拖拽符号、持久化校验 + 类型 |
| `src/utils/editorPreview.ts`（改） | 预览专用薄包装，委托给 `collapsiblePanel`，保留旧导出名 |
| `src/utils/editorFocus.ts`（新） | 纯函数：是否应自动折叠侧边栏 |
| `src/composables/useSidebar.ts`（新） | 侧边栏折叠态模块级单例 + `toggle` |
| `src/composables/useCollapsiblePanel.ts`（新） | 面板折叠/调宽/懒挂载的有状态逻辑 |
| `src/components/shared/CollapsiblePanel.vue`（新） | 可折叠列展示组件，折叠用 `ImportSideRail` |
| `src/components/editor/EditorPreviewPane.vue`（改） | 重构到 `CollapsiblePanel side="left"` |
| `src/layouts/AppLayout.vue`（改） | 图标轨折叠 + 品牌区切换 |
| `src/views/procedures/ProcedureLibraryView.vue`（改） | `onImported` 带 `from:'import'` |
| `src/views/procedures/ProcedureEditorView.vue`（改） | 三栏布局 + 自动折叠/恢复接线 |

---

## Task 1: 纯函数模块 `collapsiblePanel.ts`

**Files:**
- Create: `frontend/src/utils/collapsiblePanel.ts`
- Test: `frontend/tests/unit/utils/collapsiblePanel.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/utils/collapsiblePanel.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  RAIL_PX,
  clampWidth,
  resizePanel,
  dragDelta,
  sanitizePanel,
  type PanelConfig,
} from '@/utils/collapsiblePanel'

const cfg: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }

describe('collapsiblePanel', () => {
  it('RAIL_PX 为 32', () => {
    expect(RAIL_PX).toBe(32)
  })

  it('clampWidth 夹到 [min, max]，非有限回 defaultWidth', () => {
    expect(clampWidth(100, cfg)).toBe(300)
    expect(clampWidth(9999, cfg)).toBe(700)
    expect(clampWidth(500, cfg)).toBe(500)
    expect(clampWidth(Number.NaN, cfg)).toBe(360)
  })

  it('resizePanel 按 delta 调宽并夹紧；collapsed 透传', () => {
    expect(resizePanel({ collapsed: false, width: 400 }, 50, cfg)).toEqual({ collapsed: false, width: 450 })
    expect(resizePanel({ collapsed: false, width: 400 }, -1000, cfg).width).toBe(300)
    expect(resizePanel({ collapsed: true, width: 400 }, 50, cfg).collapsed).toBe(true)
  })

  it('dragDelta：left = x - x0，right = x0 - x', () => {
    expect(dragDelta('left', 120, 100)).toBe(20)
    expect(dragDelta('right', 120, 100)).toBe(-20)
    expect(dragDelta('right', 80, 100)).toBe(20)
  })

  it('sanitizePanel：合法透传；脏值回默认；宽度夹紧', () => {
    expect(sanitizePanel({ collapsed: true, width: 500 }, cfg)).toEqual({ collapsed: true, width: 500 })
    expect(sanitizePanel(null, cfg)).toEqual({ collapsed: false, width: 360 })
    expect(sanitizePanel({ collapsed: 'x', width: 'y' }, cfg)).toEqual({ collapsed: false, width: 360 })
    expect(sanitizePanel({ collapsed: false, width: 99999 }, cfg).width).toBe(700)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run tests/unit/utils/collapsiblePanel.spec.ts`
Expected: FAIL（`Cannot find module '@/utils/collapsiblePanel'`）

- [ ] **Step 3: 写实现**

Create `frontend/src/utils/collapsiblePanel.ts`:

```ts
/** 折叠后竖条宽度，像素。 */
export const RAIL_PX = 32

/** 可折叠面板的折叠态与宽度（像素）。 */
export interface PanelState {
  collapsed: boolean
  width: number
}

/** 面板宽度配置：默认宽 + 边界。 */
export interface PanelConfig {
  defaultWidth: number
  min: number
  max: number
}

/** 夹到 [min, max]；非有限值回 defaultWidth。 */
export function clampWidth(w: number, cfg: PanelConfig): number {
  if (!Number.isFinite(w)) return cfg.defaultWidth
  return Math.min(Math.max(w, cfg.min), cfg.max)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePanel(start: PanelState, deltaPx: number, cfg: PanelConfig): PanelState {
  return { collapsed: start.collapsed, width: clampWidth(start.width + deltaPx, cfg) }
}

/** 拖拽有符号增量：left 列 splitter 在右缘（随右拖增大），right 列在左缘（随左拖增大）。 */
export function dragDelta(side: 'left' | 'right', clientX: number, startX: number): number {
  return side === 'left' ? clientX - startX : startX - clientX
}

/** 校验持久化值：非对象/脏值回 {collapsed:false, width:defaultWidth}；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePanel(v: unknown, cfg: PanelConfig): PanelState {
  if (typeof v !== 'object' || v === null) return { collapsed: false, width: cfg.defaultWidth }
  const o = v as Record<string, unknown>
  if (typeof o.collapsed !== 'boolean' || typeof o.width !== 'number') {
    return { collapsed: false, width: cfg.defaultWidth }
  }
  return { collapsed: o.collapsed, width: clampWidth(o.width, cfg) }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run tests/unit/utils/collapsiblePanel.spec.ts`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/collapsiblePanel.ts frontend/tests/unit/utils/collapsiblePanel.spec.ts
git commit -m "feat(editor): generic collapsible-panel pure helpers"
```

---

## Task 2: `editorPreview.ts` 改为薄包装

**Files:**
- Modify: `frontend/src/utils/editorPreview.ts`（整文件替换）
- Test（不改，作回归）：`frontend/tests/unit/utils/editorPreview.spec.ts`

- [ ] **Step 1: 重写实现（委托给通用模块）**

Replace 全部内容 of `frontend/src/utils/editorPreview.ts`:

```ts
import {
  clampWidth,
  resizePanel,
  sanitizePanel,
  type PanelConfig,
  type PanelState,
} from './collapsiblePanel'

/** 编辑器 Word 预览列的折叠态与宽度（像素）。 */
export type PreviewState = PanelState

/** 预览列宽度边界（像素）。 */
export const PREVIEW_MIN = 240
export const PREVIEW_MAX = 900

/** 预览列宽度配置（默认 460px）。 */
export const PREVIEW_CONFIG: PanelConfig = { defaultWidth: 460, min: PREVIEW_MIN, max: PREVIEW_MAX }

/** 默认：展开、460px。 */
export const PREVIEW_DEFAULTS: Readonly<PreviewState> = {
  collapsed: false,
  width: PREVIEW_CONFIG.defaultWidth,
}

/** 夹到 [MIN, MAX]；非有限值回默认宽度。 */
export function clampPreviewWidth(w: number): number {
  return clampWidth(w, PREVIEW_CONFIG)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePreview(start: PreviewState, deltaPx: number): PreviewState {
  return resizePanel(start, deltaPx, PREVIEW_CONFIG)
}

/** 校验持久化值：非对象/脏值回默认；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePreview(v: unknown): PreviewState {
  return sanitizePanel(v, PREVIEW_CONFIG)
}
```

- [ ] **Step 2: 跑既有测试确认仍绿（等价性回归）**

Run: `npx vitest run tests/unit/utils/editorPreview.spec.ts`
Expected: PASS（3 passed，未改测试）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/utils/editorPreview.ts
git commit -m "refactor(editor): editorPreview delegates to collapsiblePanel"
```

---

## Task 3: 自动折叠决策纯函数 `editorFocus.ts`

**Files:**
- Create: `frontend/src/utils/editorFocus.ts`
- Test: `frontend/tests/unit/utils/editorFocus.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/utils/editorFocus.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { shouldAutoCollapse } from '@/utils/editorFocus'

describe('editorFocus.shouldAutoCollapse', () => {
  it('来自导入且侧边栏展开 → true', () => {
    expect(shouldAutoCollapse('import', false)).toBe(true)
  })
  it('来自导入但侧边栏已折叠 → false', () => {
    expect(shouldAutoCollapse('import', true)).toBe(false)
  })
  it('非导入来源 → false', () => {
    expect(shouldAutoCollapse('other', false)).toBe(false)
    expect(shouldAutoCollapse(undefined, false)).toBe(false)
    expect(shouldAutoCollapse(['import'], false)).toBe(false)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run tests/unit/utils/editorFocus.spec.ts`
Expected: FAIL（`Cannot find module '@/utils/editorFocus'`）

- [ ] **Step 3: 写实现**

Create `frontend/src/utils/editorFocus.ts`:

```ts
/** 进入编辑页是否应自动折叠侧边栏：仅当来自 Word 导入且侧边栏当前展开。 */
export function shouldAutoCollapse(fromQuery: unknown, currentCollapsed: boolean): boolean {
  return fromQuery === 'import' && currentCollapsed === false
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run tests/unit/utils/editorFocus.spec.ts`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/editorFocus.ts frontend/tests/unit/utils/editorFocus.spec.ts
git commit -m "feat(editor): shouldAutoCollapse decision helper"
```

---

## Task 4: 侧边栏单例 composable `useSidebar.ts`

**Files:**
- Create: `frontend/src/composables/useSidebar.ts`
- Test: `frontend/tests/unit/useSidebar.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/useSidebar.spec.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useSidebar } from '@/composables/useSidebar'

beforeEach(() => {
  localStorage.clear()
  // 模块级单例：上条用例可能改过，显式复位再测
  useSidebar().collapsed.value = false
})

describe('useSidebar', () => {
  it('toggle 翻转 collapsed', () => {
    const { collapsed, toggle } = useSidebar()
    expect(collapsed.value).toBe(false)
    toggle()
    expect(collapsed.value).toBe(true)
    toggle()
    expect(collapsed.value).toBe(false)
  })

  it('collapsed 变更落盘 localStorage', () => {
    const { toggle } = useSidebar()
    toggle()
    expect(localStorage.getItem('smartsop.sidebar.collapsed')).toBe('true')
  })

  it('模块级单例：多次调用共享同一 ref', () => {
    const a = useSidebar()
    const b = useSidebar()
    a.toggle()
    expect(b.collapsed.value).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run tests/unit/useSidebar.spec.ts`
Expected: FAIL（`Cannot find module '@/composables/useSidebar'`）

- [ ] **Step 3: 写实现**

Create `frontend/src/composables/useSidebar.ts`:

```ts
import { useStorage } from '@vueuse/core'
import type { Ref } from 'vue'

// 模块级单例 → 同标签页内各组件共享同一响应式 ref（不依赖 storage 事件）。
const collapsed = useStorage<boolean>('smartsop.sidebar.collapsed', false)

export function useSidebar(): { collapsed: Ref<boolean>; toggle: () => void } {
  return {
    collapsed,
    toggle: (): void => {
      collapsed.value = !collapsed.value
    },
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run tests/unit/useSidebar.spec.ts`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/composables/useSidebar.ts frontend/tests/unit/useSidebar.spec.ts
git commit -m "feat(layout): useSidebar singleton for collapse state"
```

---

## Task 5: 面板有状态逻辑 composable `useCollapsiblePanel.ts`

**Files:**
- Create: `frontend/src/composables/useCollapsiblePanel.ts`
- 测试：本任务无独立 spec；其纯逻辑（`dragDelta`/`resizePanel`/`sanitizePanel`）已在 Task 1 覆盖，结构与折叠/展开由 Task 6 的组件测试覆盖。

- [ ] **Step 1: 写实现**

Create `frontend/src/composables/useCollapsiblePanel.ts`:

```ts
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
```

- [ ] **Step 2: typecheck 确认无类型错误**

Run: `npm run typecheck`
Expected: 无错误（其余文件可能在后续任务才引用，本步只验证本文件自身类型）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/composables/useCollapsiblePanel.ts
git commit -m "feat(editor): useCollapsiblePanel stateful collapse/resize logic"
```

---

## Task 6: 展示组件 `CollapsiblePanel.vue`

**Files:**
- Create: `frontend/src/components/shared/CollapsiblePanel.vue`
- Test: `frontend/tests/unit/CollapsiblePanel.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/CollapsiblePanel.spec.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import type { PanelConfig } from '@/utils/collapsiblePanel'

const cfg: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }
const stubs = {
  ImportSideRail: {
    props: ['label', 'side'],
    emits: ['expand'],
    template: '<div class="stub-rail" :data-side="side" @click="$emit(\'expand\')">{{ label }}</div>',
  },
}

function mountPanel(side: 'left' | 'right', storageKey = `k-${side}`) {
  return mount(CollapsiblePanel, {
    props: { label: '节点详情', side, storageKey, config: cfg },
    slots: { default: '<div class="stub-content">X</div>' },
    global: { stubs },
  })
}

beforeEach(() => localStorage.clear())

describe('CollapsiblePanel', () => {
  it('展开态渲染 slot 内容、不渲染 rail', () => {
    const w = mountPanel('right')
    expect(w.find('.stub-content').exists()).toBe(true)
    expect(w.find('.stub-rail').exists()).toBe(false)
  })

  it('点折叠按钮 → 显示 rail；点 rail → 还原 slot', async () => {
    const w = mountPanel('right')
    await w.get('.collapse-btn').trigger('click')
    expect(w.find('.stub-rail').exists()).toBe(true)
    expect(w.find('.stub-content').exists()).toBe(false)
    await w.get('.stub-rail').trigger('click')
    expect(w.find('.stub-content').exists()).toBe(true)
  })

  it('side=left → 折叠箭头 «、splitter 在右缘', () => {
    const w = mountPanel('left')
    expect(w.get('.collapse-btn').text()).toBe('«')
    expect(w.find('.splitter-right').exists()).toBe(true)
  })

  it('side=right → 折叠箭头 »、splitter 在左缘', () => {
    const w = mountPanel('right')
    expect(w.get('.collapse-btn').text()).toBe('»')
    expect(w.find('.splitter-left').exists()).toBe(true)
  })

  it('折叠态把 side 透传给 rail', async () => {
    const w = mountPanel('right')
    await w.get('.collapse-btn').trigger('click')
    expect(w.get('.stub-rail').attributes('data-side')).toBe('right')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run tests/unit/CollapsiblePanel.spec.ts`
Expected: FAIL（`Failed to resolve import .../CollapsiblePanel.vue`）

- [ ] **Step 3: 写实现**

Create `frontend/src/components/shared/CollapsiblePanel.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import ImportSideRail from '@/components/shared/ImportSideRail.vue'
import { useCollapsiblePanel } from '@/composables/useCollapsiblePanel'
import { RAIL_PX, type PanelConfig } from '@/utils/collapsiblePanel'

const props = defineProps<{
  label: string
  side: 'left' | 'right'
  storageKey: string
  config: PanelConfig
}>()

const { state, everShown, onDragStart, resetWidth, collapse, expand } = useCollapsiblePanel(
  props.storageKey,
  props.config,
  props.side,
)

// 折叠按钮朝该列收起方向：left → «，right → »（与 rail 展开箭头相反）。
const collapseArrow = computed(() => (props.side === 'left' ? '«' : '»'))
</script>

<template>
  <div
    class="panel-col"
    :class="side === 'left' ? 'panel-col-left' : 'panel-col-right'"
    :style="{ width: (state.collapsed ? RAIL_PX : state.width) + 'px' }"
  >
    <ImportSideRail v-if="state.collapsed" :label="label" :side="side" @expand="expand" />
    <template v-else>
      <div v-if="everShown" class="panel-body"><slot /></div>
      <div
        class="panel-splitter"
        :class="side === 'left' ? 'splitter-right' : 'splitter-left'"
        title="拖拽调宽，双击重置"
        @pointerdown="onDragStart"
        @dblclick="resetWidth"
      >
        <button
          class="collapse-btn"
          :title="`折叠${label}`"
          @click.stop="collapse"
          @pointerdown.stop
        >{{ collapseArrow }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.panel-col {
  flex: none;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.panel-col-left { border-right: 1px solid var(--el-border-color-lighter, #ebeef5); }
.panel-col-right { border-left: 1px solid var(--el-border-color-lighter, #ebeef5); }
.panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.panel-splitter {
  position: absolute;
  top: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
  touch-action: none;
}
.splitter-right { right: -3px; }
.splitter-left { left: -3px; }
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
  color: #909399;
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
}
.panel-splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary, #d97757); border-color: var(--el-color-primary, #d97757); }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run tests/unit/CollapsiblePanel.spec.ts`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/shared/CollapsiblePanel.vue frontend/tests/unit/CollapsiblePanel.spec.ts
git commit -m "feat(editor): CollapsiblePanel shared component"
```

---

## Task 7: `EditorPreviewPane.vue` 重构到 `CollapsiblePanel`

**Files:**
- Modify: `frontend/src/components/editor/EditorPreviewPane.vue`（整文件替换）
- Modify: `frontend/tests/unit/EditorPreviewPane.spec.ts`（仅改列选择器 `.preview-col`→`.panel-col`）

- [ ] **Step 1: 改测试选择器（行为断言不变）**

In `frontend/tests/unit/EditorPreviewPane.spec.ts`，把两处 `.preview-col` 改为 `.panel-col`：

- 第 1 个用例：`expect(w.find('.panel-col').exists()).toBe(false)`
- 第 2 个用例：`expect(w.find('.panel-col').exists()).toBe(true)`

其余（`.stub-preview` / `.collapse-btn` / `.stub-rail` 与各断言）保持不变。

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run tests/unit/EditorPreviewPane.spec.ts`
Expected: FAIL（旧组件根类仍是 `.preview-col`，找不到 `.panel-col`）

- [ ] **Step 3: 重写组件**

Replace 全部内容 of `frontend/src/components/editor/EditorPreviewPane.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import WordPreviewPanel from '@/components/shared/WordPreviewPanel.vue'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { fetchSourceDocx } from '@/api/procedures'
import { PREVIEW_CONFIG } from '@/utils/editorPreview'

const props = defineProps<{ procedureId: string }>()

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const file = ref<File | null>(null)

onMounted(async () => {
  const got = await fetchSourceDocx(props.procedureId)
  if (!got) return
  file.value = new File([got.blob], got.filename, { type: DOCX_MIME })
})
</script>

<template>
  <CollapsiblePanel
    v-if="file"
    label="Word 原文预览"
    side="left"
    storage-key="smartsop.editor.preview"
    :config="PREVIEW_CONFIG"
  >
    <WordPreviewPanel :file="file" class="fill-panel" />
  </CollapsiblePanel>
</template>

<style scoped>
.fill-panel {
  flex: 1;
  min-height: 0;
}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run tests/unit/EditorPreviewPane.spec.ts`
Expected: PASS（3 passed —— 无原文不渲染、有原文渲染、折叠/还原）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/EditorPreviewPane.vue frontend/tests/unit/EditorPreviewPane.spec.ts
git commit -m "refactor(editor): EditorPreviewPane onto CollapsiblePanel"
```

---

## Task 8: `AppLayout.vue` 侧边栏图标轨折叠

**Files:**
- Modify: `frontend/src/layouts/AppLayout.vue`（整文件替换）
- 无独立 spec（router 依赖；核心逻辑已由 `useSidebar.spec` 覆盖）。

- [ ] **Step 1: 重写组件**

Replace 全部内容 of `frontend/src/layouts/AppLayout.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, EditPen, Folder, Setting, Fold, Expand } from '@element-plus/icons-vue'
import { useSidebar } from '@/composables/useSidebar'

const route = useRoute()
const { collapsed, toggle } = useSidebar()

// 顶层菜单高亮：详情页 /procedures/:id 归到「程序库」
const activeMenu = computed(() => {
  if (route.path.startsWith('/settings/fields')) return '/settings/fields'
  if (route.path.startsWith('/settings')) return '/settings'
  if (route.path.startsWith('/audit-logs')) return '/audit-logs'
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  return '/procedures/library'
})
</script>

<template>
  <el-container class="app-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="app-aside">
      <div class="app-brand" :class="{ collapsed }">
        <span v-if="!collapsed" class="brand-text">Smart SOP</span>
        <span v-else class="brand-mark">S</span>
        <button
          class="brand-toggle"
          :title="collapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="toggle"
        >
          <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
        </button>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="app-menu"
        text-color="#3a3530"
        active-text-color="#d97757"
        background-color="transparent"
      >
        <el-menu-item index="/procedures/library">
          <el-icon><Document /></el-icon>
          <span>程序库</span>
        </el-menu-item>
        <el-menu-item index="/procedures/drafts">
          <el-icon><EditPen /></el-icon>
          <span>草稿箱</span>
        </el-menu-item>
        <el-menu-item index="/audit-logs">
          <el-icon><Document /></el-icon>
          <span>审计日志</span>
        </el-menu-item>
        <el-menu-item index="/folders">
          <el-icon><Folder /></el-icon>
          <span>标准文件库</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/settings/fields">
          <el-icon><Setting /></el-icon>
          <span>字段管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="app-main">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </el-main>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-aside {
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0dbd3;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.04);
  transition: width 0.2s ease;
}
.app-brand {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  padding: 14px 20px;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e0dbd3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  box-sizing: border-box;
}
.app-brand.collapsed {
  padding: 14px 0;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
}
.brand-mark {
  font-size: 18px;
}
.brand-toggle {
  border: none;
  background: transparent;
  padding: 4px;
  cursor: pointer;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  border-radius: 4px;
}
.brand-toggle:hover {
  color: #d97757;
  background: rgba(0, 0, 0, 0.04);
}
.app-menu {
  border-right: none;
  background: transparent;
  flex: 1;
}
.app-main {
  padding: 20px 24px;
  background: #faf8f4;
  overflow: auto;
}
</style>
```

- [ ] **Step 2: 跑全量单测 + typecheck + build 确认无回归**

Run: `npm run test && npm run typecheck && npm run build`
Expected: 全 PASS、typecheck 无错、build 成功

- [ ] **Step 3: 手动冒烟**

启动前端，确认：点品牌区折叠按钮 → 侧边栏收成 64px 图标轨、hover 图标出 tooltip、点图标仍能导航、再点展开恢复；刷新后保持上次折叠态。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/layouts/AppLayout.vue
git commit -m "feat(layout): collapsible sidebar icon-rail"
```

---

## Task 9: `ProcedureLibraryView.vue` 导入导航打标

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureLibraryView.vue:50-52`（`onImported`）

- [ ] **Step 1: 改 onImported 带 from=import**

Replace in `frontend/src/views/procedures/ProcedureLibraryView.vue`:

```ts
function onImported(id: string): void {
  void router.push(`/procedures/${id}/edit`)
}
```

with:

```ts
function onImported(id: string): void {
  void router.push({ path: `/procedures/${id}/edit`, query: { from: 'import' } })
}
```

- [ ] **Step 2: typecheck 确认通过**

Run: `npm run typecheck`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/procedures/ProcedureLibraryView.vue
git commit -m "feat(import): tag editor navigation with from=import"
```

---

## Task 10: `ProcedureEditorView.vue` 三栏布局 + 自动折叠接线

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`（script imports、onMounted、新增 onUnmounted、template body、style）

- [ ] **Step 1: 扩展 script 顶部 imports 与状态**

把第 2 行的 vue import 改为含 `onUnmounted` 与 `watch`：

```ts
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
```

在第 22 行 `import EditorPreviewPane ...` 之后追加：

```ts
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { useSidebar } from '@/composables/useSidebar'
import { shouldAutoCollapse } from '@/utils/editorFocus'
import type { PanelConfig } from '@/utils/collapsiblePanel'
```

在 `const treeRef = ref(...)`（约第 35 行）之后追加：

```ts
const sidebar = useSidebar()
const autoCollapsed = ref(false)
const priorCollapsed = ref<boolean | null>(null)
const DETAIL_CFG: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }
```

- [ ] **Step 2: 在 onMounted 末尾加自动折叠 + 建立手动接管 watch**

把现有 `onMounted` 改为（在 `persistence.start()` 之后追加逻辑）：

```ts
onMounted(async () => {
  await store.load(id.value)
  if (store.loadError) return
  // 路由守卫：访问 /edit 但不可编辑 → 跳只读 /view（不留历史）。
  if (route.name === 'procedure-edit' && !store.editable) {
    void router.replace({ name: 'procedure-view', params: { id: id.value } })
    return
  }
  await persistence.tryRestore()
  persistence.start()

  // Word 导入进入 → 专注模式：自动折叠侧边栏（离开恢复）。
  if (shouldAutoCollapse(route.query.from, sidebar.collapsed.value)) {
    priorCollapsed.value = sidebar.collapsed.value
    sidebar.collapsed.value = true
    autoCollapsed.value = true
    void router.replace({ path: route.path, query: {} }) // 抹掉 from，防刷新重触发
  }
  // 在自动折叠之后建立 watch：用户编辑中手动切换即「接管」，离开不再恢复。
  watch(
    () => sidebar.collapsed.value,
    () => {
      autoCollapsed.value = false
    },
  )
})
```

- [ ] **Step 3: 加 onUnmounted 恢复**

在 `onBeforeRouteLeave(...)` 之前（约第 209 行）追加：

```ts
onUnmounted(() => {
  // 仅当本页自动折叠且用户未手动接管时，离开恢复进来前的状态。
  if (autoCollapsed.value) {
    sidebar.collapsed.value = priorCollapsed.value ?? false
  }
})
```

- [ ] **Step 4: 改 template —— 树 flex、详情包 CollapsiblePanel**

把 `<div class="body">...</div>` 整块（约第 269-306 行）替换为：

```html
<div class="body">
  <EditorPreviewPane v-if="store.hasSourceDocx" :procedure-id="store.procedure.id" />
  <div class="left">
    <ChapterTreePanel ref="treeRef" />
  </div>
  <CollapsiblePanel
    label="节点详情"
    side="right"
    storage-key="smartsop.editor.detail"
    :config="DETAIL_CFG"
  >
    <div class="right-scroll">
      <ProcedureDetailsPanel />
      <el-tabs v-model="activeTab" class="tabs">
        <el-tab-pane label="节点详情" name="node">
          <div class="pane">
            <ChapterDetailPanel v-if="kind === 'chapter'" :key="store.selectedId ?? 'none'" />
            <ContentDetailPanel v-else-if="kind === 'content'" :key="store.selectedId ?? 'none'" />
            <StepDetailPanel v-else-if="kind === 'step'" :key="store.selectedId ?? 'none'" />
            <el-empty v-else description="选择左侧节点进行编辑" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="附件" name="attach">
          <AttachmentPanel
            :procedure-id="store.procedure.id"
            :editable="store.editable"
            class="pane"
          />
        </el-tab-pane>
        <el-tab-pane label="版本历史" name="history">
          <el-timeline v-if="store.procedure.version_change_log.length" class="pane">
            <el-timeline-item
              v-for="(entry, i) in store.procedure.version_change_log"
              :key="i"
              :timestamp="formatDateTime(String(entry.changed_at ?? ''))"
            >
              {{ entry.change_type }} — {{ entry.description || '' }}
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无版本记录（回退 / 升级见 Phase 7）" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </CollapsiblePanel>
</div>
```

- [ ] **Step 5: 改 style —— 树 flex:1，移除旧 .right，加 .right-scroll**

把 `<style scoped>` 里的 `.left` / `.right` 两块（约第 337-348 行）：

```css
.left {
  width: 340px;
  flex: none;
  min-height: 0;
}
.right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow-y: auto;
}
```

替换为：

```css
.left {
  flex: 1;
  min-width: 280px;
  min-height: 0;
}
.right-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
```

（`.tabs` / `.pane` / `.body` / `.editor` 等其余样式不动。）

- [ ] **Step 6: 全量 Gate**

Run: `npm run test && npm run lint && npm run typecheck && npm run build`
Expected: 全 PASS、lint 0 warning、typecheck 无错、build 成功

- [ ] **Step 7: 手动冒烟（核心验收）**

启动前端，验证：
1. **导入自动折叠**：程序库「从 Word 导入」成功进入编辑页 → 侧边栏自动折叠成图标轨。
2. **离开恢复**：从该编辑页返回程序库 → 侧边栏恢复展开。
3. **手动接管**：导入进入（已自动折叠）后手动点展开 → 返回后侧边栏保持展开（不被强行恢复/折叠）。
4. **打开已有草稿不折叠**：直接打开一个已有草稿编辑 → 侧边栏不自动折叠。
5. **详情栏折叠/调宽**：右侧「节点详情」可点折叠成右侧 rail、点 rail 还原、拖左缘调宽、双击重置、刷新后保持。
6. **三栏联动**：预览 + 详情都折叠时，中间章节树填满；长章节标题不再被截断。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/views/procedures/ProcedureEditorView.vue
git commit -m "feat(editor): collapsible detail panel + import focus-mode sidebar"
```

---

## 收尾

- [ ] **全量 Gate 最终确认**

Run（在 `frontend/`）: `npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿（lint `--max-warnings 0`）

- [ ] **完成开发分支**：使用 superpowers:finishing-a-development-branch 决定合并 / PR / 清理。

---

## Self-Review 记录

- **Spec 覆盖**：侧边栏图标轨折叠（T4/T8）、详情栏对齐预览折叠+调宽+持久化（T1/T5/T6/T10）、共享抽象+预览重构（T1/T2/T5/T6/T7）、导入自动折叠+离开恢复+手动接管（T3/T9/T10）—— 全覆盖。
- **类型一致**：`PanelState` / `PanelConfig` / `dragDelta` / `sanitizePanel`（T1）→ `useCollapsiblePanel`（T5）→ `CollapsiblePanel`（T6）；`PREVIEW_CONFIG`（T2）→ `EditorPreviewPane`（T7）；`useSidebar` 返回 `{collapsed,toggle}`（T4）→ `AppLayout`（T8）/`ProcedureEditorView`（T10）；`shouldAutoCollapse`（T3）→ T10 一致。
- **回归保证**：`editorPreview.spec.ts` 不改即绿（T2）；`EditorPreviewPane.spec.ts` 仅改列选择器（T7）；`ImportSideRail.spec.ts` 不改。
- **无占位符**：所有步骤含完整代码 / 命令 / 预期。
