# 前端"质感移植"设计：字体 + 表格 + 动效（方案 A）

**日期**：2026-06-04
**分支**：`feat/frontend-texture-reskin`
**类型**：纯前端换肤（无后端、无业务逻辑改动）

## 1. 背景与目标

参照源项目 `HP_trae_backup-cmms`（一套独立的 Vue 3 + 纯自研 Tailwind 组件库 CMMS）的视觉"质感"，
在**不改变当前赤陶工业风配色**的前提下，把当前 SmartSOP 前端（Vue 3 + Element Plus + TypeScript）
的**字体、表格、动效**三层质感尽量逼近源项目，让界面更精致、更"活"。

### 为什么不直接搬代码
- 两边技术栈不兼容：源项目用纯自研 Tailwind 组件（`<Button>`/`<Table>`/`<Modal>`），
  当前项目通篇 Element Plus（31 个文件用 `el-table`）。直接搬代码 = 整套重写或逐页改。
- 净室红线（见 memory `cmms-clean-room-baseline`）：只取"视觉质感"这一抽象设计语言，不复制源项目代码/DOM 结构。

### 方案定调（用户已确认方案 A）
- 换字体 + 表格 + 动效，**保留"扁平工业"哲学**。
- 动效只做**位移 / 淡入**，**不引入卡片 hover 阴影上浮、不引入按钮辉光**。
- 缓动 ease-out 无弹跳，时长适度放宽到 ~0.18–0.22s。
- 目标：拿到源项目约 80% 的"活泼感"，又不背叛当前工业风骨架。
- 颜色 **100% 不动**（继续用赤陶令牌）。

## 2. 现状关键事实（已核对）

1. **字体其实从未真正加载**：`tokens.css` 声明了 `--font-display: Fraunces` / `--font-mono: JetBrains Mono`，
   但 `index.html` 与 CSS 中**无任何 `@font-face` / 字体链接**，当前实际跑系统衬线 / 等宽回退。
   → 本次是"第一次真正引入 webfont"。
2. **动效地基已部分就位**（`src/assets/styles/main.css`）：已有 `.fade` 路由过渡（0.16s）、
   `u-fade-in` 入场关键帧（0.28s, translateY 6px）、`prefers-reduced-motion` 无障碍守卫。本次在其上加码。
3. **31 个文件用 `el-table`** → 表格改造必须走**全局 EP 类覆盖**，绝不逐文件改。
4. **路由过渡**：`.fade-*` CSS 已定义，但未 grep 到 `<Transition>` 实际包住 `router-view` → 需补接。
5. 源项目质感与当前 `design-system.md` 的关系：
   - 表格（§3.7「只用行线不用斑马纹 + 浅表头 + hover」）**已对齐**，仅需精修。
   - 字体（§2.2 Fraunces 衬线）**冲突**：本次改为几何无衬线。
   - 卡片阴影上浮（§2.4「线不靠影」红线）：**本方案不引入**，红线保留。
   - 动效时长（§2.4「120–160ms 无弹跳」）：放宽到 ~180–220ms，仍无弹跳。

## 3. 架构原则

所有改动集中在**全局层 + 共享层**，90 个业务页面零改动自动继承。改动落在 4 个面：

### ① 字体层（`tokens.css` + `index.html` + 自托管 woff2）
- 引入 **Space Grotesk**（display）+ **DM Sans**（body）的自托管 woff2（**不挂 Google CDN**：合规、更快、离线可用）。
- 字体文件放 `frontend/public/fonts/`，`@font-face` 写在 `main.css`（或独立 `fonts.css`），`font-display: swap`。
- 令牌调整：
  - `--font-display` → `'Space Grotesk', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif`
  - 新增 `--font-body` → `'DM Sans', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif`
  - `--font-mono` **保留** JetBrains Mono（数据等宽不变，编号/版本/日期仍走 mono）。
- 标题字距收紧：`h1–h3 { letter-spacing: -0.02em; }`。
- 中文字符自动回退到 `PingFang SC / Microsoft YaHei`（Latin webfont 不含 CJK 字形）。

