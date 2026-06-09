# 侧栏 IA 整改补充:设置消歧 + 客户/供应商归置

- 日期:2026-06-09
- 范围:前端 IA(SmartSOP frontend),后端不动
- 关系:本 spec 是 `2026-06-08-config-center-deployment-hub-design.md` 的**补充**,只覆盖该计划未触及的两处侧栏问题;不重写、不重复配置中心 Hub 与聚合页设计。

## 1. 背景与动机

对当前侧栏(`AppSidebar.vue`)与路由表(`router/routes.ts`)做 IA 评估后,定位到四类问题。其中两类已由已有的「配置中心 Hub」计划承接,本 spec 只处理剩余两类:

| 评估发现 | 处置 |
|---|---|
| ① 配置入口碎片化 → 需部署导向 Hub | 已由 `config-center-hub` 计划覆盖,本 spec 不重做 |
| ② 缺初始化引导线 | 同上(Hub 六阶段静态引导即此) |
| **③ 「公司设置」/「系统设置」并列、名实错位** | **本 spec Part A** |
| **④ 「客户」/「供应商」被拆到两个一级组,却由同一开关联动** | **本 spec Part B** |

### 1.1 问题 ③ 细节

- `/admin/company`(route name `platform-settings`,标签「公司设置」)→ `CompanySettingsView.vue`,含公司资料 + 模块显隐开关(`show_requests` / `show_locations` / `show_meters` / `show_vendors_customers`)。
- `/admin/settings`(route name `global-settings`,标签「系统设置」)→ `SettingsView.vue`,全局参数(审批流 / 版本控制等)。
- 二者并排放在侧栏「管理 → 组织配置」子组,名称高度相近,叶子层难辨差异;且 route name 与界面标签语义错位(`platform-settings` 实为公司资料、`global-settings` 实为全局参数)。

### 1.2 问题 ④ 细节

- 客户 `/maintenance/customers`(route name `inventory-customers`)在「维护」一级组。
- 供应商 `/inventory/vendors`(route name `inventory-vendors`)在「库存采购」一级组。
- 两者业务上是一对"往来单位",且在 `AppSidebar.hiddenPaths` 中由**同一个开关** `show_vendors_customers` 联动显隐,却被拆到两个不相关的一级组,概念割裂。客户的 route name 还带 `inventory-` 前缀,与其 `/maintenance/` path 不符。

### 1.3 既有事实(已核实)

- `inventory-customers` / `inventory-vendors` / `platform-settings` / `global-settings` 四个 route name **在 `routes.ts` 之外零引用**(无 `router.push({name})` 等用法)→ 改名安全。
- `show_vendors_customers` 在 `AppSidebar.hiddenPaths` 中按**路径**(`/inventory/vendors` + `/maintenance/customers`)隐藏,与 route name、分组无关 → 重组后行为不变。
- `AppSidebar` 模板中组标签 `v-if="!collapsed && g.entries.length"`:一级组 `entries` 经 `filterEntries` 过滤后为空时,组标签与组内项均不渲染 → 空组自动隐藏。

## 2. 设计

纯前端 IA 重构,复用现有 view 组件,不动后端、不新增端点。

### 2.1 Part A — 组织设置合并(公司资料 + 全局参数)

沿用 config-center 聚合页的 `el-tabs + ?tab=` 模式,把两个设置页合为一个带 tab 的聚合页。

**新建聚合页** `frontend/src/views/admin/config/OrganizationConfigView.vue`:

| tab 标签 | `?tab=` | 内嵌组件 |
|---|---|---|
| 公司资料 | `company` | `CompanySettingsView.vue`(原样复用,含模块开关) |
| 全局参数 | `global` | `SettingsView.vue`(原样复用) |

- 路由 `/admin/config/organization`,name `config-organization`,`meta.title='组织设置'`。
- `activeTab` 与 `route.query.tab` 双向同步(进入读 query,切换 `router.replace` 写 query),与 config-center 聚合页一致。默认 tab `company`。
- 两个子页**原样复用**,不重写业务逻辑;子页自带页标题与 padding,嵌入可接受(与 config-center 聚合页约定一致)。

**旧路由转 redirect**(不破坏书签):

```ts
{ path: '/admin/company',  redirect: { path: '/admin/config/organization', query: { tab: 'company' } } }
{ path: '/admin/settings', redirect: { path: '/admin/config/organization', query: { tab: 'global'  } } }
```

- 既有别名 redirect(`/settings → /admin/settings`、`/platform/settings → /admin/company`)**保留不动**,二次跳转仍到达新目标。
- `platform-settings` / `global-settings` 两个 name 随路由转 redirect 而消失,名实错位由"消除"解决。

**侧栏**:`管理 → 组织配置` 子组的两个叶子(公司设置 + 系统设置)**合并为一个叶子**:

```
组织配置
 ├ 组织设置   → /admin/config/organization
 └ 货币       → /admin/currencies   (super_admin only,保留)
```

- `orgConfigItems` computed 改为:`组织设置`(始终) + `货币`(super_admin)。
- `activeMenu` 现有 `if (p.startsWith('/admin/')) return p` 已覆盖 `/admin/config/organization`,无需新增。

