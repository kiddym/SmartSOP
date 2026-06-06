import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import type { CompanySettings } from '@/types/platform'

const { gcs, ucs, lc } = vi.hoisted(() => ({
  gcs: vi.fn(),
  ucs: vi.fn(),
  lc: vi.fn(),
}))
vi.mock('@/api/companySettings', () => ({
  getCompanySettings: gcs,
  updateCompanySettings: ucs,
}))
vi.mock('@/api/currencies', () => ({ listCurrencies: lc }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: () => true,
    user: { role_code: 'admin' },
  }),
}))

import AppSidebar from '@/components/AppSidebar.vue'
import CompanySettingsView from '@/views/platform/CompanySettingsView.vue'

const FULL: CompanySettings = {
  date_format: 'YYYY-MM-DD',
  timezone: 'Asia/Shanghai',
  default_currency_code: 'CNY',
  auto_assign: true,
  show_requests: true,
  show_locations: true,
  show_meters: true,
  show_vendors_customers: true,
}

function makeRouter(initialPath: string): Router {
  return createRouter({
    history: createMemoryHistory(initialPath),
    routes: [
      { path: '/procedures/library', component: { template: '<div/>' } },
      { path: '/maintenance/meters', component: { template: '<div/>' } },
      { path: '/maintenance/requests', component: { template: '<div/>' } },
      { path: '/maintenance/work-orders', component: { template: '<div/>' } },
      { path: '/maintenance/customers', component: { template: '<div/>' } },
      { path: '/assets/locations', component: { template: '<div/>' } },
      { path: '/inventory/vendors', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

async function mountSidebar(initialPath = '/procedures/library') {
  const router = makeRouter(initialPath)
  await router.push(initialPath)
  await router.isReady()
  const w = mount(AppSidebar, {
    props: { collapsed: false },
    global: { plugins: [router] },
  })
  await flushPromises()
  return w
}

function sidebarLabels(w: Awaited<ReturnType<typeof mountSidebar>>): string {
  return w.findAll('.el-menu-item').map((i) => i.text()).join('|')
}

describe('导航模块显隐（侧栏）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    gcs.mockReset()
    ucs.mockReset()
    lc.mockReset()
  })

  it('show_meters=false 时不渲染「计量」项，其余项保留', async () => {
    gcs.mockResolvedValue({ ...FULL, show_meters: false })
    const w = await mountSidebar()
    const labels = sidebarLabels(w)
    expect(labels).not.toContain('计量')
    // 同组其他项不受影响
    expect(labels).toContain('工单')
    expect(labels).toContain('请求')
  })

  it('全部开关为 true 时「计量」正常渲染', async () => {
    gcs.mockResolvedValue({ ...FULL })
    const w = await mountSidebar()
    expect(sidebarLabels(w)).toContain('计量')
  })

  it('show_vendors_customers=false 时隐藏「供应商」与「客户」两项', async () => {
    gcs.mockResolvedValue({ ...FULL, show_vendors_customers: false })
    const w = await mountSidebar()
    const labels = sidebarLabels(w)
    expect(labels).not.toContain('供应商')
    expect(labels).not.toContain('客户')
    // 库存采购组其他项保留
    expect(labels).toContain('备件库存')
  })

  it('设置加载失败时降级为全部显示（绝不隐藏导航）', async () => {
    gcs.mockRejectedValue(new Error('boom'))
    const w = await mountSidebar()
    const labels = sidebarLabels(w)
    expect(labels).toContain('计量')
    expect(labels).toContain('请求')
    expect(labels).toContain('位置')
    expect(labels).toContain('供应商')
    expect(labels).toContain('客户')
  })
})

function mountView() {
  return mount(CompanySettingsView, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('CompanySettingsView 导航开关', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    gcs.mockReset().mockResolvedValue({ ...FULL, show_meters: false })
    ucs.mockReset().mockResolvedValue({ ...FULL, show_meters: true })
    lc.mockReset().mockResolvedValue([{ id: 'c1', code: 'CNY', name: '人民币', symbol: '¥' }])
  })

  it('回显 4 个开关（show_meters=false → 对应 switch 未选中）', async () => {
    const w = mountView()
    await flushPromises()
    // 4 个导航开关标签都渲染
    expect(w.text()).toContain('显示请求模块')
    expect(w.text()).toContain('显示位置模块')
    expect(w.text()).toContain('显示计量模块')
    expect(w.text()).toContain('显示供应商与客户模块')
    // 计量开关回显为关闭
    const meterItem = w
      .findAll('.el-form-item')
      .find((fi) => fi.text().includes('显示计量模块'))
    expect(meterItem).toBeTruthy()
    expect(meterItem!.find('.el-switch').classes()).not.toContain('is-checked')
  })

  it('切换计量开关并保存，PUT 携带 show_meters=true', async () => {
    const w = mountView()
    await flushPromises()
    const meterItem = w
      .findAll('.el-form-item')
      .find((fi) => fi.text().includes('显示计量模块'))!
    await meterItem.find('.el-switch').trigger('click')
    await flushPromises()

    const saveBtn = w.findAll('.el-button').find((b) => b.text() === '保存')!
    await saveBtn.trigger('click')
    await flushPromises()

    expect(ucs).toHaveBeenCalledWith(expect.objectContaining({ show_meters: true }))
  })
})
