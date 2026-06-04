# 前端质感移植（字体+表格+动效，方案A）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变赤陶工业风配色的前提下，把当前 SmartSOP 前端的字体、表格、动效三层质感逼近源项目 `HP_trae_backup-cmms`。

**Architecture:** 全部改动集中在「全局样式层 + 少量共享组件」，90 个业务页面零改动自动继承。新增自托管 webfont、一份 Element Plus 全局覆盖样式、动效/杂项令牌；保留「线不靠影 / 无斑马纹 / 无弹跳」红线（动效只做位移+淡入，不引入卡片 hover 阴影上浮 / 按钮辉光）。颜色令牌一字不动。

**Tech Stack:** Vue 3 + TypeScript + Element Plus + Tailwind + Vite。字体 Space Grotesk + DM Sans（OFL，自托管 woff2）。

---

## 关于"测试"

这是一次纯视觉换肤，绝大多数改动是 CSS，没有可单测的逻辑。本计划的"验证"采用：
1. `npm run build`（含 `vue-tsc --noEmit`）+ `npm run lint` 全绿——保证不破坏类型/构建；
2. 跑起 dev（见 `running-smartsop-dev` skill）+ chrome-devtools MCP 截图目视核对；
3. `grep` 断言关键 CSS/令牌已落位；
4. 手动核对 `prefers-reduced-motion: reduce` 下新动画被禁用。

不为纯 CSS 编造假单测。所有 `npm` 命令在 `frontend/` 目录下执行。

---

## 现状关键事实（已核对，写任务前必读）

