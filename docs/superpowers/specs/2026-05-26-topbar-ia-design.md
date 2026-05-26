# 顶栏 IA + 标准文件库 → 文件夹配置 设计

**日期：** 2026-05-26
**状态：** 待批准
**作者：** 协作设计（cui_yuming + Claude）

## 背景与目标

当前 `AppLayout.vue` 是「侧栏（220px，6 项平铺）+ 主区」的两段式外壳，没有顶栏。`docs/design-system.md` §3.1 与 `docs/feature-clarifications.md` §50 Q321 钉死的目标外壳是「顶栏（48px）+ 侧栏（240px）+ 主区」的三段式，并把入口按 **内容容器 vs 管理类** 重新切分：

- **侧栏 = 内容容器**：程序库、草稿箱、（底部「系统区」）废止
- **顶栏 ⚙▾ = 管理 / 历史**：系统设置、字段管理、审计日志

落地过程中发现两件需要在本设计内解决的附带问题：

1. **「标准文件库」是配置不是导航树**。FolderManageView 的实际形态是 CRUD 配置页（字段：`name / parent_id / prefix / sequence_digits`，定义文件夹分类与编号规则）；没有任何地方把它当作导航树。design-system §3.1 ASCII 中「标准文件库 ▸ QC 质量 ▸ QA 保证」是**未落地的 future 设想**，现状不匹配。本设计据此把它移入 ⚙ 配置组、并改名「文件夹配置」。
2. **全库搜索 / 待阅读 在 backend 不存在**（grep 全仓 `/search`、`unread` 均零命中）。Q321 假设它们存在；本设计采用**诚实占位策略**：搜索框 `disabled + title="即将上线"`，未读徽标在 `count===0` 时完全不渲染。

**目标：**

1. 把外壳从二段式（侧栏 + 主区）升级到三段式（顶栏 + 侧栏 + 主区），并按 Q321 切分入口。
2. 重命名「标准文件库」→「文件夹配置」并归入 ⚙ 配置组（UI 三处 + 现行文档四份同步）。
3. 把顶栏 / 侧栏拆成独立组件 `AppTopBar.vue` / `AppSidebar.vue`，让 `AppLayout.vue` 退回纯编排；为后续顶栏功能演化（待阅读真值、profile、通知）腾位。
4. 新增 `/procedures/deprecated` 路由——复用 `ProcedureLibraryView` + `meta.forceStatus='DEPRECATED'`，承担侧栏「废止」入口。

## 范围

**做：**

- 新组件 `AppTopBar.vue` + `AppSidebar.vue`，按下述决策矩阵实现。
- `AppLayout.vue` 重构：剥掉 brand row / menu，退回纯编排（`<AppTopBar/> + <AppSidebar/> + <RouterView/>`）。
- 路由新增 `/procedures/deprecated`；`/folders` 的 `meta.title` 改「文件夹配置」。
- `ProcedureLibraryView` 读 `route.meta.forceStatus`，在场景内强制状态筛 + 锁定 status 下拉。
- 「标准文件库」→「文件夹配置」UI 三处 + 现行文档四份同步（详见 §5）。
- 新增单测：`AppTopBar.spec.ts`、`AppSidebar.spec.ts`、router 扩展。
- design-system.md §3.1 加注「标准文件库 / 文件夹配置」术语演变 + 把 ASCII 中"标准文件库 ▸ QC ▸ QA"树状结构标注为「未落地，独立 topic」。

**不做（YAGNI）：**

- 全库搜索的真功能（API、SearchView、命中高亮）。本设计只放占位。
- 待阅读跟踪（read_state 表、unread count 端点）。本设计只预留 `unreadCount` prop。
- 响应式 `<1024px` 断点。`min-width` 隐含假设，工业内网工具不上手机。
- 顶栏品牌图形 logo（仅文字 "Smart SOP"）。
- 暗壳 / 亮壳决策（独立 topic，未启动）。
- 路由 URL 重命名（`/folders` 不改，URL 与文案解耦）。
- `FolderManageView.vue` 文件名不改（已是中性英文）。
- 历史 plan / spec 文件中"标准文件库"不动（日期快照，应保留时点表述）。

## 设计决策矩阵