### ② 表格层（全局 EP 覆盖 CSS）
集中写在一处全局样式（如 `main.css` 的 `el-table` 覆盖块或独立 `element-overrides.css`）：
- 表头：`bg-elevated` 底 + 12px + `text-secondary`；西文列名可选 `text-transform: uppercase; letter-spacing` —
  **中文列名不大写**（大写中文无意义且难看，靠 `:lang` 或仅对已知英文列生效）。
- 行分隔强化为 1px `border-subtle`，确认**无斑马纹**。
- 行 hover 底色用 `--bg-hover`（若无则新增令牌）；选中行赤陶浅染（复用 `--el-color-primary-light-9`）。
- 排序箭头、空态（带图标 + "暂无数据"）、加载骨架行——观感对齐源项目，**配色全用现有令牌**。

### ③ 动效层（`main.css` + 路由包裹）
- 路由过渡：时长 0.16s → **~0.2s ease-out**；在布局组件中用 `<Transition name="fade" mode="out-in">` **真正包住** `<router-view>`。
- 列表/卡片首屏 **`u-fade-in` stagger 入场**（位移 + 淡入；**无阴影上浮、无辉光**）。
- 加入：**shimmer 骨架**、**pulse 徽标**（通知/角标）、**菜单选中左条**（3px）、**6px 细滚动条**、**focus 3px 光环**（赤陶色）。
- 守红线：不加卡片 hover 上浮阴影、不加按钮辉光；所有缓动 ease-out 无弹跳；`prefers-reduced-motion` 全程生效（新增动画都要进守卫块）。

### ④ 共享组件精修（少量文件）
- `src/components/StatusTag.vue` → 圆点徽标样式（前导小圆点 + 胶囊）。
- `src/components/analytics/KpiCard.vue`、空态组件、骨架组件 → 对齐源项目质感，配色用现有令牌。
- 仅精修这几个**共享**组件；业务页面不动。

## 4. 范围边界（YAGNI）

**做：**
- 字体引入与令牌调整；EP 表格全局覆盖；动效加码 + 路由过渡补接；少量共享组件精修。
- 同步更新 `design-system.md`：§2.2 字体改无衬线、§2.4 动效时长放宽（保留「线不靠影」「无斑马纹」「无弹跳」红线）。

**不做：**
- ❌ 不动任何配色令牌（赤陶梯度原样保留）。
- ❌ 不动 TypeScript 架构、不动业务逻辑、不动 API 层。
- ❌ 不引入 lucide 图标（继续用 `@element-plus/icons-vue`，避免 31+ 文件级改动）。
- ❌ 不搬源项目页面/组件代码（净室 + 栈不兼容）；只取抽象质感。
- ❌ 不引入卡片 hover 阴影上浮 / 按钮辉光（方案 A 明确排除）。

## 5. 验证策略

- **本地 dev 跑起来**（backend 8000 + frontend 5173，见 `running-smartsop-dev` skill），用 chrome-devtools MCP 截图对比改造前后。
- 重点页面目视核对：列表/表格页、编辑器、分析看板、登录页。
- `pnpm lint` / `typecheck` / `test`（前端）全绿。
- 逐项确认 `prefers-reduced-motion: reduce` 下所有新动画被禁用。
- 确认中文文本字体回退正确（无方框/豆腐块）、等宽数据列仍走 mono。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 自托管 woff2 体积/许可 | 选 OFL 开源许可字体（Space Grotesk/DM Sans 均 OFL），只引常用字重（400/500/600），子集化可后续优化 |
| EP 表格覆盖打架（个别硬编码灰/阴影） | 集中在一处覆盖文件，用足够具体的选择器；留一轮"打磨 pass"对照截图修补 |
| 动效在低端机/大列表卡顿 | 入场动画只用 transform/opacity（合成层友好）；stagger 限制条数；reduced-motion 守卫兜底 |
| WangEditor 等独立主题区域字体不一致 | 本次以全局 body 字体覆盖为主；WangEditor 深度主题列为已知后续项，不在本范围 |

## 7. 交付物

- 字体文件 + `@font-face` + 令牌调整。
- 全局 EP 表格覆盖样式。
- 动效加码 + 路由过渡接线。
- 共享组件精修（StatusTag/KpiCard/空态/骨架）。
- `design-system.md` §2.2 / §2.4 同步更新。
- 改造前后截图对比 + 全绿门禁。
