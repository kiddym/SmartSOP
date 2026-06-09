import { describe, it, expect } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OrganizationConfigView from '@/views/admin/config/OrganizationConfigView.vue'

// 子页用 stub,聚合页只验证 tab 骨架与 ?tab= 双向同步
const stubs = {
  CompanySettingsView: { template: '<div class="stub-company" />' },
  SettingsView: { template: '<div class="stub-global" />' },
}

async function mountWith(query: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: OrganizationConfigView }],
  })
  router.push({ path: '/', query })
  await router.isReady()
  const wrapper = mount(OrganizationConfigView, {
    global: { plugins: [createPinia(), router], stubs },
  })
  return { wrapper, router }
}

describe('OrganizationConfigView', () => {
  it('渲染公司资料与全局参数两个 tab', async () => {
    const { wrapper } = await mountWith()
    const labels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['公司资料', '全局参数']))
  })

  it('按 query.tab=global 选中全局参数', async () => {
    const { wrapper } = await mountWith({ tab: 'global' })
    expect(wrapper.find('.el-tabs__item.is-active').text()).toBe('全局参数')
  })

  it('点击 tab 写回 query.tab', async () => {
    const { wrapper, router } = await mountWith()
    const globalTab = wrapper.findAll('.el-tabs__item').find((n) => n.text() === '全局参数')!
    await globalTab.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('global')
  })

  it('路由 query 变化时 activeTab 双向同步(前进/后退)', async () => {
    const { wrapper, router } = await mountWith({ tab: 'global' })
    expect(wrapper.find('.el-tabs__item.is-active').text()).toBe('全局参数')
    await router.replace({ query: { tab: 'company' } })
    await flushPromises()
    expect(wrapper.find('.el-tabs__item.is-active').text()).toBe('公司资料')
  })
})
