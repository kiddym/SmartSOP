# 侧栏 IA 整改补充 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「公司设置/系统设置」合并为带 tab 的「组织设置」聚合页并消歧 route name;把「客户/供应商」合并为「往来单位」一级组。

**Architecture:** 纯前端 IA。新建一个 `el-tabs` 聚合页复用现有两个设置 view;旧设置路由转 redirect 到对应 tab;侧栏「组织配置」两叶子合并为一叶子,新增「往来单位」一级组并从「维护」「库存采购」移出客户/供应商;客户/供应商 route name 对齐(零引用,安全)。不动后端、不改 path。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Element Plus、vue-router、Pinia、Vitest + @vue/test-utils。

参考 spec:`docs/superpowers/specs/2026-06-09-sidebar-ia-cleanup-design.md`

---

## 前置事实(已核实,执行时无需重查)

- `inventory-customers` / `inventory-vendors` / `platform-settings` / `global-settings` 四个 route name **仅在 `frontend/src/router/routes.ts` 定义,别处零引用** → 改名/删名安全。
- `/admin/settings` → `@/views/settings/SettingsView.vue`(全局参数);`/admin/company` → `@/views/platform/CompanySettingsView.vue`(公司资料+模块开关)。
- ⚠️ **当前 `tests/unit/AppSidebar.spec.ts` 已是红的**:最近一次 commit(`1a0ae6d`)把组件「管理」组改成 6 个子分组,但该 spec 的 L118-133 仍断言旧的 4 子分组 `['人员与权限','组织配置','系统配置','审计']`。Task 3 会把这条断言改正为当前真实的 6 子分组结构(顺带修红)。
- `AppSidebar.spec.ts` 用自带的 `makeRouter` 路由桩(非真实 routes),`activeMenu` 由 path 字符串计算;改 route name 不影响该 spec。
- config-center 计划(`2026-06-08-config-center-hub`)目前**仅 Task 1 落地**(CustomFieldsView lockedEntity),其 Hub/聚合页/Task 11 侧栏简化**尚未实现**。故本计划按"先于 config-center Task 11"的默认路径执行(侧栏「组织配置」子组仍在)。

---

## 文件结构

**新建:**
- `frontend/src/views/admin/config/OrganizationConfigView.vue` — 组织设置聚合页(公司资料/全局参数 两 tab)
- `frontend/tests/unit/OrganizationConfigView.spec.ts` — 聚合页测试
- `frontend/tests/unit/configRoutes.spec.ts` — 组织设置路由 redirect + 改名测试

**修改:**
- `frontend/src/router/routes.ts` — 新增 `/admin/config/organization`;`/admin/company`、`/admin/settings` 转 redirect;`inventory-customers`/`inventory-vendors` 改名
- `frontend/src/components/AppSidebar.vue` — `orgConfigItems` 合并为「组织设置」;新增「往来单位」组;移出客户/供应商;删 `Setting` 未用 import
- `frontend/tests/unit/AppSidebar.spec.ts` — 更新断言(修红 + 新结构)

所有命令在 `frontend/` 目录下执行。

---

## Task 1: 组织设置聚合页

**Files:**
- Create: `frontend/src/views/admin/config/OrganizationConfigView.vue`
- Test: `frontend/tests/unit/OrganizationConfigView.spec.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/OrganizationConfigView.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OrganizationConfigView from '@/views/admin/config/OrganizationConfigView.vue'

// 子页用 stub,聚合页只验证 tab 骨架
const stubs = {
  CompanySettingsView: { template: '<div class="stub-company" />' },
  SettingsView: { template: '<div class="stub-global" />' },
}

function mountWith(query: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: OrganizationConfigView }],
  })
  router.push({ path: '/', query })
  return router.isReady().then(() =>
    mount(OrganizationConfigView, { global: { plugins: [createPinia(), router], stubs } }),
  )
}

describe('OrganizationConfigView', () => {
  it('渲染公司资料与全局参数两个 tab', async () => {
    const w = await mountWith()
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['公司资料', '全局参数']))
  })

  it('按 query.tab=global 选中全局参数', async () => {
    const w = await mountWith({ tab: 'global' })
    expect(w.find('.el-tabs__item.is-active').text()).toBe('全局参数')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/OrganizationConfigView.spec.ts`