| # | 维度 | 决策 | 理由 |
|---|---|---|---|
| Q1 | 品牌 + 折叠按钮位置 | **α 顶栏统揽**：≡ + "Smart SOP" 都进顶栏左端；侧栏第 0 像素就是导航项，无 brand row | "burger + brand" 是 VS Code / GitHub / Linear 的通用 shell 模式；β 那种"侧栏只剩折叠按钮的 brand row"在丢掉品牌后显得"为存在而存在"、将来必删 |
| Q2 | ⚙▾ 下拉内部结构 | **B 分组 + 分隔线**：`[配置: 文件夹配置 / 系统设置 / 字段管理]` ── `[历史: 审计日志]` | tap-count 仍为 1，比平铺多语义分组；比嵌套子菜单少一层发现成本，规避 [el-dropdown jsdom test] 嵌套测试坑 |
| Q3 | 搜索 / 待阅读占位 | **β** 搜索框 `disabled + title="即将上线"`；待阅读徽标 `v-if="unreadCount>0"`（目前永假） | 把"我们要做但还没做"诚实占位；把"我们没数据可显示"的隐藏。各取其义：占位的占位，隐藏的隐藏。避免显示"0"造成"已读 0 条未读"的伪信息 |
| ✚ | 标准文件库归位 | **重命名「文件夹配置」+ 移入 ⚙ 配置组** | 实测代码是 CRUD 配置页，不是导航树；design-system §3.1 那种 tree-in-sidebar 是未落地未来工作 |
| 默认 | 侧栏宽度 | 240px（展开）/ 64px（折叠） | design-system §3.1 文字版规范即为 240；现状 220 是历史遗留 |
| 默认 | 废止入口实现 | `/procedures/deprecated` 路由 → 复用 `ProcedureLibraryView`，`meta.forceStatus='DEPRECATED'` | 比 `?status=DEPRECATED` query 参数更利于侧栏 active 高亮；零新视图组件 |
| 默认 | 顶栏高度令牌 | 新增 `--topbar-height: 48px` 到 tokens.css | 单一来源，便于将来调整 |

## 架构

### A. 组件分解

```
AppLayout.vue (重构, ~50 行)
├── <AppTopBar :collapsed="collapsed" @toggle-sidebar="toggle" />
├── <AppSidebar :collapsed="collapsed" />
└── <RouterView />
```

| 文件 | 状态 | 职责 |
|---|---|---|
| `frontend/src/components/AppTopBar.vue` | 新建 | 48px 顶栏。布局：≡ 折叠按钮（图标随 `collapsed` 切换 `Fold`/`Expand`）/ 品牌文字 "Smart SOP" / 搜索框（disabled，`title="全库搜索 · 即将上线"`） / 未读徽标（`v-if="unreadCount > 0"`，mono 字体）/ ⚙▾ `el-dropdown` |
| `frontend/src/components/AppSidebar.vue` | 新建 | 240/64 双态侧栏。布局：[内容]组（程序库 / 草稿箱）→ flex spacer → 1px `border-subtle` → [系统区]组（废止） |
| `frontend/src/layouts/AppLayout.vue` | 重构 | 持有 `useSidebar()`，把 `collapsed/toggle` 下传；剥掉所有内部 brand / menu / aside 样式 |
| `frontend/src/composables/useSidebar.ts` | 不动 | 现有单例 composable 继续使用 |

### B. `AppTopBar.vue` 行为契约

**Props**

```ts
defineProps<{
  collapsed: boolean    // 当前侧栏折叠态，用于切换 ≡ 图标
  unreadCount?: number  // 默认 0；>0 时渲染陶土橙徽标
}>()
```

**Emits**

```ts
defineEmits<{
  (e: 'toggle-sidebar'): void
}>()
```

**模板骨架**

```vue
<header class="app-topbar">
  <button class="topbar-toggle" @click="$emit('toggle-sidebar')" :aria-label="collapsed ? '展开侧栏' : '折叠侧栏'">
    <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
  </button>
  <span class="app-brand">Smart SOP</span>
  <input
    class="topbar-search"
    disabled
    placeholder="⌕ 全库搜索（即将上线）"
    title="全库搜索 · 即将上线"
  />
  <span class="topbar-spacer" />
  <span v-if="unreadCount && unreadCount > 0" class="topbar-unread font-mono">
    待阅读 <span class="badge">{{ unreadCount }}</span>
  </span>
  <el-dropdown trigger="click" @command="onCommand">
    <button class="topbar-cog" aria-label="设置菜单">
      <el-icon><Setting /></el-icon><span class="caret">▾</span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item disabled class="group-label">配置</el-dropdown-item>
        <el-dropdown-item command="/folders">文件夹配置</el-dropdown-item>
        <el-dropdown-item command="/settings">系统设置</el-dropdown-item>
        <el-dropdown-item command="/settings/fields">字段管理</el-dropdown-item>
        <el-dropdown-item divided disabled class="group-label">历史</el-dropdown-item>
        <el-dropdown-item command="/audit-logs">审计日志</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</header>
```

```ts
const router = useRouter()
function onCommand(path: string): void {
  router.push(path)
}
```

**`group-label` 样式**：仅作分组标题，`disabled` 防止可点；CSS 让它样式跟 EP 默认 disabled item 区分（小字、灰色、`text-transform: uppercase`、`letter-spacing: .5px`、不带 hover）。

### C. `AppSidebar.vue` 行为契约

