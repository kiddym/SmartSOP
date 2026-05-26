# UI 设计系统（Design System）

> Smart SOP 前端视觉规范。决策权威见 [feature-clarifications.md §49（Q313–Q319）](feature-clarifications.md)；本文件是详细令牌与组件参考。配色变更需同步回填 [frontend-coding-standards.md §8](frontend-coding-standards.md)。

## 1. 设计定位

**暖炭黑 · Claude Code 本色**（工业风）。暖炭黑暗壳 + 陶土橙强调 + 暖白文字，「文档区」（编辑器画布 / PDF 预览）保持亮纸底。性格三选：**数据走等宽 / 信息密度适中 / 强调色克制**。

- 工业感来源：等宽数据、线条分隔（不靠阴影）、小圆角、克制强调色。
- 双层底色：**暗壳**承载应用框架（导航/侧栏/列表/工具栏/弹层）；**亮纸**承载将来要打印成 PDF 的文档内容。

## 2. 设计令牌

### 2.1 色板

**暗壳**

| 令牌 | Hex | 用途 |
|---|---|---|
| `bg-base` | `#1A1714` | 最底层应用背景、主内容区 |
| `bg-surface` | `#211E1B` | 侧栏、顶栏、面板（暖炭黑） |
| `bg-elevated` | `#2A2622` | 卡片、下拉、弹层 |
| `bg-hover` | `#322D28` | 行 / 按钮 hover |
| `border-subtle` | `#3A352F` | 主分隔线（低对比） |
| `border-strong` | `#4A443C` | 需要存在感的分隔 |
| `text-primary` | `#ECE6DD` | 正文（暖白） |
| `text-secondary` | `#B3AA9E` | 次要 / 标签 |
| `text-tertiary` | `#7A7269` | 禁用 / 占位 |

**陶土橙强调（克制：仅主按钮 / 激活 / 焦点 / 选中）**

| 令牌 | Hex | 用途 |
|---|---|---|
| `accent` | `#D97757` | 主按钮、激活条、链接 |
| `accent-hover` | `#E08A6E` | hover |
| `accent-active` | `#C56546` | pressed |
| `accent-bg` | `rgba(217,119,87,.12)` | 选中行底、焦点环底 |

**亮纸（文档区：富文本画布 + PDF 预览，与打印件一致）**

| 令牌 | Hex | 用途 |
|---|---|---|
| `paper-bg` | `#FAF8F4` | 编辑 / 预览画布底 |
| `paper-text` | `#2A2521` | 墨黑正文 |
| `paper-border` | `#E5DFD5` | 纸面分隔 |

**状态色（暖盘，修订 Q172 → 见 feature-clarifications Q317）**

| 状态 | Hex | 呈现 |
|---|---|---|
| DRAFT 草稿 | `#A89A86` 暖灰 | ○ 空心圆点 |
| PUBLISHED 已发布 | `#88B07A` 鼠尾草绿 | ● 实心圆点 |
| ARCHIVED 已归档 | `#6B635A` 暗暖灰 | ● 暗点 |
| 废止 DEPRECATED | `#D9685E` 暖红 | 描边小红 tag（跟在状态右侧，警示保留份量） |

> 原则：**陶土橙只表示交互**，绝不当状态色；已发布用鼠尾草绿，让「橙」语义唯一。

### 2.2 字体

| 角色 | 字体栈 | 用在 |
|---|---|---|
| 无衬线（UI / 正文） | `Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif` | 标题、正文、菜单、按钮、状态词 |
| 等宽（数据） | `"JetBrains Mono", "Sarasa Mono SC", ui-monospace, monospace` | 编号 `QC-0001`、版本 `v3`、测量值 `12.5 mm`、状态枚举、日期 |

字号：页标题 `20/600` · 区块标题 `16/600` · 正文 `14/400`（基准）· 元信息 `12/400` · 等宽数据 `13`。行高：正文 1.6 / UI 1.5。

### 2.3 间距与密度（适中）

- 基准 4px 栅格；间距用 `8 / 12 / 16`。
- 列表行 40px、表格行 36–40px、面板 padding 16px。

### 2.4 圆角 / 边框 / 阴影 / 焦点 / 动效