Expected: FAIL(组件不存在)

- [ ] **Step 3: 创建 OrganizationConfigView.vue**

新建 `frontend/src/views/admin/config/OrganizationConfigView.vue`:

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import CompanySettingsView from '@/views/platform/CompanySettingsView.vue'
import SettingsView from '@/views/settings/SettingsView.vue'

// 公司资料(CompanySettingsView)+ 全局参数(SettingsView)合为一页两 tab。
// 两子页原样复用、各自带页标题,故本聚合页不再加标题。tab 由 ?tab= 驱动,
// 供旧路由 /admin/company、/admin/settings redirect 落到指定 tab。
const route = useRoute()
const router = useRouter()
const activeTab = ref<string>((route.query.tab as string) || 'company')
watch(activeTab, (t) => router.replace({ query: { ...route.query, tab: t } }))
</script>

<template>
  <div class="config-aggregate">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="公司资料" name="company"><CompanySettingsView /></el-tab-pane>
      <el-tab-pane label="全局参数" name="global"><SettingsView /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `npx vitest run tests/unit/OrganizationConfigView.spec.ts`
Expected: PASS

- [ ] **Step 5: typecheck**

Run: `npm run typecheck`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/admin/config/OrganizationConfigView.vue frontend/tests/unit/OrganizationConfigView.spec.ts
git commit -m "feat(config): 组织设置聚合页(公司资料+全局参数两 tab)"
```

---

## Task 2: 路由新增/重定向 + 客户供应商改名

**Files:**
- Modify: `frontend/src/router/routes.ts`
- Test: `frontend/tests/unit/configRoutes.spec.ts`

- [ ] **Step 1: 改名前 grep 守卫(确认零新增引用)**

Run: `cd frontend && grep -rn "inventory-customers\|inventory-vendors\|platform-settings\|global-settings" src tests --include="*.ts" --include="*.vue" | grep -v "router/routes.ts"`
Expected: 无输出(若有输出,说明出现了新引用,需先把那些 `{ name: '...' }` 用法同步改名,再继续)

- [ ] **Step 2: 写失败测试**

新建 `frontend/tests/unit/configRoutes.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('组织设置路由', () => {
  it('新增 /admin/config/organization 可解析且 name 为 config-organization', async () => {
    const r = makeRouter()
    await r.push('/admin/config/organization')
    expect(r.currentRoute.value.matched.length).toBeGreaterThan(0)
    expect(r.currentRoute.value.name).toBe('config-organization')
  })

  it('旧设置路由 redirect 到聚合页对应 tab', async () => {
    const cases: [string, string][] = [
      ['/admin/company', 'company'],
      ['/admin/settings', 'global'],
    ]
    const r = makeRouter()
    for (const [from, tab] of cases) {
      await r.push(from)
      expect(r.currentRoute.value.path).toBe('/admin/config/organization')
      expect(r.currentRoute.value.query.tab).toBe(tab)
    }
  })

  it('既有别名 redirect 双跳仍达组织设置', async () => {
    const r = makeRouter()
    await r.push('/platform/settings') // → /admin/company → ?tab=company
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('company')
    await r.push('/settings') // → /admin/settings → ?tab=global
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('global')
  })

  it('客户/供应商 route name 已对齐 partners-*', async () => {
    const r = makeRouter()
    await r.push('/maintenance/customers')
    expect(r.currentRoute.value.name).toBe('partners-customers')
    await r.push('/inventory/vendors')
    expect(r.currentRoute.value.name).toBe('partners-vendors')
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `npx vitest run tests/unit/configRoutes.spec.ts`
Expected: FAIL(新路由不存在 / 旧路由仍是组件 / name 仍是 inventory-*)

- [ ] **Step 4: 新增组织设置路由**

在 `frontend/src/router/routes.ts` 中,把 `/admin/settings` 这条记录(当前 L117-122)整段替换为「新聚合页 + 旧路由 redirect」。

当前:

```ts
  {
    path: '/admin/settings',
    name: 'global-settings',
    component: () => import('@/views/settings/SettingsView.vue'),
    meta: { title: '系统设置', requiresAuth: true },
  },
  { path: '/settings', redirect: '/admin/settings' },
```

替换为:

```ts
  {
    path: '/admin/config/organization',
    name: 'config-organization',
    component: () => import('@/views/admin/config/OrganizationConfigView.vue'),
    meta: { title: '组织设置', requiresAuth: true },
  },
  {
    path: '/admin/settings',
    redirect: { path: '/admin/config/organization', query: { tab: 'global' } },
  },
  { path: '/settings', redirect: '/admin/settings' },
```

- [ ] **Step 5: 旧 /admin/company 转 redirect**

`routes.ts` 中 `/admin/company` 记录(当前 L195-200):

```ts
  {
    path: '/admin/company',
    name: 'platform-settings',
    component: () => import('@/views/platform/CompanySettingsView.vue'),
    meta: { title: '公司设置', requiresAuth: true },
  },
  { path: '/platform/settings', redirect: '/admin/company' },
```

替换为(保留下面那条别名 redirect 不动):

```ts
  {
    path: '/admin/company',
    redirect: { path: '/admin/config/organization', query: { tab: 'company' } },
  },
  { path: '/platform/settings', redirect: '/admin/company' },
```

- [ ] **Step 6: 客户/供应商 route name 对齐**

`routes.ts` 中(当前 L267-274):

```ts
    path: '/inventory/vendors',
    name: 'inventory-vendors',
```
改 name 为:
```ts
    path: '/inventory/vendors',
    name: 'partners-vendors',
```

```ts
    path: '/maintenance/customers',
    name: 'inventory-customers',
```
改 name 为:
```ts
    path: '/maintenance/customers',
    name: 'partners-customers',
```

> path 与 `{ path: '/inventory/customers', redirect: '/maintenance/customers' }` 旧别名均不动。

- [ ] **Step 7: 运行确认通过 + typecheck**

Run: `npx vitest run tests/unit/configRoutes.spec.ts && npm run typecheck`
Expected: PASS,无类型错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/router/routes.ts frontend/tests/unit/configRoutes.spec.ts
git commit -m "feat(nav): 组织设置路由聚合 + 客户供应商 route name 对齐"
```

---

## Task 3: 侧栏重排(组织设置合并 + 往来单位组)+ 修红

**Files:**
- Modify: `frontend/src/components/AppSidebar.vue`
- Test: `frontend/tests/unit/AppSidebar.spec.ts`

- [ ] **Step 1: 更新测试(修红 + 新结构)**

对 `frontend/tests/unit/AppSidebar.spec.ts` 做以下精确替换。

**(1a) 顶部 import** —— 在现有 import 区(`import type { CurrentUser } from '@/types/auth'` 之后)追加两行:

```ts
import { useCompanySettingsStore } from '@/store/companySettings'
import type { CompanySettings } from '@/types/platform'
```

**(1b) makeRouter 路由桩** —— 在 `{ path: '/admin/company', component: { template: '<div/>' } },` 之后追加一行:

```ts
      { path: '/admin/config/organization', component: { template: '<div/>' } },
```

**(1c) 7 个 group-label** —— 把现有用例(当前 L76-81)

```ts
  it('collapsed=false：6 个 group-label（SOP/维护/资产/库存采购/分析/管理）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const labels = w.findAll('.menu-group-label')
    expect(labels.map((l) => l.text())).toEqual(['SOP', '维护', '资产', '库存采购', '分析', '管理'])
  })
```

替换为:

```ts
  it('collapsed=false：7 个 group-label（含往来单位）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const labels = w.findAll('.menu-group-label')
    expect(labels.map((l) => l.text())).toEqual([
      'SOP',
      '维护',
      '资产',
      '库存采购',
      '往来单位',
      '分析',
      '管理',
    ])
  })
```

**(1d) 客户/供应商归往来单位** —— 把现有「客户归入维护组」用例(当前 L99-106)

```ts
  it('客户归入维护组', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    expect(items.some((i) => i.text().includes('客户'))).toBe(true)
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const maintenance = groups.find((g) => g.label === '维护')!
    expect(maintenance.entries.some((e) => e.label === '客户')).toBe(true)
  })
```

替换为:

```ts
  it('客户与供应商归入「往来单位」组,且不再在维护/库存采购组', async () => {
    const w = await mountSidebar('/procedures/library')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const partners = groups.find((g) => g.label === '往来单位')!
    expect(partners.entries.map((e) => e.label)).toEqual(['客户', '供应商'])
    const maintenance = groups.find((g) => g.label === '维护')!
    expect(maintenance.entries.some((e) => e.label === '客户')).toBe(false)
    const inventory = groups.find((g) => g.label === '库存采购')!
    expect(inventory.entries.some((e) => e.label === '供应商')).toBe(false)
  })
```

**(1e) 管理组 6 子分组(修红)+ 组织设置叶子** —— 把现有「管理组：4 个折叠子分组」用例(当前 L118-133)

```ts
  it('管理组：4 个折叠子分组（人员与权限/组织配置/系统配置/审计）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/admin/users')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const admin = groups.find((g) => g.label === '管理')!
    expect(admin.entries.map((e) => e.label)).toEqual([
      '人员与权限',
      '组织配置',
      '系统配置',
      '审计',
    ])
    // 每个子分组都带 items（NavSubGroup）
    expect(admin.entries.every((e) => Array.isArray(e.items))).toBe(true)
    const subMenus = w.findAll('.el-sub-menu')
    expect(subMenus.length).toBe(4)
  })