### 2.2 Part B — 客户/供应商 → 「往来单位」分组

纯侧栏 + 路由 name 调整,**不新建页面、不改 path**。

**新建一级分组「往来单位」**,置于「库存采购」之后:

```
往来单位
 ├ 客户     → /maintenance/customers
 └ 供应商   → /inventory/vendors
```

- 从「维护」组移除「客户」;从「库存采购」组移除「供应商」。
- **route name 对齐**:`inventory-customers → partners-customers`、`inventory-vendors → partners-vendors`(零引用,安全)。
- **path 不动**:`/maintenance/customers`、`/inventory/vendors` 保持原样;`/inventory/customers → /maintenance/customers` 旧 redirect 保留。
- **联动开关收益**:`hiddenPaths` 仍按 path 隐藏两项;`show_vendors_customers` 关闭后「往来单位」组 `entries` 变空 → 组标签 `v-if` 使**整组自动消失**,优于现状(两项从混合组里零散消失)。

## 3. 与配置中心计划的协调

本 spec 与 `2026-06-08-config-center-hub` 计划各自独立可落地,无硬依赖。两处交叠点由**后落地的一方**负责对齐:

1. **Hub 入口指向**:config-center 的 `ConfigConsoleView`(其 Task 9)阶段 ① 入口由 `/admin/company` 改指 `/admin/config/organization?tab=company`,阶段 ③ 由 `/admin/settings` 改指 `?tab=global`。
2. **侧栏「组织配置」最终去留**:config-center 的 Task 11 会把侧栏「管理」组整体简化为「用户 / 角色 / 团队 / 配置中心」,**移除整个「组织配置」子组**(并入 Hub)。届时本 spec 新增的「组织设置」叶子随子组一并消失,由 Hub 的「组织设置」入口承接;`OrganizationConfigView` 聚合页与 `/admin/config/organization` 路由继续存在并被 Hub 引用。
3. **若本 spec 先落地**:「组织设置」单叶子先在「组织配置」子组中存在;config-center Task 11 落地时按其计划移除子组即可,无需回改本 spec 产物。
4. **若 config-center 先落地**:本 spec 落地时,「组织配置」子组可能已不在侧栏;此时 Part A 的侧栏改动退化为"无操作"(子组已被 Hub 取代),仅需确保 Hub 阶段 ①③ 入口指向新聚合页 tab。Part B 与 config-center 无交叠,照常落地。

> 实施计划默认"本 spec 先于 config-center Task 11 落地"的路径(当前侧栏「组织配置」子组仍在),并在计划中标注上述退化分支。

## 4. 文件结构

**新建:**
- `frontend/src/views/admin/config/OrganizationConfigView.vue` — 组织设置聚合页(公司资料 / 全局参数 两 tab)

**修改:**
- `frontend/src/router/routes.ts` — 新增 `/admin/config/organization`;`/admin/company`、`/admin/settings` 转 redirect;`inventory-customers`/`inventory-vendors` 改名
- `frontend/src/components/AppSidebar.vue` — `orgConfigItems` 合并为「组织设置」;新增「往来单位」一级组;从「维护」「库存采购」移除客户/供应商

**测试(新建/更新):**
- `frontend/tests/unit/OrganizationConfigView.spec.ts`(新建)
- `frontend/tests/unit/configRoutes.spec.ts`(更新或新建:org 两条 redirect 落到对应 tab)
- `frontend/tests/unit/AppSidebar.spec.ts`(更新:往来单位组、组织设置单叶子、开关关闭整组隐藏)

## 5. 范围与非目标

**做**:组织设置聚合页 + 旧路由 redirect、侧栏组织配置合并、往来单位一级组、客户/供应商 route name 对齐、协调说明。

**不做(YAGNI):**
- 不改 customers/vendors 的 path(避免再次路径迁移的连锁)。
- 不动后端 / 不新增端点 / 不改模型。
- 不实现 config-center 计划的 12 个 Task(仅在文档层协调)。
- 不给 `OrganizationConfigView` 子页加 `embedded` 去标题(两 tab 各保留小标题可接受,保持最小改动)。

## 6. 验证

- `npm run typecheck` + `npm run lint` 绿。
- 前端单测全绿(`npx vitest run`)。
- 运行态(`running-smartsop-dev` skill)走查:
  - 侧栏「管理 → 组织配置 → 组织设置」可达,聚合页两 tab 切换、各自 CRUD 正常;
  - 旧 URL `/admin/company`、`/admin/settings` redirect 命中对应 tab;`/settings`、`/platform/settings` 二次跳转仍达;
  - 侧栏「往来单位」组含客户 + 供应商,二者均可达;
  - 公司设置关闭 `show_vendors_customers` 后,「往来单位」整组消失;关闭其它开关行为不变。

## 7. 风险

- **route name 改名**:已核实四个 name 零引用,风险低;计划仍在改名步骤前置 grep 守卫,确认无新增引用。
- **redirect 链双跳**:`/platform/settings → /admin/company → /admin/config/organization?tab=company` 为两跳;vue-router 支持链式 redirect,运行态走查确认最终落点。
- **与 config-center 落地顺序**:已在第 3 节给出两个方向的退化分支,任一顺序均可收敛。