- 圆角：按钮 / 输入 / chip `4px` · 卡片 / 下拉 `6px` · 模态 `8px`（小圆角，偏工业）。
- 分隔靠线不靠影：1px `border-subtle` 是主要分隔手段。
- 阴影：仅下拉 / 模态 `0 4px 16px rgba(0,0,0,.4)`；纸面孤岛（§3.8）专用 `--shadow-paper` = `0 2px 12px rgba(0,0,0,.4)`（桌上一张文件的投影，与层级阴影不可混用）。
- 焦点环：2px 陶土橙 + `accent-bg` 底，键盘可达。
- 动效：120–160ms ease-out，无弹跳。

## 3. 组件规范

### 3.1 应用框架（App Shell）

```
┌───────────────────────────────────────────────────────┐
│ ≡  Smart SOP      [⌕ 搜索全库…]            待阅读③  ⚙  │  顶栏 48px · bg-surface · 底边 border-subtle
├────────────┬──────────────────────────────────────────┤
│ 文件夹配置   │  程序库                          [＋ 新建] │
│ ▸ QC 质量   │  ┌────────────────────────────────────┐  │
│ ▸ QA 保证   │  │  主内容区(列表 / 编辑器 / 详情)        │  │  bg-base
│ ──────────│  │                                    │  │
│ 废止        │  └────────────────────────────────────┘  │
└────────────┴──────────────────────────────────────────┘
  侧栏 240px · bg-surface          主区 bg-base
```

三段式：顶栏（48px）+ 左侧栏（240px，文件夹树）+ 主区。各段以 1px `border-subtle` 分隔，不用阴影。

> **IA 归位（§50）**：根路由 `/` = **程序库列表**、不设独立工作台（Q320）；顶栏 `⚙▾` = **设置 + 审计日志**下拉（管理类）、`待阅读③` 点击即筛列表（Q304）；侧栏底部「系统区」= **废止**（内容容器，Q321；模板库已废 §56/Q340）。

> **术语演变 (2026-05-26)**：「文件夹配置」（原称「标准文件库」）= ⚙ 配置组下的文件夹 CRUD 管理页。本节早期版本 ASCII（`▸ QC 质量 ▸ QA 保证` 树状结构）描述的"侧栏文件夹树导航"现已实现，但**位置在 ProcedureLibraryView 内部双栏的左侧 FolderTreePane**（非全局 AppSidebar）。详见 [`docs/superpowers/specs/2026-05-26-library-ia-archive-folder-design.md`]。

### 3.2 侧栏 / 文件夹树（文件夹配置）

| 态 | 样式 |
|---|---|
| 默认 | 32px 行高 · text-secondary · 线性文件夹图标 · 右侧 mono 计数走 text-tertiary |
| hover | `bg-hover` |
| 选中 | 左侧 3px 陶土橙竖条 + `accent-bg` 底 + text-primary |

「废止」固定在树底「系统区」、独立分隔（§50 Q321「内容容器归侧栏」；§41 Q269）。模板库已废除（§56/Q340），系统区仅「废止」。

### 3.3 按钮

| 类型 | 样式 | 用在 |
|---|---|---|
| 主 Primary | 实心陶土橙 + 奶白字 `#FAF8F4` · hover `accent-hover` | 唯一强动作（新建 / 保存 / 发布） |
| 次 Secondary | 透明底 + 1px `border-subtle` + text-primary · hover `bg-hover`+`border-strong` | 取消 / 次要操作 |
| 文本 / 图标 | 无边框 · text-secondary · hover text-primary+`bg-hover` | ⋮ 菜单、工具栏 |
| 危险 | 描边 / 文字走废止红；仅删除确认弹窗内填充实心红 | 删除 / 废弃 |

高 32px · 圆角 4px · 标签用无衬线（非数据，不走等宽）。

### 3.4 状态指示（修订 Q172 后）

```
○ 草稿        #A89A86 空心暖灰点
● 已发布      #88B07A 鼠尾草绿实心点
● 已归档      #6B635A 暗点
[废止]        #D9685E 描边红 tag（跟在状态右侧）
```

状态词用无衬线；旁边的 `v3`、`3版`、日期走等宽。

### 3.5 程序库列表行（40px）

