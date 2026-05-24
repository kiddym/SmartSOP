# Word 导入弹窗三栏可拖拽调整列宽 — 设计文档

- 日期：2026-05-24
- 状态：已通过 brainstorming 设计评审，待写实施计划
- 关联：承接「三栏比例重平衡」改动（左 38% / 中 28% / 右 34%）。本设计把这套**静态**比例升级为**用户可拖拽**的动态列宽，并跨会话记住。

## 1. 目标与背景

`ImportDialog.vue` 的三栏（Word 原文预览 / 章节大纲 / 内容预览）当前是硬编码 `width: %`，用户无法按当前文档/任务调整各栏权重——有的文档表头复杂需要更宽的原文预览，有的大纲很深需要更宽的中栏。

本设计在「左|中」「中|右」之间插入两根可拖拽分隔条，列宽改由响应式百分比状态驱动，并用 `@vueuse/core` 的 `useStorage` 持久化到 localStorage，下次打开导入弹窗保持上次布局。

**这是纯前端改动**，集中在 `ImportDialog.vue` 单文件，不引入新依赖（`@vueuse/core` 已在 `package.json`）。子组件（`WordPreviewPanel` / `ImportTreePanel` / `ImportDetailPanel` / `ImportTreeRow`）均不改动。

## 2. 范围

### 做（In scope）

1. `ImportDialog.vue`：三栏宽度由静态 CSS 改为内联 style 绑定的响应式百分比状态。
2. 在「左|中」「中|右」之间各加一根分隔条（splitter handle），支持鼠标/指针拖拽实时调整列宽。
3. 用 `useStorage` 持久化 `{ left, mid }` 两个百分比到 localStorage，默认 `{ left: 38, mid: 28 }`（右列 = 100 − left − mid）。
4. 最小宽度约束 18%/列，拖拽时 clamp。
5. 双击任一分隔条恢复默认 38/28/34 并清回持久化默认。
6. 单测：宽度计算 / clamp / 重置 的纯函数逻辑（`vitest`）。
7. 跑通前端门禁：lint / typecheck / build / vitest。

### 不做（Out of scope，YAGNI）

- 垂直方向（高度）调整。
- 列的折叠/隐藏、列顺序拖拽。
- 把分栏抽成通用 `ResizableCols` 组件库（当前仅此一处使用；若日后第二处出现再抽）。
- 触屏手势优化（`pointer` 事件天然兼容触屏即可，不额外做）。
- 任何后端改动。

## 3. 状态模型

```ts
// 持久化：仅存左、中两栏百分比；右列为派生值
const DEFAULTS = { left: 38, mid: 28 } as const
const MIN_PCT = 18

const cols = useStorage('smartsop.import.cols', { ...DEFAULTS })
// 派生
const rightPct = computed(() => 100 - cols.value.left - cols.value.mid)
```

- 为何存百分比而非像素：弹窗为 `96vw`，窗口缩放时百分比保持三栏相对比例稳定；像素则需监听容器宽度二次换算。
- 为何只存 left/mid：右列恒为派生值，避免三值冗余导致和不为 100 的状态漂移。
- `useStorage` 自带读默认值 + 写入节流；首次无存储时回落 `DEFAULTS`。

## 4. 模板与样式

```
.cols (flex 容器)
 ├─ .col.left   :style="{ width: cols.left + '%' }"   → WordPreviewPanel
 ├─ .splitter   (handle 1：左|中)
 ├─ .col.mid    :style="{ width: cols.mid + '%' }"    → ImportTreePanel
 ├─ .splitter   (handle 2：中|右)
 └─ .col.right  :style="{ width: rightPct + '%' }"    → ImportDetailPanel
```

- 移除原 `.col.left/mid/right { width: % }` 静态规则，宽度全部走内联 style。
- `.splitter`：宽约 6px、`flex: none`、`cursor: col-resize`、hover 时显露主题色（`--el-color-primary` 暖陶土色）细线；拖拽中 body 加 `user-select: none` 防选中。
- 三栏 `width` 之和 + 两根 splitter 宽度 ≈ 100%；splitter 占用的 ~12px 由 flex 容器吸收，对百分比影响可忽略（容器宽 ~1900px 时 < 0.7%）。

## 5. 拖拽机制

每根 splitter 绑定 `@pointerdown`，按 handle 标识（`'lm'` 左中 / `'mr'` 中右）分派：

1. **pointerdown**：记录 `startX`、起始 `cols` 快照、容器像素宽 `containerW`（`el.getBoundingClientRect().width`）；`setPointerCapture`；置拖拽态。
2. **pointermove**（经 `useEventListener(window, 'pointermove')`，仅拖拽态生效）：
   - `deltaPct = (e.clientX − startX) / containerW * 100`
   - handle `'lm'`：`left = clamp(start.left + deltaPct)`，`mid = clamp(start.mid − deltaPct)`；右列不变。
   - handle `'mr'`：`mid = clamp(start.mid + deltaPct)`，右列 = `100 − left − mid` 随之变化；左列不变。
   - `clamp` 保证被拖的两栏都 ≥ `MIN_PCT`，且对侧不被挤破 `MIN_PCT`（见 §6）。
3. **pointerup**：清拖拽态、释放 capture。`useStorage` 已实时把 `cols` 写入 localStorage，无需额外保存动作。

clamp/换算逻辑抽为纯函数（如 `utils/importCols.ts` 的 `resizeLeftMid(start, deltaPct)` / `resizeMidRight(...)`），便于单测，组件只管事件与状态。

## 6. 约束与边界

- **最小宽度**：任一参与列不得 < 18%。`'lm'` 拖拽时 `left ∈ [18, start.left+start.mid−18]`，`mid` 取补；`'mr'` 拖拽时 `mid ∈ [18, start.mid+rightStart−18]`，右列取补。
- **三值守恒**：任何操作后 `left + mid + right == 100`（右为派生，天然成立）；clamp 后用补值回填另一栏，不出现总和漂移。
- **持久化脏值防御**：读 localStorage 后校验 `left/mid ≥ 18 且 left+mid ≤ 82`，不满足则回落 `DEFAULTS`（防用户手改 storage 或旧版本遗留值导致布局崩坏）。
- **双击重置**：splitter `@dblclick` → `cols.value = { ...DEFAULTS }`（同步写回 storage）。

## 7. 测试

`tests/unit/utils/importCols.spec.ts`（纯函数，无需挂载组件）：

| 用例 | 断言 |
|------|------|
| 左中拖动正向/负向 | left/mid 按 delta 变化，right 不变，和为 100 |
| 中右拖动 | mid/right 变化，left 不变，和为 100 |
| 拖到下限 | 被拖列 clamp 到 18，对侧不超界 |
| 反向拖到对侧下限 | 对侧 clamp 到 18 |
| 脏值校验 | 越界/和非法的输入回落 DEFAULTS |

门禁：`npm run lint`、`npm run typecheck`（或 `vue-tsc`）、`npm run build`、`npm run test`（vitest）全绿。

## 8. 受影响文件

| 文件 | 改动 |
|------|------|
| `frontend/src/components/import-v2/ImportDialog.vue` | 列宽改响应式 + 两根 splitter + 拖拽/持久化/重置逻辑 + 样式 |
| `frontend/src/utils/importCols.ts` | 新建：clamp + 两个 resize 纯函数 + 脏值校验 + 常量 |
| `frontend/tests/unit/utils/importCols.spec.ts` | 新建：纯函数单测 |

子组件不改动。无后端改动、无数据库迁移。