```

替换为:

```ts
  it('管理组：6 个折叠子分组', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/admin/users')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const admin = groups.find((g) => g.label === '管理')!
    expect(admin.entries.map((e) => e.label)).toEqual([
      '人员与权限',
      '组织配置',
      'SOP 配置',
      '表单与字段',
      '自动化与数据',
      '审计',
    ])
    expect(admin.entries.every((e) => Array.isArray(e.items))).toBe(true)
    expect(w.findAll('.el-sub-menu').length).toBe(6)
  })

  it('组织配置子组：公司设置/系统设置 已合并为「组织设置」单叶子', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/admin/users')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const admin = groups.find((g) => g.label === '管理')!
    const org = admin.entries.find((e) => e.label === '组织配置')!
    expect(org.items!.map((i) => i.label)).toEqual(['组织设置', '货币'])
  })
```

**(1f) 维护组去客户** —— 把现有「维护组：…客户 均可点」用例(当前 L173-181)

```ts
  it('维护组：资产不再属维护；工单/请求/预防性维护/计量/客户 均可点（无 is-disabled）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['工单', '请求', '预防性维护', '计量', '客户']) {
      const it = find(label)
      expect(it.classes()).not.toContain('is-disabled')
    }
  })
```

替换为:

```ts
  it('维护组：工单/请求/预防性维护/计量 均可点（客户已移出）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['工单', '请求', '预防性维护', '计量']) {
      expect(find(label).classes()).not.toContain('is-disabled')
    }
  })