**Props**

```ts
defineProps<{
  collapsed: boolean
}>()
```

**模板骨架**

```vue
<aside class="app-aside" :class="{ collapsed }">
  <el-menu
    :default-active="activeMenu"
    :collapse="collapsed"
    :collapse-transition="false"
    router
    text-color="#3a3530"
    active-text-color="#d97757"
    background-color="transparent"
  >
    <div class="menu-group-label" v-if="!collapsed">内容</div>
    <el-menu-item index="/procedures/library">
      <el-icon><Document /></el-icon><template #title>程序库</template>
    </el-menu-item>
    <el-menu-item index="/procedures/drafts">
      <el-icon><EditPen /></el-icon><template #title>草稿箱</template>
    </el-menu-item>

    <div class="menu-spacer" />

    <div class="menu-group-label" v-if="!collapsed">系统区</div>
    <el-menu-item index="/procedures/deprecated">
      <el-icon><Delete /></el-icon><template #title>废止</template>
    </el-menu-item>
  </el-menu>
</aside>
```

**`activeMenu` 计算**

```ts
const route = useRoute()
const activeMenu = computed(() => {
  if (route.path.startsWith('/procedures/deprecated')) return '/procedures/deprecated'
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  // /procedures/library, /procedures/:id, /procedures/:id/edit 均归"程序库"
  if (route.path.startsWith('/procedures')) return '/procedures/library'
  return ''  // ⚙ 下的页面不在侧栏高亮（设置 / 字段管理 / 审计 / 文件夹配置）
})
```

> ⚙ 下的 4 个页面在侧栏**无高亮**，是符合 IA 的——它们不属于侧栏菜单空间。

**`menu-spacer` 实现**：`flex: 1` 占满中间空隙，把"系统区"压到底部。`menu-group-label` 折叠态隐藏（图标轨没法承载文本标题）。

### D. `AppLayout.vue` 重构后骨架

```vue
<script setup lang="ts">
import AppTopBar from '@/components/AppTopBar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'

const { collapsed, toggle } = useSidebar()
</script>

<template>
  <div class="app-shell">
    <AppTopBar :collapsed="collapsed" @toggle-sidebar="toggle" />
    <div class="app-body">
      <AppSidebar :collapsed="collapsed" />
      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell { display: flex; flex-direction: column; height: 100vh; }
.app-body { flex: 1; display: flex; min-height: 0; }
.app-main {
  flex: 1; overflow: auto;
  padding: 20px 24px;
  background: #faf8f4;
}
</style>
```

### E. 路由变更（`router/index.ts`）

**新增**

```ts
{
  path: '/procedures/deprecated',
  name: 'procedure-deprecated',
  component: () => import('@/views/procedures/ProcedureLibraryView.vue'),
  meta: { title: '废止程序', forceStatus: 'DEPRECATED' },
},
```

**修改**

`/folders` 路由的 `meta.title` 从 `'标准文件库'` → `'文件夹配置'`。

其他 8 条路由全部保留，URL 不动。

### F. `ProcedureLibraryView` 适配

`onMounted` 读 `route.meta.forceStatus`：

- 若存在：在视图本地 state 里强制 `statusFilter = meta.forceStatus`；把状态筛选下拉 `disabled` 并加 tooltip「当前在'废止'视图，按状态过滤已锁定」；页面标题用 `meta.title`。
- 若不存在：现状行为不变。

实现挂在 setup 顶部读 `useRoute().meta`，避免引入 watcher（路由切换会重新 mount 因为 RouterView 用 `<Transition mode="out-in">`，组件实例重建，onMounted 重新跑）。

### G. tokens.css 新增

```css
--topbar-height: 48px;
```

`AppTopBar.vue` 的 `.app-topbar` 高度引用 `var(--topbar-height)`，不硬编码。

## 标准文件库 → 文件夹配置 重命名落地

**UI 三处（必改）**

| 文件 | 行 | 改动 |
|---|---|---|
| `frontend/src/layouts/AppLayout.vue` | 59 | 该 menu-item 整体删除（迁到 ⚙），随重构一并消失 |
| `frontend/src/views/folders/FolderManageView.vue` | 115 | `<h2 class="title">标准文件库</h2>` → `<h2 class="title">文件夹配置</h2>` |
| `frontend/src/router/index.ts` | 39 | `meta: { title: '标准文件库' }` → `meta: { title: '文件夹配置' }` |

**现行 doc 四份（同步）**