- `main.ts` 样式导入顺序：`element-plus/dist/index.css` → `tokens.css` → `main.css`（后加载者覆盖前者）。
- `tokens.css` 是配色/字体令牌单一来源；**本计划不改任何配色令牌**，只改字体相关 + 新增动效/杂项令牌。
- `main.css` 仅 56 行：已有 `body` 硬编码字体栈、`h1–h3/.app-brand` 用 `--font-display`、`.fade` 路由过渡（0.16s）、`u-fade-in` 入场关键帧、`prefers-reduced-motion` 守卫。
- 路由过渡**已接好**：`AppLayout.vue` 中 `<Transition name="fade" mode="out-in">` 已包住 `<RouterView>`。本计划只**放宽时长**，不重新接线。
- `StatusTag.vue` 已是「圆点 + mono」雏形，无胶囊底；`KpiCard.vue` 用 `el-card shadow="never"`，数值未走 mono。
- 31 个文件用 `el-table` → 表格改造**只能**走全局覆盖。
- 无 `frontend/public/` 目录，需新建。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/public/fonts/*.woff2` | 自托管字体文件 | 新建 |
| `frontend/src/assets/styles/fonts.css` | `@font-face` 声明 | 新建 |
| `frontend/src/assets/styles/element-overrides.css` | EP 全局覆盖（表格/输入/按钮） | 新建 |
| `frontend/src/assets/styles/tokens.css` | 字体令牌改写 + 新增动效/杂项令牌 | 改 |
| `frontend/src/assets/styles/main.css` | body 字体走令牌、标题字距、滚动条、focus 光环、放宽过渡、pulse、reduced-motion 扩容 | 改 |
| `frontend/src/main.ts` | 导入 fonts.css 与 element-overrides.css | 改 |
| `frontend/src/components/StatusTag.vue` | 状态胶囊底色 | 改 |
| `frontend/src/components/analytics/KpiCard.vue` | 数值走 mono | 改 |
| `docs/design-system.md` | §2.2 字体、§2.4 动效时长同步 | 改 |

---

## Task 1: 自托管 Space Grotesk + DM Sans webfont

**Files:**
- Create: `frontend/public/fonts/` (6 个 woff2)
- Create: `frontend/src/assets/styles/fonts.css`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 下载并规范化字体文件（OFL，自托管）**

在 `frontend/` 下执行（用 google-webfonts-helper 下载干净的 latin 子集 woff2，再重命名为稳定文件名）：

```bash
mkdir -p public/fonts && cd public/fonts
# Space Grotesk: 400/500/600
for w in regular 500 600; do
  curl -sfL "https://gwfh.mranftl.com/api/fonts/space-grotesk?download=zip&subsets=latin&variants=${w}&formats=woff2" -o sg-${w}.zip && unzip -oq sg-${w}.zip && rm sg-${w}.zip
done
# DM Sans: 400/500/600/700
for w in regular 500 600 700; do
  curl -sfL "https://gwfh.mranftl.com/api/fonts/dm-sans?download=zip&subsets=latin&variants=${w}&formats=woff2" -o dm-${w}.zip && unzip -oq dm-${w}.zip && rm dm-${w}.zip
done
# 规范化命名（去掉版本号/子集后缀），稳定 @font-face src
rename_one() { mv "$(ls $1* 2>/dev/null | head -1)" "$2" 2>/dev/null; }
rename_one space-grotesk-*-regular space-grotesk-400.woff2
rename_one space-grotesk-*-500     space-grotesk-500.woff2
rename_one space-grotesk-*-600     space-grotesk-600.woff2
rename_one dm-sans-*-regular       dm-sans-400.woff2
rename_one dm-sans-*-500           dm-sans-500.woff2
rename_one dm-sans-*-600           dm-sans-600.woff2
rename_one dm-sans-*-700           dm-sans-700.woff2
ls -la
cd ../..
```

**若 gwfh 不可达（沙箱无网）**：回退到 CDN——跳过本 Step 与 fonts.css 的本地 `src`，改在 `index.html` `<head>` 加
`<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600&display=swap">`，
并在 Task 完成说明里标注「用了 CDN，未自托管」交给用户决定。优先自托管。

- [ ] **Step 2: 验证字体文件就位且非空**

```bash
cd frontend && ls -la public/fonts/*.woff2 && find public/fonts -name '*.woff2' -size +5k | wc -l
```
Expected: 7 个 woff2，每个 > 5k（非空）。

- [ ] **Step 3: 写 `frontend/src/assets/styles/fonts.css`**

```css
/* 自托管 webfont（OFL）。中文字形不在 latin 子集内，由 tokens.css 字体栈回退到系统中文字体。 */
@font-face {
  font-family: 'Space Grotesk';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts/space-grotesk-400.woff2') format('woff2');
}
@font-face {
  font-family: 'Space Grotesk';
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url('/fonts/space-grotesk-500.woff2') format('woff2');
}
@font-face {
  font-family: 'Space Grotesk';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('/fonts/space-grotesk-600.woff2') format('woff2');
}
@font-face {
  font-family: 'DM Sans';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts/dm-sans-400.woff2') format('woff2');
}
@font-face {
  font-family: 'DM Sans';
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url('/fonts/dm-sans-500.woff2') format('woff2');
}
@font-face {
  font-family: 'DM Sans';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('/fonts/dm-sans-600.woff2') format('woff2');
}
@font-face {
  font-family: 'DM Sans';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url('/fonts/dm-sans-700.woff2') format('woff2');
}
```

- [ ] **Step 4: 在 `main.ts` 导入 fonts.css（tokens 之后）**

把：
```ts
import './assets/styles/tokens.css'
import './assets/styles/main.css'
```
改为：
```ts
import './assets/styles/tokens.css'
import './assets/styles/fonts.css'
import './assets/styles/main.css'
```

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功（`vue-tsc --noEmit` 无报错），dist 产物含 fonts。

- [ ] **Step 6: 提交**

```bash
git add frontend/public/fonts frontend/src/assets/styles/fonts.css frontend/src/main.ts
git commit -m "feat(ui): 自托管 Space Grotesk + DM Sans webfont"
```

---

## Task 2: 字体令牌改写 + 应用

**Files:**
- Modify: `frontend/src/assets/styles/tokens.css`
- Modify: `frontend/src/assets/styles/main.css`

- [ ] **Step 1: 改 `tokens.css` 字体令牌**

把：
```css
  /* 字体 */
  --font-display: 'Fraunces', Georgia, 'Times New Roman', serif;