```

**(1g) 库存采购去供应商 + 往来单位可点** —— 把现有「库存采购组：…供应商 均可点」用例(当前 L198-207)

```ts
  it('库存采购组：备件库存/采购单/供应商 均可点（多备件套件已下沉为 Tab）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['备件库存', '采购单', '供应商']) {
      expect(find(label).classes()).not.toContain('is-disabled')
    }
    // 多备件套件不再作为侧栏一级项
    expect(items.some((i) => i.text().includes('多备件套件'))).toBe(false)
  })
```

替换为:

```ts
  it('库存采购组：备件库存/采购单 均可点（供应商已移出，多备件套件已下沉为 Tab）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['备件库存', '采购单']) {
      expect(find(label).classes()).not.toContain('is-disabled')
    }
    expect(items.some((i) => i.text().includes('多备件套件'))).toBe(false)
  })

  it('往来单位组：客户/供应商 均可点', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['客户', '供应商']) {
      expect(find(label).classes()).not.toContain('is-disabled')
    }
  })

  it('关闭 show_vendors_customers 后「往来单位」整组消失', async () => {
    setUser('super_admin')
    const cs = useCompanySettingsStore()
    // 仅设该开关为关;其余开关字段缺省 → isModuleVisible 返回 true(显示)。
    cs.settings = { show_vendors_customers: false } as unknown as CompanySettings
    const w = await mountSidebar('/procedures/library')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const partners = groups.find((g) => g.label === '往来单位')
    expect(partners?.entries.length ?? 0).toBe(0)
    expect(w.findAll('.menu-group-label').map((l) => l.text())).not.toContain('往来单位')
  })
