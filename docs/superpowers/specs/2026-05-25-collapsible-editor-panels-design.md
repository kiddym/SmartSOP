# 可折叠的编辑器面板（侧边栏 / 原文 / 详情）+ 导入进入自动折叠 设计

**日期：** 2026-05-25
**状态：** 待批准
**作者：** 协作设计（cui_yuming + Claude）

## 背景与目标

统一「创建 / 编辑」模型后，编辑页 `ProcedureEditorView` 实际叠了四栏：

- **最左**：全局侧边栏（`AppLayout.vue`，固定 220px：Smart SOP 导航——程序库 / 草稿箱 / 审计日志 / 标准文件库 / 系统设置 / 字段管理）
- **左**：Word 原文预览（`EditorPreviewPane.vue`，已可折叠 / 拖拽调宽 / 持久化）
- **中**：章节树（`.left`，固定 340px，用户主要工作区 `ChapterTreePanel`）
- **右**：节点详情（`.right`，`flex:1`，`ProcedureDetailsPanel` + 节点 / 附件 / 版本历史 Tabs）

详情栏 `flex:1` 是它「摊得很大」的根因：章节节点常常只有一个标题输入 + 一个跳号开关 + 「暂无子节点」空态，却占满整列。截图显示屏幕拥挤、章节标题被截断成「…」。

`EditorPreviewPane` 已经具备我们想要的全部能力：折叠成一根 `ImportSideRail`（竖排标签 + `«`/`»` 箭头）、拖拽调宽、状态持久化到 localStorage。本设计把这套能力**抽成共享件**，并应用到右侧详情栏；同时给全局侧边栏加图标轨折叠。

> 注：`ImportSideRail.vue` 源自上一份 [`2026-05-25-collapsible-import-panels-design.md`]，统一入口（P3）后已从 `components/import-v2/` 迁到 `components/shared/`，本设计复用之。

**目标：**

1. **全局侧边栏**一键折叠成**图标轨**（Element Plus `el-menu` 原生 `collapse`，220px ↔ 64px，导航仍可点）。全局生效、状态持久化、默认展开。
2. **右侧节点详情栏**完全对齐 Word 原文预览：折叠成 rail + 拖拽调宽 + 状态持久化。
3. 把预览的「折叠 + 调宽 + 持久化」逻辑抽成**共享 composable + 组件**，预览与详情共用；现有可用的预览代码做小幅重构（有测试兜底）。
4. **从 Word 导入进入编辑页时自动折叠侧边栏**（专注模式）：仅导入那次进入触发；离开编辑页恢复进来前的状态；编辑中若手动切换侧边栏，则尊重手动选择、不再恢复。

## 范围

**做：**

- 抽通用 `collapsiblePanel.ts`（纯函数）+ `useCollapsiblePanel`（composable）+ `CollapsiblePanel.vue`（展示组件）。
- `EditorPreviewPane` 重构到 `CollapsiblePanel`（行为不变，键不变）。
- 右侧详情栏用 `CollapsiblePanel side="right"` 包裹：折叠成 rail + 左缘 splitter 调宽 + 持久化。
- 编辑页三栏改为：预览（固定可调可折叠）/ 树（`flex:1`，可增长）/ 详情（固定可调可折叠）。
- 全局侧边栏图标轨折叠（`AppLayout` + `useSidebar` 单例 composable）。
- Word 导入进入自动折叠 + 离开恢复（决策抽成纯函数 `editorFocus.ts`）。

**不做（YAGNI）：**

- 移动端 / 窄屏响应式。
- 折叠动画 / 过渡（沿用 Element Plus `el-menu` 自带过渡即可，先求正确）。
- 折叠 / 展开的键盘快捷键。
- 中栏（章节树）折叠。
- 改动已退役的 import dialog（与本页独立）。
- 改动 `WordPreviewPanel` / 各详情面板（`ChapterDetailPanel` 等）内部。

## 架构

### A. 编辑页布局变更（`ProcedureEditorView.vue`）

三栏改为对称结构，中栏柔性：

```
[预览]            [树]              [详情]
固定宽、可调、     flex:1，          固定宽、可调、
可折叠            min-width ~280px   可折叠
```

