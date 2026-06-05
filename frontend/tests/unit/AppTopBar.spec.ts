import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import i18n from '@/i18n'

// 最小路由 stub：只要 push 不报错即可
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/folders', component: { template: '<div/>' } },
      { path: '/settings', component: { template: '<div/>' } },
      { path: '/settings/fields', component: { template: '<div/>' } },
      { path: '/settings/heading-rules', component: { template: '<div/>' } },
      { path: '/audit-logs', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

function mountTopBar(props: Record<string, unknown> = {}) {
  return mount(AppTopBar, {
    props: { collapsed: false, ...props },
    global: { plugins: [makeRouter(), i18n] },
  })
}

describe('AppTopBar', () => {
  // 内嵌的 UserMenu 调用 useAuthStore()，需要活跃的 pinia。
  beforeEach(() => setActivePinia(createPinia()))

  it('渲染品牌文字（i18n app.name）', () => {
    const w = mountTopBar()
    expect(w.text()).toContain('Smart CMMS')
  })

  it('collapsed=false 折叠按钮 aria-label 为「折叠侧栏」', () => {
    const w = mountTopBar({ collapsed: false })
    expect(w.find('.topbar-toggle').attributes('aria-label')).toBe('折叠侧栏')
  })

  it('collapsed=true 折叠按钮 aria-label 为「展开侧栏」', () => {
    const w = mountTopBar({ collapsed: true })
    expect(w.find('.topbar-toggle').attributes('aria-label')).toBe('展开侧栏')
  })

  it('点击折叠按钮 emit toggle-sidebar', async () => {
    const w = mountTopBar()
    await w.find('.topbar-toggle').trigger('click')
    expect(w.emitted('toggle-sidebar')).toHaveLength(1)
  })

  it('搜索框为 disabled，含「即将上线」title', () => {
    const w = mountTopBar()
    const input = w.find('input.topbar-search')
    expect(input.attributes('disabled')).toBeDefined()
    expect(input.attributes('title')).toContain('即将上线')
  })

  it('unreadCount 默认（不传）不渲染徽标', () => {
    const w = mountTopBar()
    expect(w.find('.topbar-unread').exists()).toBe(false)
  })

  it('unreadCount=0 不渲染徽标', () => {
    const w = mountTopBar({ unreadCount: 0 })
    expect(w.find('.topbar-unread').exists()).toBe(false)
  })

  it('unreadCount=3 渲染徽标，含 mono 字体 class，徽标数字为 3', () => {
    const w = mountTopBar({ unreadCount: 3 })
    const badge = w.find('.topbar-unread')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).toContain('font-mono')
    expect(badge.find('.badge').text()).toBe('3')
  })

  it('齿轮设置入口已移除（配置/历史项整合进侧边栏「设置」组）', () => {
    const w = mountTopBar()
    expect(w.find('.topbar-cog').exists()).toBe(false)
    expect(w.find('[aria-label="设置菜单"]').exists()).toBe(false)
  })
})