```
│ QC-0001    装配作业规程                  ● 已发布   v3·3版   2026-05-18   ⋮ │
   └─等宽─┘   └──无衬线名称──┘             └状态┘     └等宽┘   └等宽日期┘   └hover出现┘
```

- hover：整行 `bg-hover`；选中：左 2px 陶土橙条 + `accent-bg`。
- 跨库搜索时（§42）在名称下补一行 mono 路径，text-tertiary。

### 3.6 输入 / 搜索框

底 `bg-base`（比面板更暗、内陷感）· 1px `border-subtle` · 占位 text-tertiary · **聚焦** → 边框转陶土橙 + 2px `accent-bg` 焦点环 · 高 32px · 圆角 4px。搜索框带前置 ⌕ + 可清除 ✕。

### 3.7 卡片 / 面板 / 表格

- 卡片 / 面板：`bg-elevated` + 1px `border-subtle` + 圆角 6px + padding 16px。
- 表格（步骤表 / 审计 diff）：表头 `bg-surface` · 12px · text-secondary · sticky；**只用行线不用斑马纹**（工业 = 线条）；数据单元格走等宽、文字单元格无衬线；hover `bg-hover`。审计 diff 表：旧值删除线 + text-tertiary、新值 text-primary。

### 3.8 亮纸文档区

编辑器画布（WangEditor）与 PDF 预览是一座「亮纸孤岛」：`paper-bg #FAF8F4` + 墨黑字，嵌在暗壳里（四周 bg-base 留边 + 1px 框），像桌上的一张文件。**工具栏仍是暗壳**（bg-surface），只有画布是纸——既保持框架统一，又让「正在编辑的就是将来打印的那张纸」。技术上是把 CSS 变量切回浅色的 `.paper` 容器（见 §4.4）。

### 3.9 模态 / 下拉 / Toast / 空状态

- 模态：`bg-elevated` · 圆角 8px · 1px `border-strong` · 柔影 · 遮罩 `rgba(0,0,0,.6)`；底部按钮右对齐（次 + 主）。
- ⋮ 下拉：`bg-elevated` · 圆角 6px · 项 32px · hover `bg-hover` · 危险项红字。
- Toast：右上 · `bg-elevated` · 按类型左侧色条（橙 / 绿 / 红）。
- 空状态（§41 Q275）：居中线性图标 + text-secondary 文案 + 主按钮 CTA。

## 4. Element Plus 改造方案

核心：**令牌单一来源（CSS 变量）→ Tailwind 与 Element Plus 都来读它**；EP 走暗色模式 + 变量重映射；亮纸区是局部把变量切回浅色的孤岛。全部走 `element-overrides.css` 集中通道（合规 [frontend-coding-standards §8.1](frontend-coding-standards.md)）。

### 4.1 单一来源 `tokens.css`

```css
:root {
  --bg-base:#1A1714; --bg-surface:#211E1B; --bg-elevated:#2A2622; --bg-hover:#322D28;
  --border-subtle:#3A352F; --border-strong:#4A443C;
  --text-primary:#ECE6DD; --text-secondary:#B3AA9E; --text-tertiary:#7A7269;
  --accent:#D97757; --accent-hover:#E08A6E; --accent-active:#C56546;
  --accent-rgb:217 119 87;              /* alpha 用：rgb(var(--accent-rgb)/.12) */
  --st-draft:#A89A86; --st-published:#88B07A; --st-archived:#6B635A; --st-deprecated:#D9685E;
}
.paper { --paper-bg:#FAF8F4; --paper-text:#2A2521; --paper-border:#E5DFD5; }
```

### 4.2 Tailwind 读同一份（`tailwind.config.js`）

```js
colors: {
  base:'var(--bg-base)', surface:'var(--bg-surface)', elevated:'var(--bg-elevated)',
  accent:{ DEFAULT:'var(--accent)', hover:'var(--accent-hover)', active:'var(--accent-active)' },
  ink:{ DEFAULT:'var(--text-primary)', soft:'var(--text-secondary)', faint:'var(--text-tertiary)' },
  st:{ draft:'var(--st-draft)', published:'var(--st-published)', archived:'var(--st-archived)', deprecated:'var(--st-deprecated)' },
}
```

> 保留 `preflight:false`（已是），避免 Tailwind reset 掀翻 EP 基样式；删除原 `primary:#409eff`。

