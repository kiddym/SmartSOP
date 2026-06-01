# 审查树 content 行表格/图片类型标识 — 设计

- 日期：2026-05-31
- 范围：纯前端（Vue/Element Plus），零后端、零数据库迁移
- 状态：设计已与用户确认，待写实现计划

## 1. 背景与动机

Word 解析后，表格和图片在节点树中是**独立的 content 行**（不与文字整合）。当前一个 content 行只显示 `node.body` 首个块级元素的纯文本预览（`utils/nodeTree.ts` 的 `nodeTitle`），body 首块为空时退化为占位「未命名章节」。结果：**纯图片行、无前导文字的表格行，用户不展开渲染就无法分辨这一行解析出来的是什么**。

类型信息在解析时本就已知（IR `Block.kind` / `Block.images`），但导入落库后丢失——`Node` 模型只有 `heading_level`（null=正文）和 `kind`（`node`/`step`，与表单相关，非内容类型），不携带「表格/图片/文字」。

注：导入后没有独立的「导入审查向导树」；triage 已并入编辑器（`api/parse.ts` 注释「triage 移到编辑器」），审查发生在编辑器的节点树上、对着已落库的 `Node`。因此本方案在编辑器节点树组件上实现，零持久化即可在「审查发生处」生效。

## 2. 目标 / 非目标

**目标**
- 在节点树的 content 行上，对「表格」「图片」两类显示「图标 + 文字标签」，让用户一眼识别该行解析出的内容类型。

**非目标（YAGNI）**
- 不给纯文字 content 行打标（无标签即默认文字形态）。
- 不给章节标题行打标。
- 不改后端、不改 `Node` 模型、不做数据库迁移。
- 不区分「图文混排」（含图片的段落统一归为图片）。
- 不改变现有标题预览 / 编号 / review 黄标 / 删除按钮等任何既有行为。

## 3. 设计

### 3.1 分类纯函数（`frontend/src/utils/nodeTree.ts`）

与既有 `nodeTitle` 并列新增：

```ts
export type ContentKind = 'table' | 'image'

/** content 行的内容类型标识；无需打标（纯文字、或章节标题行）返回 null。
 *  仅对正文行（heading_level === null）判定。表格优先于图片
 *  （表格单元格内可能内嵌图，整体语义仍是表格）。
 *  判定依据 = body HTML 是否含 <table> / <img>，与后端序列化输出对应，稳定无漂移。 */
export function contentKind(node: Node): ContentKind | null {
  if (node.heading_level !== null) return null   // 章节标题行不打标
  const body = node.body ?? ''
  if (/<table[\s>]/i.test(body)) return 'table'
  if (/<img[\s>]/i.test(body)) return 'image'
  return null                                    // 纯文字 → 不打标（方案 b）
}
```

### 3.2 预计算进 `TreeRow`

保持 `NodeTreeRow` 为纯展示组件、判定逻辑可独立单测（沿用 `nodeTree.ts` 既有「纯函数 + 测试」风格）。在 `visibleRows()` 里与 `title` 一同算好：

```ts
export interface TreeRow {
  node: Node
  title: string
  contentKind: ContentKind | null   // 新增
  hasChildren: boolean
  expanded: boolean
}
```

`visibleRows()` 内 `rows.push({...})` 处补 `contentKind: contentKind(node)`。

### 3.3 渲染（`frontend/src/components/editor/NodeTreeRow.vue`）

在 `<span class="ntr-code">`（编号）与 `<span class="ntr-title">`（标题预览）之间插入：

```vue
<span v-if="row.contentKind" class="ntr-type" :class="`ntr-type--${row.contentKind}`">
  <el-icon><component :is="TYPE_ICON[row.contentKind]" /></el-icon>
  {{ TYPE_LABEL[row.contentKind] }}
</span>
```

- 图标用项目已在用的 Element Plus 图标（`@element-plus/icons-vue`），不引入 emoji：
  - 表格 → `Grid`，图片 → `Picture`
- 文字标签：`表格` / `图片`
- script 内定义常量映射：
  ```ts
  import { Grid, Picture } from '@element-plus/icons-vue'
  const TYPE_ICON = { table: Grid, image: Picture } as const
  const TYPE_LABEL = { table: '表格', image: '图片' } as const
  ```

### 3.4 样式

沿用既有 chip 风格（参考 `.ntr-review`），中性灰底，与黄色「待确认」区分；`flex:none` 不挤占标题空间：

```css
.ntr-type {
  flex: none; display: inline-flex; align-items: center; gap: 2px;
  font-size: 11px; line-height: 1; padding: 1px 4px; border-radius: 3px;
  color: #5c6b7a; background: #eef1f4; border: 1px solid #dde3e9;
}
.ntr-type .el-icon { font-size: 12px; }
```

## 4. 数据流

`Node`（已落库，含 `body` HTML）→ `visibleRows()` 调 `contentKind(node)` → `TreeRow.contentKind` → `NodeTreeRow` 按其渲染图标+标签。全程只读 `node.body`，不写任何状态、不发任何请求。

## 5. 错误处理 / 边界

- `node.body` 为 `null`/空串 → `contentKind` 返回 `null`（与现有 `nodeTitle` 的空 body 处理一致），不打标。
- 章节标题行（`heading_level !== null`）→ 始终 `null`。
- 同时含表格和图片的极少数 content 行 → 归「表格」（表格优先，已声明）。
- 正则 `/<table[\s>]/i`、`/<img[\s>]/i` 容忍属性与自闭合（`<img .../>`、`<table border=...>`）。

## 6. 测试

**单测（`frontend/tests/.../nodeTree.spec.ts`，沿用既有 pure-fn 测试套）**
- `contentKind`：表格 HTML → `'table'`；图片 HTML（`<img>`）→ `'image'`；表格+图片同存 → `'table'`；纯文字 → `null`；空 body → `null`；`heading_level !== null` 的章节行 → `null`。
- `visibleRows`：返回的 `TreeRow` 携带正确 `contentKind`。

**组件测（`NodeTreeRow` 既有 spec）**
- 表格行渲染 `Grid` 图标 + 「表格」；图片行渲染 `Picture` 图标 + 「图片」。
- 纯文字 content 行、章节行：不渲染 `.ntr-type`。
- 不破坏既有元素（caret/checkbox/chip/code/title/review/del）渲染。

## 7. 影响面

改动文件 2 个：
- `frontend/src/utils/nodeTree.ts`（加 `ContentKind` 类型、`contentKind` 函数、`TreeRow.contentKind` 字段、`visibleRows` 填值）
- `frontend/src/components/editor/NodeTreeRow.vue`（图标 import、常量映射、模板 1 处插入、样式 1 块）

加测试文件改动若干。后端、数据库、API、`Node` 模型：**零改动**。