| 文件 | 命中数 | 处理 |
|---|---|---|
| `docs/design-system.md` | 2 | 全部改名；§3.1 加注「文件夹配置（原称"标准文件库"，2026-05-26 起改名）」；§3.1 ASCII 中「▸ QC 质量 ▸ QA 保证」树状结构旁加注「未落地，独立 topic」；§50.2 引用同步 |
| `docs/feature-clarifications.md` | 9 | 全部改名；§50.2 Q321 决策列表中"侧栏：废止 / ⚙：设置 + 审计"补一句"文件夹配置同入 ⚙ 配置组（修订 2026-05-26）"，标记修订时间但不改原决策结构 |
| `docs/editor-behavior.md` | 4 | 全部改名（无修订注，是引用性提及） |
| `docs/data-model.md` | 1 | 全部改名（无修订注） |

**不动的（历史快照）**

- `docs/plans/2026-05-20-ui-design-system-foundation.md`（1 处）
- `docs/superpowers/plans/2026-05-25-collapsible-editor-panels.md`（1 处）
- `docs/superpowers/specs/2026-05-25-collapsible-editor-panels-design.md`（1 处）

理由：日期戳的 plan/spec 是当时的快照，措辞保留更利于回溯当时的设计语境。

## 测试

### 新增

**`frontend/tests/components/AppTopBar.spec.ts`**

1. 渲染 "Smart SOP" 品牌文本
2. 折叠按钮点击 → `wrapper.emitted('toggle-sidebar')` 长度为 1
3. 搜索 input 有 `disabled` 属性 + `title` 包含「即将上线」
4. `unreadCount=0` 不渲染 `.topbar-unread`
5. `unreadCount=3` 渲染 `.topbar-unread`，数字 `<span class="badge">` 含 `3`；`.topbar-unread` 的 computed `fontFamily` 含 `JetBrains Mono`
6. ⚙ dropdown：mock router，直接调用 `vm.onCommand('/folders')`，断言 `router.push` 被调用 `'/folders'`。**不**模拟 dropdown 打开（按 [el-dropdown jsdom test] 已知坑）
7. dropdown 命令清单契约：把 5 项 `command` 抽成组件内部常量 `MENU_COMMANDS = [{group, label, path}, ...]`，断言其长度、顺序、`path` 取值与 router 已有路由一一对应。不依赖 dropdown 渲染。

**`frontend/tests/components/AppSidebar.spec.ts`**

1. `collapsed=false`：渲染 2 个 group-label（内容 / 系统区） + 3 个 menu-item（程序库 / 草稿箱 / 废止）
2. `collapsed=true`：group-label 不渲染，menu-item 渲染图标
3. `activeMenu` 在不同 route 下的归类：mock `useRoute()` 返回 `/procedures/deprecated` → `activeMenu === '/procedures/deprecated'`；`/procedures/abc123/edit` → `'/procedures/library'`；`/settings` → `''`
4. menu-spacer 把"系统区"组压到底部（quick DOM 顺序断言：`[内容] → [spacer] → [系统区]`）

**`frontend/tests/router.spec.ts`**（如不存在则新建）

1. `/procedures/deprecated` 路由存在；`meta.forceStatus === 'DEPRECATED'`；component lazy 指 `ProcedureLibraryView`
2. `/folders` 的 `meta.title === '文件夹配置'`

### 已有不需改

- StatusTag / ProcedureTable 测试不动
- useSidebar 测试不动

## 风险与已知未解

| 项 | 风险 | 缓解 |
|---|---|---|
| `el-dropdown` 在 jsdom 下打不开 | 测试覆盖不足 | 既知问题，按 [memory: el-dropdown jsdom test] 测 `@command` 派发本身，不模拟打开 |
| ⚙ 下拉中 `el-dropdown-item disabled` 作为 group label | EP 默认 disabled 样式可能被误读成"已禁用配置项" | 用自定义 class `.group-label` 覆盖：小字、uppercase、灰色，不带 hover；视觉上明显区别 |
| `/procedures/deprecated` 复用 LibraryView 状态锁定 | 用户混淆"我现在到底在哪个视图" | 锁状态下拉 + tooltip + 用 `meta.title` 改页面标题 |
| design-system.md §3.1 ASCII 与现实背离 | 未来读者照 ASCII 实现"侧栏树"会重新撞墙 | 本设计同步加注「未落地」；如要真正实现，是另一个 topic |
| feature-clarifications.md §50.2 是"决策权威"，重命名改动该文需谨慎 | 改原决策正文等于改历史 | 不改原文，只在该节末加一行**修订注**：「2026-05-26 起，"标准文件库"改名"文件夹配置"，并归入 ⚙ 配置组」 |

## 引用

- [`docs/design-system.md`](../../design-system.md) §3.1（外壳）/ §2.4（阴影规范）/ §3.8（亮纸孤岛）
- [`docs/feature-clarifications.md`](../../feature-clarifications.md) §49（Q313–Q319 视觉立意）/ §50（Q320–Q321 IA 归位）
- 内存提示：`[[el-dropdown jsdom test]]` - EP dropdown 在 jsdom 不渲染，测 `$emit('command')`
