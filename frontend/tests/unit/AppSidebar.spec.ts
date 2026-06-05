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
      { path: '/procedures/:id', component: { template: '<div/>' } },
      { path: '/procedures/:id/edit', component: { template: '<div/>' } },
      { path: '/folders', component: { template: '<div/>' } },
      { path: '/audit-logs', component: { template: '<div/>' } },
      { path: '/settings', component: { template: '<div/>' } },
      { path: '/settings/fields', component: { template: '<div/>' } },
      { path: '/settings/heading-rules', component: { template: '<div/>' } },
      { path: '/platform/users', component: { template: '<div/>' } },
      { path: '/platform/roles', component: { template: '<div/>' } },
      { path: '/platform/teams', component: { template: '<div/>' } },
      { path: '/platform/settings', component: { template: '<div/>' } },
      { path: '/platform/currencies', component: { template: '<div/>' } },
      { path: '/maindata/locations', component: { template: '<div/>' } },
      { path: '/maindata/assets', component: { template: '<div/>' } },
      { path: '/inventory/parts', component: { template: '<div/>' } },
      { path: '/inventory/purchase-orders', component: { template: '<div/>' } },
      { path: '/inventory/vendors', component: { template: '<div/>' } },
      { path: '/inventory/customers', component: { template: '<div/>' } },
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