```

**(1h) activeMenu it.each 追加组织设置** —— 在 `it.each([...])`(当前 L141-150)的数组里,`['/admin/settings', '/admin/settings'],` 之后追加一行:

```ts
    ['/admin/config/organization', '/admin/config/organization'],
```

- [ ] **Step 2: 运行确认失败**

Run: `npx vitest run tests/unit/AppSidebar.spec.ts`
Expected: FAIL(组件仍是旧结构,新断言不满足)

- [ ] **Step 3: 改 AppSidebar.vue —— orgConfigItems 合并**

把 `orgConfigItems` computed(当前 L105-113)整段:

```ts
const orgConfigItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [{ label: '公司设置', path: '/admin/company', icon: OfficeBuilding }]
  if (auth.user?.role_code === 'super_admin') {
    items.push({ label: '货币', path: '/admin/currencies', icon: Coin })
  }
  // 全局参数「系统设置」并入组织配置（消除旧「系统配置」子分组与同名叶子项的父子重名）。
  items.push({ label: '系统设置', path: '/admin/settings', icon: Setting })
  return items
})
```

替换为:

```ts
const orgConfigItems = computed<NavItem[]>(() => {
  // 公司资料 + 全局参数已合并为「组织设置」聚合页(/admin/config/organization,两 tab)。
  const items: NavItem[] = [
    { label: '组织设置', path: '/admin/config/organization', icon: OfficeBuilding },
  ]
  if (auth.user?.role_code === 'super_admin') {
    items.push({ label: '货币', path: '/admin/currencies', icon: Coin })
  }
  return items
})
```

- [ ] **Step 4: 改 AppSidebar.vue —— 维护组移除客户**

把「维护」组里这两行(当前 L184-185):

```ts
      { label: '计量', path: '/maintenance/meters', feature: 'meters', icon: Odometer },
      { label: '客户', path: '/maintenance/customers', icon: Avatar },
```

改为(删掉客户那行):

```ts
      { label: '计量', path: '/maintenance/meters', feature: 'meters', icon: Odometer },