### 4.3 EP 暗模式 + 变量重映射（`element-overrides.css`）

启用 EP 暗模式（`main.ts` 引 `theme-chalk/dark/css-vars.css`，`index.html` 给 `<html class="dark">`），再把 EP 变量指向令牌：

```css
html.dark{
  --el-bg-color:var(--bg-base); --el-bg-color-page:var(--bg-base);
  --el-bg-color-overlay:var(--bg-elevated);
  --el-fill-color:var(--bg-hover); --el-fill-color-light:var(--bg-elevated);
  --el-text-color-primary:var(--text-primary); --el-text-color-regular:var(--text-primary);
  --el-text-color-secondary:var(--text-secondary); --el-text-color-placeholder:var(--text-tertiary);
  --el-border-color:var(--border-subtle); --el-border-color-light:var(--border-subtle);
  --el-border-color-darker:var(--border-strong);
  --el-border-radius-base:4px; --el-border-radius-small:4px;

  /* primary 阶梯 → 陶土橙（暗模式向底色混，示意值，落地用 mix() 精算） */
  --el-color-primary:var(--accent);
  --el-color-primary-light-3:#A85E45; --el-color-primary-light-5:#7A4634;
  --el-color-primary-light-7:#4D2E22; --el-color-primary-light-8:#3A241B;
  --el-color-primary-light-9:#261913; --el-color-primary-dark-2:var(--accent-active);

  /* 语义色 → 状态盘（el-alert/el-message 等天然上盘） */
  --el-color-success:var(--st-published); --el-color-info:var(--st-draft);
  --el-color-danger:var(--st-deprecated); --el-color-warning:#D9A14E;
}
```

### 4.4 亮纸孤岛（`.paper`）

```css
.paper{
  background:var(--paper-bg); color:var(--paper-text);
  --el-bg-color:var(--paper-bg); --el-text-color-primary:var(--paper-text);
  --el-border-color:var(--paper-border);
}
```

> EP 的下拉 / 对话框 / tooltip 都 teleport 到 `body`（在 `.paper` 之外），弹层自动保持暗壳，只有画布内联内容变纸。WangEditor 是第三方，另起 `wangeditor-overrides.css`：工具栏走暗壳、`.w-e-text-container` 走纸。

### 4.5 自建 vs 用 EP

| 用 EP（变量重映射即可） | 自建（Tailwind + scoped） |
|---|---|
| 表单控件、日期选择、对话框、下拉、消息 / 通知、分页、tabs、上传、el-table | 应用框架 / 侧栏项、状态点 + 标签、程序库列表行、卡片 |

> 列表行视觉（等宽编号 + 左激活条 + 圆点状态）很特化，自建比硬掰 el-table 划算；表单密集处用 EP 省事。

### 4.6 文件组织与风险

```
src/assets/styles/
├── tokens.css              ← 单一来源
├── element-overrides.css   ← --el-* 映射（集中，合规 §8.1）
├── wangeditor-overrides.css
└── main.css                ← @tailwind + import 以上（EP 基 → EP 暗 → 本覆盖，顺序在后）
```

**已知风险**：① EP primary 阶梯暗模式需精算 9 档，否则个别 hover 态发闷——落地用 SCSS `mix()` 或定稿硬值；② 个别 EP 组件硬编码灰 / 阴影，需留一轮「打磨 pass」；③ WangEditor 主题是独立工作量。均可控，不动架构。

## 5. 与既有文档的关系

- **修订 Q172**（§22.8 status chip 配色）：原 EP 默认盘（已发布 = 主蓝 `#409EFF`）→ 本暖盘（已发布 = 鼠尾草绿 `#88B07A`），呈现由填充 tag → 圆点 + 等宽标签。见 feature-clarifications Q317。
- 关联：[§41 列表页](feature-clarifications.md)（列表行 / 空状态 / 侧栏树）、[§42 搜索](feature-clarifications.md)（命中高亮 / 路径行）、[§43 审计](feature-clarifications.md)（diff 表）、[pdf-rendering](pdf-rendering.md)（亮纸 = PDF 版式一致）。
- 配色变更必须同步回填 [frontend-coding-standards §8.2](frontend-coding-standards.md)。