- `.left`（树）：`flex:1`（取代现 340px 固定）+ `min-width: 280px`，吸收任何被释放的空间——附带修掉被截断的章节标题。
- `.right`（详情）：用 `CollapsiblePanel side="right"` 包裹 `ProcedureDetailsPanel` + Tabs，变成固定宽度、左缘 splitter 可调、可折叠成右侧 rail。键 `smartsop.editor.detail`，config `{defaultWidth:360, min:300, max:700}`，label「节点详情」，默认展开。
- 预览折叠和 / 或详情折叠 → 树自动填满。两者都折叠 → 树独占。

### B. 共享折叠 / 调宽抽象（预览 + 详情共用）

**1. `utils/collapsiblePanel.ts`（新，纯函数 + 通用类型）**

```ts
/** 折叠后竖条宽度，像素。 */
export const RAIL_PX = 32

/** 可折叠面板的折叠态与宽度（像素）。 */
export interface PanelState { collapsed: boolean; width: number }

/** 面板宽度配置：默认宽 + 边界。 */
export interface PanelConfig { defaultWidth: number; min: number; max: number }

/** 夹到 [min, max]；非有限值回 defaultWidth。 */
export function clampWidth(w: number, cfg: PanelConfig): number

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePanel(start: PanelState, deltaPx: number, cfg: PanelConfig): PanelState

/** 拖拽的有符号增量：left 列 splitter 在右缘（随右拖增大），right 列在左缘（随左拖增大）。 */
export function dragDelta(side: 'left' | 'right', clientX: number, startX: number): number

/** 校验持久化值：非对象 / 脏值回 {collapsed:false, width:defaultWidth}；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePanel(v: unknown, cfg: PanelConfig): PanelState
```

**2. `utils/editorPreview.ts`（改为薄包装，保持向后兼容）**

保留现有全部导出名（`PreviewState`、`PREVIEW_DEFAULTS`、`PREVIEW_MIN`、`PREVIEW_MAX`、`clampPreviewWidth`、`resizePreview`、`sanitizePreview`），内部委托给通用模块、固定预览自己的 `PanelConfig`（`{defaultWidth:460, min:240, max:900}`）。

→ **现有 `tests/unit/utils/editorPreview.spec.ts` 不改即绿**，作为重构等价性的回归保证。

**3. `composables/useCollapsiblePanel.ts`（新）**

入参：`(storageKey: string, cfg: PanelConfig, side: 'left' | 'right')`。职责：

- `useStorage<PanelState>(storageKey, {collapsed:false, width:cfg.defaultWidth})`，加载时过 `sanitizePanel`。
- 指针拖拽（pointerdown / move / up，pointer capture）。delta 用纯函数 `dragDelta(side, clientX, startX)` 计算（`left` → `clientX - startX`；`right` → `startX - clientX`），再交给 `resizePanel`。
- `everShown`：首次展开后置 true（懒挂载重型内容，沿用预览既有行为）。
- `resetWidth()`：宽度回 `cfg.defaultWidth`（双击 splitter）。
- 返回 `{ state, everShown, onDragStart, resetWidth }`；window 级 move/up/cancel 用 `useEventListener` 注册（随组件卸载自动清理）。

**4. `components/shared/CollapsiblePanel.vue`（新展示组件）**

- **props**：`{ label: string; side: 'left' | 'right'; storageKey: string; config: PanelConfig }`。
- 内部用 `useCollapsiblePanel`。
- **折叠态**：渲染 `ImportSideRail :label :side`，点击 `@expand` → `state.collapsed=false`。
- **展开态**：根列 `:style="{ width: state.width + 'px' }"`，渲染默认 `<slot>`（仅 `everShown` 后挂载）+ splitter；splitter 位置由 `side` 决定（`left`→右缘，`right`→左缘），含折叠按钮（朝该列收起方向：`left`→`«`，`right`→`»`）、`@click.stop` 折叠 + `@pointerdown.stop`、`@dblclick` 重置。注意：这与折叠态 `ImportSideRail` 的展开箭头方向相反（rail 展开箭头 `left`→`»`、`right`→`«`，朝面板展开方向）。
- 折叠态根列宽固定 `RAIL_PX`。

**5. `EditorPreviewPane.vue` 重构到 `CollapsiblePanel side="left"`**