```
改为（保留下方原有 `--font-mono` 注释与定义不动）：
```css
  /* 字体（西文 webfont 见 fonts.css；中文自动回退系统字体）。
     权威定义见 docs/design-system.md §2.2。 */
  --font-display: 'Space Grotesk', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  --font-body: 'DM Sans', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
```

- [ ] **Step 2: 改 `main.css`——body 走 `--font-body`、标题加字距**

把：
```css
html,
body,
#app {
  height: 100%;
  margin: 0;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  color: var(--text-primary);
  background: var(--bg-surface);
}
```
改为：
```css
html,
body,
#app {
  height: 100%;
  margin: 0;
  font-family: var(--font-body);
  color: var(--text-primary);
  background: var(--bg-surface);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
```
并把：
```css
h1,
h2,
h3,
.app-brand {
  font-family: var(--font-display);
}
```
改为：
```css
h1,
h2,
h3,
.app-brand {
  font-family: var(--font-display);
  letter-spacing: -0.02em;
}
```

- [ ] **Step 2.5: 同步 Element Plus 基础字体（EP 默认用自己的 font-family）**

在 `main.css` 末尾追加（让 EP 组件也吃到 body 字体，中文不受影响）：
```css
/* Element Plus 默认字体跟随设计字体栈 */
:root {
  --el-font-family: var(--font-body);
}
```

- [ ] **Step 3: 断言令牌已落位**

Run: `cd frontend && grep -n "Space Grotesk" src/assets/styles/tokens.css && grep -n "font-body" src/assets/styles/main.css`
Expected: 两条均命中。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/assets/styles/tokens.css frontend/src/assets/styles/main.css
git commit -m "feat(ui): 字体令牌切换为 Space Grotesk/DM Sans，标题收紧字距"
```

---

## Task 3: 动效与杂项令牌 + main.css 加码

**Files:**
- Modify: `frontend/src/assets/styles/tokens.css`
- Modify: `frontend/src/assets/styles/main.css`

- [ ] **Step 1: `tokens.css` 新增动效/杂项令牌（配色不动）**

在 `:root { ... }` 内、`--topbar-height` 那一行下方追加：
```css

  /* 动效（design-system.md §2.4：ease-out 无弹跳）。质感移植后路由/入场略放宽到 ~0.2s。 */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --dur-route: 0.2s;
  --dur-enter: 0.28s;

  /* 交互杂项 */
  --bg-hover: rgba(0, 0, 0, 0.04);      /* 表格/菜单 hover 底色（中性，不引入新彩色） */
  --ring-focus: 0 0 0 3px rgba(217, 119, 87, 0.18);  /* 焦点光环 = 赤陶 accent 18% */
```

- [ ] **Step 2: `main.css` 放宽路由过渡时长**

把：
```css
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.16s ease;
}
```
改为：
```css
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur-route) var(--ease-standard);
}
```

- [ ] **Step 3: `main.css` 追加滚动条 / 焦点光环 / pulse / 守卫扩容**

在 `prefers-reduced-motion` 块**之前**追加：
```css
/* ---- 细滚动条（6px，中性） ---- */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background-color: rgba(0, 0, 0, 0.18);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background-color: rgba(0, 0, 0, 0.3);
}

/* ---- 键盘焦点光环（赤陶） ---- */
:focus-visible {
  outline: none;
  box-shadow: var(--ring-focus);
  border-radius: 4px;
}

/* ---- 角标脉冲（通知/未读） ---- */
@keyframes u-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.u-pulse {
  animation: u-pulse 2s var(--ease-standard) infinite;
}
```

并把现有 reduced-motion 守卫：
```css
@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active,
  .u-fade-in {
    transition: none !important;
    animation: none !important;
  }
}
```
改为（把新动画纳入守卫）：
```css
@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active,
  .u-fade-in,
  .u-pulse {
    transition: none !important;
    animation: none !important;
  }
}
```

- [ ] **Step 4: 断言**