```

- [ ] **Step 5: 改 AppSidebar.vue —— 库存采购移除供应商 + 新增往来单位组**

把「库存采购」组结尾的供应商行 + 其后到「分析」组之间(当前 L205-208):

```ts
      { label: '供应商', path: '/inventory/vendors', icon: Shop },
    ],
  },
  {
    label: '分析',
```

替换为(删供应商、补「往来单位」一级组):

```ts
    ],
  },
  {
    label: '往来单位',
    entries: [
      { label: '客户', path: '/maintenance/customers', icon: Avatar },
      { label: '供应商', path: '/inventory/vendors', icon: Shop },
    ],
  },
  {
    label: '分析',
```

- [ ] **Step 6: 改 AppSidebar.vue —— 删除未用的 Setting import**

`Setting` 现仅被已删除的「系统设置」叶子使用。把 import 区(当前 L34-35):

```ts
  // 管理：系统配置
  Setting,
```

改为(删 `Setting,` 那行,保留注释):

```ts
  // 管理：系统配置
```

- [ ] **Step 7: 运行测试 + typecheck + lint**

Run: `npx vitest run tests/unit/AppSidebar.spec.ts && npm run typecheck && npm run lint`
Expected: PASS,无类型/lint 错误(未用 import 会被 lint 拦截 → 据此确认 Setting 已删干净)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AppSidebar.vue frontend/tests/unit/AppSidebar.spec.ts
git commit -m "feat(nav): 侧栏组织设置合并为单叶子 + 客户供应商并入「往来单位」组"
```

---

## Task 4: 全量门禁 + 运行态走查

**Files:** 无(验证 + 收尾)

- [ ] **Step 1: 全量门禁**

Run: `npm run typecheck && npm run lint && npx vitest run`
Expected: 三者全绿(注意:此前 `AppSidebar.spec.ts` 的预存红已在 Task 3 修复,此处应全绿)

- [ ] **Step 2: 运行态走查**

用 `running-smartsop-dev` skill 启动 dev,以管理员(super_admin)登录,逐项确认:
- 侧栏「管理 → 组织配置 → 组织设置」可达;聚合页「公司资料 / 全局参数」两 tab 切换正常,各自表单 CRUD/保存正常;
- 直接访问 `/admin/company`、`/admin/settings` 分别 redirect 到 `/admin/config/organization?tab=company`、`?tab=global`;`/settings`、`/platform/settings` 二次跳转仍达对应 tab;
- 侧栏出现「往来单位」一级组(位于「库存采购」之后),含客户 + 供应商,二者均可达;
- 「维护」组不再有客户;「库存采购」组不再有供应商;
- 进入「组织设置 → 公司资料」,关闭「显示供应商/客户」开关并保存后,刷新侧栏 →「往来单位」整组消失;重新开启后恢复;
- 折叠态侧栏:「组织设置」「客户」「供应商」均有图标,不出现空白项。

- [ ] **Step 3: 收尾 commit(如走查触发微调)**

```bash
git add -A
git commit -m "chore(nav): 侧栏 IA 整改运行态走查修正与收口"
```

---

## Self-Review(已对照 spec 检查)

- **Spec 覆盖**:Part A 组织设置聚合页(Task 1)+ 旧路由 redirect & 侧栏合并(Task 2/3);Part B 往来单位组 & 改名(Task 2/3);协调说明在 spec 第 3 节,本计划默认"先于 config-center Task 11"路径并已在前置事实标注。验证(Task 4)对应 spec 第 6 节。
- **非目标**:未改 customers/vendors 的 path、未动后端、未实现 config-center 12 Task、未给子页加 embedded —— 计划内均未出现。
- **类型/命名一致**:聚合页 route name `config-organization`、tab name `company`/`global`、新 route name `partners-customers`/`partners-vendors`、侧栏叶子「组织设置」「往来单位」在各 Task 间一致。
- **预存红处置**:`AppSidebar.spec.ts` L118 旧 4 子分组断言由 Task 3 (1e) 改正为真实 6 子分组,Task 4 Step 1 全量门禁因此能全绿。
- **改名安全**:Task 2 Step 1 前置 grep 守卫确认四个 route name 零新增引用后再改。