- 键不变 `smartsop.editor.preview`，config `{defaultWidth:460, min:240, max:900}`，label「Word 原文预览」。
- `WordPreviewPanel` 放进 slot，懒挂载经 `CollapsiblePanel` 的 `everShown` 控制（沿用现行为：首次展开才挂载）。
- `fetchSourceDocx` 取文件逻辑保留在 `EditorPreviewPane`；无源文件时不渲染（同现状）。

### C. 全局侧边栏图标轨（`AppLayout.vue` + `useSidebar`）

**`composables/useSidebar.ts`（新，模块级单例）：**

```ts
import { useStorage } from '@vueuse/core'
// 模块级单例 → 同标签页内各组件共享同一个响应式 ref（不依赖 storage 事件）。
const collapsed = useStorage('smartsop.sidebar.collapsed', false)
export function useSidebar() {
  return { collapsed, toggle: () => { collapsed.value = !collapsed.value } }
}
```

**`AppLayout.vue`：**

- `<el-aside :width="collapsed ? '64px' : '220px'">`。
- `<el-menu :collapse="collapsed" ...>`——Element Plus 原生图标折叠：折叠后只剩图标、hover 出 tooltip、`router` 导航与 `active` 高亮均保留。
- 品牌区随状态切换：展开「Smart SOP」+ 折叠按钮（`‹`）；折叠紧凑标记「S」+ 展开按钮（`›`）。按钮调 `toggle()`。

### D. Word 导入进入自动折叠（专注模式）

**决策纯函数 `utils/editorFocus.ts`（新）：**

```ts
/** 进入编辑页是否应自动折叠侧边栏：仅当来自 Word 导入且侧边栏当前展开。 */
export function shouldAutoCollapse(fromQuery: unknown, currentCollapsed: boolean): boolean {
  return fromQuery === 'import' && currentCollapsed === false
}
```

**导入导航打标（`ProcedureLibraryView.vue`）：**

`onImported` 改为 `router.push({ path: '/procedures/${id}/edit', query: { from: 'import' } })`。其余进入编辑页的路径（打开已有草稿、升级 / 复制跳转）不带此标记，不受影响。

**`ProcedureEditorView.vue` 接线（用 `useSidebar`）：**

- 本地态：`autoCollapsed = ref(false)`、`priorCollapsed = ref<boolean | null>(null)`。
- `onMounted`（在现有 `store.load` 之后）：
  1. 若 `shouldAutoCollapse(route.query.from, sidebar.collapsed.value)`：记 `priorCollapsed.value = sidebar.collapsed.value`（= false）；`sidebar.collapsed.value = true`；`autoCollapsed.value = true`。
  2. `router.replace({ query: {} })` 抹掉 `from`，防止刷新重触发。
  3. **在以上之后**建立 `watch(sidebar.collapsed, () => { autoCollapsed.value = false })`——用户编辑中手动切换即「接管」，离开不再恢复（手动选择作为全局偏好持久化保留）。
- `onUnmounted`（真正离开才触发，避开未保存守卫取消导航的情形）：若 `autoCollapsed.value` 仍为 true → `sidebar.collapsed.value = false`（恢复进来前状态）。

> 选 `onUnmounted` 而非 `onBeforeRouteLeave` 恢复：未保存守卫可能取消离开，此时不应提前恢复；卸载只在确实离开时发生。

## 数据流

1. 程序库点「Word 导入」→ 导入成功 → `onImported` → `push({query:{from:'import'}})` → 进编辑页。
2. 编辑页 `mount`：`shouldAutoCollapse` 为真 → 折叠侧边栏、`autoCollapsed=true`、抹掉 query。
3. 编辑中：手动点侧边栏折叠 / 展开（`toggle`）→ watch 触发 → `autoCollapsed=false`。
4. 离开编辑页（`unmount`）：`autoCollapsed` 仍真 → 恢复侧边栏展开；否则保持当前（含用户手动设的）状态。
5. 预览 / 详情：点 splitter 折叠按钮 → `state.collapsed=true` 落盘 → 该列变 32px rail、树填满；点 rail → `expand` → 恢复记住的宽度；拖 splitter → 宽度落盘；双击 splitter → 宽度回默认。

## 边界与错误处理

