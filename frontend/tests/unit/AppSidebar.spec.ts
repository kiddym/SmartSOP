import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import { useAuthStore } from '@/store/auth'
import { useBillingStore } from '@/store/billing'
import type { CurrentUser } from '@/types/auth'

function makeRouter(initialPath: string): Router {
  return createRouter({
    history: createMemoryHistory(initialPath),
    routes: [
      { path: '/procedures/library', component: { template: '<div/>' } },
      { path: '/procedures/drafts', component: { template: '<div/>' } },
      { path: '/procedures/folders', component: { template: '<div/>' } },
      { path: '/procedures/:id', component: { template: '<div/>' } },
      { path: '/procedures/:id/edit', component: { template: '<div/>' } },
      { path: '/admin/audit-logs', component: { template: '<div/>' } },
      { path: '/admin/settings', component: { template: '<div/>' } },
      { path: '/admin/fields', component: { template: '<div/>' } },
      { path: '/admin/heading-rules', component: { template: '<div/>' } },
      { path: '/admin/users', component: { template: '<div/>' } },
      { path: '/admin/roles', component: { template: '<div/>' } },
      { path: '/admin/teams', component: { template: '<div/>' } },
      { path: '/admin/company', component: { template: '<div/>' } },
      { path: '/admin/currencies', component: { template: '<div/>' } },
      { path: '/assets', component: { template: '<div/>' } },
      { path: '/assets/locations', component: { template: '<div/>' } },
      { path: '/inventory/parts', component: { template: '<div/>' } },
      { path: '/inventory/parts/kits', component: { template: '<div/>' } },
      { path: '/inventory/purchase-orders', component: { template: '<div/>' } },
      { path: '/inventory/vendors', component: { template: '<div/>' } },
      { path: '/maintenance/customers', component: { template: '<div/>' } },
      { path: '/maintenance/requests', component: { template: '<div/>' } },
      { path: '/maintenance/preventive-maintenances', component: { template: '<div/>' } },
      { path: '/maintenance/meters', component: { template: '<div/>' } },
      { path: '/maintenance/work-orders', component: { template: '<div/>' } },
      { path: '/maintenance/work-orders/:id', component: { template: '<div/>' } },
      { path: '/analytics', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

function setUser(roleCode: string | null, permissions: string[] = []): void {
  const store = useAuthStore()
  store.user = {
    id: 'u1',
    email: 'a@b.com',
    name: 'A',
    company_id: 'c1',
    role_code: roleCode,
    permissions,
  } satisfies CurrentUser
}

async function mountSidebar(initialPath: string, collapsed = false) {
  const router = makeRouter(initialPath)
  await router.push(initialPath)
  await router.isReady()
  return mount(AppSidebar, {
    props: { collapsed },
    global: { plugins: [router] },
  })
}

interface ExposedGroup {
  label: string
  entries: Array<{ label: string; path?: string; items?: { label: string }[] }>
}

describe('AppSidebar', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('collapsed=false：6 个 group-label（SOP/维护/资产/库存采购/分析/管理）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const labels = w.findAll('.menu-group-label')
    expect(labels.map((l) => l.text())).toEqual(['SOP', '维护', '资产', '库存采购', '分析', '管理'])
  })

  it('SOP 组含 程序库/草稿箱/文件夹（不再含审计日志）', async () => {
    const w = await mountSidebar('/procedures/library')
    expect(w.text()).toContain('程序库')
    expect(w.text()).toContain('草稿箱')
    expect(w.text()).toContain('文件夹')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const sop = groups.find((g) => g.label === 'SOP')!
    expect(sop.entries.map((e) => e.label)).toEqual(['程序库', '草稿箱', '文件夹'])
  })

  it('通知中心已从侧栏移除（顶栏铃铛为唯一入口）', async () => {
    setUser('manager', ['analytics.view'])
    const w = await mountSidebar('/analytics')
    expect(w.text()).not.toContain('通知中心')
  })

  it('客户归入维护组', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    expect(items.some((i) => i.text().includes('客户'))).toBe(true)
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const maintenance = groups.find((g) => g.label === '维护')!
    expect(maintenance.entries.some((e) => e.label === '客户')).toBe(true)
  })

  it('管理组：super_admin 见货币，非 super_admin 不见', async () => {
    setUser('super_admin')
    const w1 = await mountSidebar('/admin/users')
    expect(w1.text()).toContain('货币')
    setActivePinia(createPinia())
    setUser('manager')
    const w2 = await mountSidebar('/admin/users')
    expect(w2.text()).not.toContain('货币')
  })

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

  it('collapsed=true：group-label 不渲染', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library', true)
    expect(w.findAll('.menu-group-label').length).toBe(0)
  })

  it.each([
    ['/assets', '/assets'],
    ['/assets/locations', '/assets/locations'],
    ['/admin/users', '/admin/users'],
    ['/admin/settings', '/admin/settings'],
    ['/admin/fields', '/admin/fields'],
    ['/admin/audit-logs', '/admin/audit-logs'],
    ['/maintenance/customers', '/maintenance/customers'],
    ['/inventory/parts/kits', '/inventory/parts'],
    ['/procedures/folders', '/procedures/folders'],
  ])('在 %s 时 activeMenu 为 %s', async (path, active) => {
    setUser('super_admin')
    const w = await mountSidebar(path)
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe(active)
  })

  it('在 /procedures/drafts 时 activeMenu 为 /procedures/drafts', async () => {
    const w = await mountSidebar('/procedures/drafts')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/drafts')
  })

  it('在 /procedures/:id/edit 时 activeMenu 归到 /procedures/library', async () => {
    const w = await mountSidebar('/procedures/abc123/edit')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/library')
  })

  it('在 /admin/heading-rules 时 activeMenu 为 /admin/heading-rules', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/admin/heading-rules')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/admin/heading-rules')
  })

  it('维护组：资产不再属维护；工单/请求/预防性维护/计量/客户 均可点（无 is-disabled）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['工单', '请求', '预防性维护', '计量', '客户']) {
      const it = find(label)
      expect(it.classes()).not.toContain('is-disabled')
    }
  })

  it('在 /maintenance/requests 时 activeMenu 为该路径', async () => {
    const w = await mountSidebar('/maintenance/requests')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/maintenance/requests')
  })

  it('资产组：资产/位置 均可点', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['资产', '位置']) {
      expect(find(label).classes()).not.toContain('is-disabled')
    }
  })

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

  it('在 /inventory/parts 时 activeMenu 为该路径', async () => {
    const w = await mountSidebar('/inventory/parts')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/inventory/parts')
  })

  it('分析组：有 analytics.view 时「分析仪表盘」带 path /analytics', async () => {
    setUser('manager', ['analytics.view'])
    const w = await mountSidebar('/analytics')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const analytics = groups.find((g) => g.label === '分析')!
    const dash = analytics.entries.find((e) => e.label === '分析仪表盘')!
    expect(dash).toBeTruthy()
    expect(dash.path).toBe('/analytics')
  })

  it('分析组：无 analytics.view 时隐藏「分析仪表盘」（分析组为空）', async () => {
    setUser('manager', [])
    const w = await mountSidebar('/procedures/library')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const analytics = groups.find((g) => g.label === '分析')!
    expect(analytics.entries.length).toBe(0)
    // 空组不渲染 group-label
    const labels = w.findAll('.menu-group-label').map((l) => l.text())
    expect(labels).not.toContain('分析')
  })

  it('在 /analytics 时 activeMenu 为该路径', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/analytics')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/analytics')
  })

  it('维护组：工单有 path /maintenance/work-orders', async () => {
    const w = await mountSidebar('/procedures/library')
    const groups = (w.vm as unknown as { groups: ExposedGroup[] }).groups
    const maintenance = groups.find((g) => g.label === '维护')!
    const wo = maintenance.entries.find((e) => e.label === '工单')!
    expect(wo.path).toBe('/maintenance/work-orders')
  })

  it('在 /maintenance/work-orders/abc 时 activeMenu 为 /maintenance/work-orders', async () => {
    const w = await mountSidebar('/maintenance/work-orders/abc')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/maintenance/work-orders')
  })

  const findItem = (w: Awaited<ReturnType<typeof mountSidebar>>, label: string) =>
    w.findAll('.el-menu-item').find((i) => i.text().includes(label))!

  it('订阅未知（加载失败 subscription=null）时 SOP 项不显示锁标（后端 402 兜底，勿误锁付费用户）', async () => {
    const w = await mountSidebar('/procedures/library')
    expect(findItem(w, '程序库').find('.lock-icon').exists()).toBe(false)
  })

  it('订阅已知为 free 时 SOP 项显示锁标', async () => {
    const billing = useBillingStore()
    billing.subscription = {
      plan: 'free',
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 3,
      features: [],
      catalog: [],
    }
    const w = await mountSidebar('/procedures/library')
    expect(findItem(w, '程序库').find('.lock-icon').exists()).toBe(true)
  })

  it('每个叶子导航项都配了图标（折叠态只显示图标，漏配会变空白不可辨认）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    expect(items.length).toBeGreaterThan(0)
    for (const it of items) {
      expect(it.find('.nav-icon').exists()).toBe(true)
    }
  })
})