Run: `cd frontend && grep -n "ring-focus\|u-pulse\|dur-route" src/assets/styles/tokens.css src/assets/styles/main.css`
Expected: 命中令牌定义与引用。

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/assets/styles/tokens.css frontend/src/assets/styles/main.css
git commit -m "feat(ui): 动效/杂项令牌 + 细滚动条/焦点光环/脉冲，放宽路由过渡"
```

---

## Task 4: Element Plus 全局覆盖（表格/输入/按钮）

**Files:**
- Create: `frontend/src/assets/styles/element-overrides.css`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 写 `element-overrides.css`**

```css
/* Element Plus 全局质感覆盖。配色全部走现有令牌；遵守 design-system.md：
   表格只用行线不用斑马纹、浅表头、hover 行底色；不引入卡片阴影上浮。 */

/* ---- 表格 ---- */
.el-table {
  --el-table-border-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: var(--bg-hover);
  font-size: 13px;
}
.el-table th.el-table__cell {
  background-color: var(--bg-elevated);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
}
/* 确认无斑马纹（即便某处开了 stripe 也压平） */
.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: transparent;
}
/* 选中行赤陶浅染 */
.el-table__body tr.current-row > td.el-table__cell {
  background-color: var(--el-color-primary-light-9);
}
/* 数据感单元格可按需走等宽：给需要 mono 的列加 class="mono-cell"（cell-class-name） */
.el-table .mono-cell {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* ---- 输入焦点光环 ---- */
.el-input__wrapper.is-focus,
.el-textarea__inner:focus {
  box-shadow: var(--ring-focus), 0 0 0 1px var(--el-color-primary) inset !important;
}

/* ---- 按钮字体（display 字，略加字距，呼应源项目） ---- */
.el-button {
  font-family: var(--font-display);
  letter-spacing: 0.01em;
}
```

- [ ] **Step 2: 在 `main.ts` 末尾导入（最后导入，确保覆盖 EP 默认）**

把：
```ts
import './assets/styles/fonts.css'
import './assets/styles/main.css'
```
改为：
```ts
import './assets/styles/fonts.css'
import './assets/styles/main.css'
import './assets/styles/element-overrides.css'
```

- [ ] **Step 3: 断言导入顺序**

Run: `cd frontend && grep -n "element-overrides" src/main.ts`
Expected: 命中，且在 `main.css` 之后。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/assets/styles/element-overrides.css frontend/src/main.ts
git commit -m "feat(ui): Element Plus 全局覆盖——表格浅表头/行线/选中染色、输入光环、按钮字体"
```

---

## Task 5: 共享组件精修（StatusTag 胶囊 + KpiCard 数值 mono）

**Files:**
- Modify: `frontend/src/components/StatusTag.vue`
- Modify: `frontend/src/components/analytics/KpiCard.vue`

- [ ] **Step 1: StatusTag 加胶囊底色**

在 `StatusTag.vue` `<style scoped>` 内，把 `.status-tag` 规则：
```css
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  /* 状态枚举属于数据字段，走等宽（docs/design-system.md §2.2）。 */
  font-family: var(--font-mono);
}
```
改为：
```css
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  /* 状态枚举属于数据字段，走等宽（docs/design-system.md §2.2）。 */
  font-family: var(--font-mono);
}
/* 胶囊底色：各状态色 12% 浅染（不新增配色令牌，用现有 st-*） */
.status-draft {
  background: color-mix(in srgb, var(--st-draft) 12%, transparent);
  color: var(--st-draft);
}
.status-published {
  background: color-mix(in srgb, var(--st-published) 14%, transparent);
  color: var(--st-published);
}
.status-archived {
  background: color-mix(in srgb, var(--st-archived) 14%, transparent);
  color: var(--st-archived);
}
```

- [ ] **Step 2: KpiCard 数值走 mono**

在 `KpiCard.vue` `<style scoped>` 内，把 `.kpi-value` 规则：
```css
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  margin-top: 4px;
}
```
改为：
```css
.kpi-value {
  font-size: 24px;
  font-weight: 600;
  margin-top: 4px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/StatusTag.vue frontend/src/components/analytics/KpiCard.vue
git commit -m "feat(ui): StatusTag 胶囊底色 + KpiCard 数值等宽"
```

---

## Task 6: 同步 `docs/design-system.md`

**Files:**
- Modify: `docs/design-system.md`（§2.2 字体、§2.4 动效）

- [ ] **Step 1: 读取相关段落确认现状**

Run: `cd /Users/yuming/Desktop/smart\ CMMS/SmartSOP && sed -n '55,80p' docs/design-system.md`
Expected: 看到 §2.2 字体表与 §2.4 动效条目。

- [ ] **Step 2: 更新 §2.2 字体**

把 §2.2 中 display 字体由 `Fraunces` 改为 `Space Grotesk`（自托管 woff2），body 由系统字改为 `DM Sans`，mono 保持 `JetBrains Mono` 不变。在表后补一句：
`西文走 Space Grotesk/DM Sans 自托管 webfont（OFL），中文回退 PingFang SC/Microsoft YaHei；数据字段（编号/版本/日期/测量值/状态枚举）仍走 mono。`

- [ ] **Step 3: 更新 §2.4 动效**

把「动效：120–160ms ease-out，无弹跳。」改为：
`动效：路由/入场 ~180–220ms、交互反馈 120–160ms，ease-out 无弹跳。位移+淡入为主；**不引入卡片 hover 阴影上浮、不引入按钮辉光**（「线不靠影」红线保留）。`

保留 §2.4 其余「分隔靠线不靠影」「阴影仅下拉/模态/纸面孤岛」与 §3.7「只用行线不用斑马纹」原文不动。

- [ ] **Step 4: 提交**

```bash
git add docs/design-system.md
git commit -m "docs: design-system §2.2 字体/§2.4 动效同步质感移植（红线保留）"
```

---

## Task 7: 整体验证 pass（dev 跑起来 + 截图 + 门禁）

**Files:** 无（仅验证）

- [ ] **Step 1: 门禁全绿**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 四项全部通过。

- [ ] **Step 2: 跑 dev 并截图核对**

按 `running-smartsop-dev` skill 起 backend(8000)+frontend(5173)。用 chrome-devtools MCP 依次截图核对：
1. 登录页（AuthLayout）——字体是否变为无衬线、焦点光环；
2. 任一**表格密集**页（如库存零件列表 / 审计日志）——浅表头、行线、hover、无斑马纹；
3. 分析看板（KpiCard 数值等宽 + 图表）；
4. 程序编辑器（StatusTag 胶囊、整体字体）。
Expected: 视觉接近源项目质感，配色仍为赤陶；无方框/豆腐块（中文回退正常）。

- [ ] **Step 3: reduced-motion 核对**

在 devtools 中开启 `Emulate prefers-reduced-motion: reduce`（或 `mcp__chrome-devtools__emulate`），刷新页面，确认路由切换/入场/脉冲动画均被禁用。
Expected: 无动画。

- [ ] **Step 4: 收尾**

无新增改动则本任务无提交；如截图暴露个别 EP 硬编码灰/阴影需补覆盖，回到 `element-overrides.css` 修补并单独提交（"打磨 pass"）。

---

## Self-Review（已执行）

- **Spec 覆盖**：①字体层→Task1/2；②表格层→Task4；③动效层→Task3（+已接好的路由过渡放宽）；④共享组件→Task5；design-system 同步→Task6；验证策略→Task7。全覆盖。
- **占位符扫描**：无 TBD/TODO；每个 CSS 改动给了完整前后代码块。
- **一致性**：令牌名 `--font-body`/`--bg-hover`/`--ring-focus`/`--ease-standard`/`--dur-route` 在定义（Task2/3）与引用（Task3/4/5）处一致；字体文件名 `space-grotesk-400.woff2` 等在 Task1 下载/重命名与 fonts.css `src` 一致。
- **范围红线**：全程未改任何配色令牌；未引入卡片 hover 阴影上浮 / 按钮辉光；未引入 lucide；未搬源项目代码。