describe('AppSidebar', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('collapsed=false：6 个 group-label（SOP/维护/供应/洞察/平台/设置）+ SOP 项目可见', async () => {
    const w = await mountSidebar('/procedures/library')
    const labels = w.findAll('.menu-group-label')
    expect(labels.length).toBe(6)
    const labelText = labels.map((l) => l.text())
    expect(labelText).toEqual(['SOP', '维护', '供应', '洞察', '平台', '设置'])
    // SOP 域可用项
    expect(w.text()).toContain('程序库')
    expect(w.text()).toContain('草稿箱')
    expect(w.text()).toContain('文件夹')
    expect(w.text()).toContain('审计日志')
    // 占位模块标记
    expect(w.text()).toContain('即将上线')
  })

  it('super_admin：平台组含 5 项且均无「即将上线」标记', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/platform/users')
    const items = (w.vm as unknown as { platformItems: { label: string; soon?: boolean }[] })
      .platformItems
    expect(items.map((i) => i.label)).toEqual(['用户', '角色', '团队', '公司设置', '货币'])
    expect(items.every((i) => !i.soon)).toBe(true)
    expect(w.text()).toContain('用户')
    expect(w.text()).toContain('货币')
  })

  it('非 super_admin：平台组隐藏「货币」项，剩 4 项', async () => {
    setUser('manager')
    const w = await mountSidebar('/platform/users')
    const items = (w.vm as unknown as { platformItems: { label: string }[] }).platformItems
    expect(items.map((i) => i.label)).toEqual(['用户', '角色', '团队', '公司设置'])
    expect(w.text()).not.toContain('货币')
  })

  it('在 /platform/* 时 activeMenu 为该路径', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/platform/currencies')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/platform/currencies')
  })

  it('collapsed=true：group-label 不渲染', async () => {
    const w = await mountSidebar('/procedures/library', true)
    expect(w.findAll('.menu-group-label').length).toBe(0)
  })

  it('在 /procedures/drafts 时 activeMenu 为 /procedures/drafts', async () => {
    const w = await mountSidebar('/procedures/drafts')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/drafts')
  })

  it('在 /procedures/:id/edit 时 activeMenu 归到 /procedures/library', async () => {
    const w = await mountSidebar('/procedures/abc123/edit')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/library')
  })

  it('在 /folders 时 activeMenu 为 /folders', async () => {
    const w = await mountSidebar('/folders')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/folders')
  })

  it('在 /audit-logs 时 activeMenu 为 /audit-logs', async () => {
    const w = await mountSidebar('/audit-logs')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/audit-logs')
  })

  it('在 /settings 时 activeMenu 为 /settings（设置组已并入侧栏并高亮）', async () => {
    const w = await mountSidebar('/settings')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/settings')
  })

  it('在 /settings/fields 时 activeMenu 为 /settings/fields（子路径不被 /settings 抢占）', async () => {
    const w = await mountSidebar('/settings/fields')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/settings/fields')
  })

  it('在 /settings/heading-rules 时 activeMenu 为 /settings/heading-rules', async () => {
    const w = await mountSidebar('/settings/heading-rules')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/settings/heading-rules')
  })

  it('维护组：资产/位置/请求/预防性维护/计量/工单 均可点（无 is-disabled、不渲染「即将上线」）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!

    for (const label of ['资产', '位置', '请求', '预防性维护', '计量', '工单']) {
      const it = find(label)
      expect(it.classes()).not.toContain('is-disabled')
      expect(it.text()).not.toContain('即将上线')
    }
  })

  it('在 /maintenance/* 时 activeMenu 为该路径', async () => {
    const w = await mountSidebar('/maintenance/requests')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/maintenance/requests')
  })

  it('在 /maindata/assets 时 activeMenu 为该路径', async () => {
    const w = await mountSidebar('/maindata/assets')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/maindata/assets')
  })

  it('供应组：备件库存/采购单/供应商/客户 均可点（无 is-disabled、不渲染「即将上线」）', async () => {
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    const find = (label: string) => items.find((i) => i.text().includes(label))!
    for (const label of ['备件库存', '采购单', '供应商', '客户']) {
      const it = find(label)
      expect(it.classes()).not.toContain('is-disabled')
      expect(it.text()).not.toContain('即将上线')
    }
  })

  it('在 /inventory/* 时 activeMenu 为该路径', async () => {
    const w = await mountSidebar('/inventory/parts')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/inventory/parts')
  })

  it('洞察组：有 analytics.view 时「分析仪表盘」带 path、无 soon', async () => {
    setUser('manager', ['analytics.view'])
    const w = await mountSidebar('/analytics')
    const items = (
      w.vm as unknown as { insightItems: { label: string; path?: string; soon?: boolean }[] }
    ).insightItems
    const dash = items.find((i) => i.label === '分析仪表盘')!
    expect(dash).toBeTruthy()
    expect(dash.path).toBe('/analytics')
    expect(dash.soon).toBeFalsy()
    // 通知中心仍 soon
    const notif = items.find((i) => i.label === '通知中心')!
    expect(notif.soon).toBe(true)
  })

  it('洞察组：无 analytics.view 时隐藏「分析仪表盘」', async () => {
    setUser('manager', [])
    const w = await mountSidebar('/procedures/library')
    const items = (w.vm as unknown as { insightItems: { label: string }[] }).insightItems
    expect(items.map((i) => i.label)).toEqual(['通知中心'])
  })

  it('在 /analytics 时 activeMenu 为该路径', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/analytics')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/analytics')
  })

  it('维护组：工单有 path /maintenance/work-orders、无 soon', async () => {
    const w = await mountSidebar('/procedures/library')
    const groups = (
      w.vm as unknown as {
        groups: { label: string; items: { label: string; path?: string; soon?: boolean }[] }[]
      }
    ).groups
    const maintenance = groups.find((g) => g.label === '维护')!
    const wo = maintenance.items.find((i) => i.label === '工单')!
    expect(wo.path).toBe('/maintenance/work-orders')
    expect(wo.soon).toBeFalsy()
  })

  it('在 /maintenance/work-orders/abc 时 activeMenu 为 /maintenance/work-orders', async () => {
    const w = await mountSidebar('/maintenance/work-orders/abc')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/maintenance/work-orders')
  })

  const findItem = (w: Awaited<ReturnType<typeof mountSidebar>>, label: string) =>
    w.findAll('.el-menu-item').find((i) => i.text().includes(label))!

  it('订阅未知（加载失败 subscription=null）时 SOP 项不显示锁标（后端 402 兜底，勿误锁付费用户）', async () => {
    // 默认 billing.subscription = null（模拟一次拉取失败/未加载）
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

  it('每个导航项都配了图标（折叠态只显示图标，漏配会变空白不可辨认）', async () => {
    setUser('super_admin')
    const w = await mountSidebar('/procedures/library')
    const items = w.findAll('.el-menu-item')
    expect(items.length).toBeGreaterThan(0)
    // 默认 slot 的 .nav-icon 在折叠态仍渲染；每个菜单项都必须有，含 soon 占位项。
    for (const it of items) {
      expect(it.find('.nav-icon').exists()).toBe(true)
    }
  })
})