- **预览 + 详情都折叠**：树 `flex:1` 唯一增长，填满（减去两条 32px rail）。
- **树最小宽**：`min-width` 防被两侧挤压到不可用。
- **持久化脏值**：`sanitizePanel` 回退 `{collapsed:false, width:defaultWidth}`；`useStorage('…sidebar…', false)` 非布尔由默认兜底。
- **拖拽方向**：`side` 决定 delta 符号（见上）；pointer capture + `useEventListener` 卸载自动清理。
- **刷新防重触发**：进入即 `router.replace` 抹掉 `from=import`。
- **手动优先**：watch 在自动折叠动作之后建立，自身的程序化折叠不会误触发「接管」。
- **编辑页→编辑页跳转**（升级 / 复制）：旧实例 `unmount` 先恢复，新实例无 `from=import` 不再折叠——符合「非导入不自动折叠」。
- **图标轨**：`el-menu :collapse` 下导航、active 高亮、hover tooltip 由 Element Plus 保证。

## 测试

Gate（在 `frontend/`）：`npm run lint && npm run typecheck && npm run test && npm run build`，`--max-warnings 0`。

**新增：**

- `tests/unit/utils/collapsiblePanel.spec.ts`：`clampWidth` / `resizePanel` / `sanitizePanel`（带 config 的夹紧、collapsed 透传、脏值回退）、`dragDelta`（left/right 符号）、`RAIL_PX`。
- `tests/unit/utils/editorFocus.spec.ts`：`shouldAutoCollapse`（`from==='import'` 且展开→true；已折叠→false；非 import→false；undefined→false）。
- `tests/unit/useSidebar.spec.ts`：`toggle` 翻转 `collapsed`、落盘 localStorage、模块级单例多次调用共享同一 ref。
- `tests/unit/CollapsiblePanel.spec.ts`：折叠态渲染 `ImportSideRail`；点 rail emit/切回展开；展开态渲染 slot；`side` 决定箭头 / splitter 侧。

> 不写 `AppLayout.spec.ts`：仓库无 router 依赖的测试，AppLayout 依赖 `useRoute` / `RouterView` / `el-menu router`，全量挂载脆弱。其折叠核心逻辑由 `useSidebar.spec` 覆盖，视图接线靠 typecheck + build + 手动冒烟（与本仓库既有惯例一致）。

**回归保证：**

- `tests/unit/utils/editorPreview.spec.ts`（**不改**——薄包装等价的关键回归）。
- `tests/unit/EditorPreviewPane.spec.ts`（**仅改选择器** `.preview-col`→`.panel-col`，保留全部行为断言）。
- `tests/unit/ImportSideRail.spec.ts`（**不改**）。

**接线类（无独立视图 spec，靠 typecheck + build + 手动冒烟）：**

- `ProcedureLibraryView` 的 `from:'import'`、`ProcedureEditorView` 的自动折叠 / 恢复接线（决策已抽 `editorFocus` 单测）。

## 文件清单

**新建：**

- `frontend/src/utils/collapsiblePanel.ts`
- `frontend/src/utils/editorFocus.ts`
- `frontend/src/composables/useCollapsiblePanel.ts`
- `frontend/src/composables/useSidebar.ts`
- `frontend/src/components/shared/CollapsiblePanel.vue`
- `frontend/tests/unit/utils/collapsiblePanel.spec.ts`
- `frontend/tests/unit/utils/editorFocus.spec.ts`
- `frontend/tests/unit/useSidebar.spec.ts`
- `frontend/tests/unit/CollapsiblePanel.spec.ts`

**修改：**

- `frontend/src/utils/editorPreview.ts`（改为通用模块的薄包装）
- `frontend/src/components/editor/EditorPreviewPane.vue`（重构到 `CollapsiblePanel side="left"`）
- `frontend/src/layouts/AppLayout.vue`（图标轨折叠 + 品牌区切换）
- `frontend/src/views/procedures/ProcedureEditorView.vue`（三栏布局：树 `flex:1`、详情包 `CollapsiblePanel`；自动折叠 / 恢复接线）
- `frontend/src/views/procedures/ProcedureLibraryView.vue`（`onImported` 带 `from:'import'`）
- `frontend/tests/unit/EditorPreviewPane.spec.ts`（仅改列选择器 `.preview-col`→`.panel-col`）

**不改（回归兜底）：** `WordPreviewPanel.vue`、`ImportSideRail.vue`、各详情面板（`ChapterDetailPanel` / `ContentDetailPanel` / `StepDetailPanel`）、`editorPreview.spec.ts`、`ImportSideRail.spec.ts`。
