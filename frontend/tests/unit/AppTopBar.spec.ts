import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
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

  it('exposes MENU_COMMANDS 命令契约：5 项，路径与现行路由一致', () => {
    const w = mountTopBar()
    const commands = (w.vm as unknown as { MENU_COMMANDS: ReadonlyArray<{ group: string; label: string; path: string }> }).MENU_COMMANDS
    expect(commands).toHaveLength(5)
    expect(commands[0]).toEqual({ group: '配置', label: '文件夹配置', path: '/folders' })
    expect(commands[1]).toEqual({ group: '配置', label: '系统设置', path: '/settings' })
    expect(commands[2]).toEqual({ group: '配置', label: '字段管理', path: '/settings/fields' })
    expect(commands[3]).toEqual({ group: '配置', label: '标题字典', path: '/settings/heading-rules' })
    expect(commands[4]).toEqual({ group: '历史', label: '审计日志', path: '/audit-logs' })
  })

  it('onCommand 派发 router.push（mock router 验证路径）', async () => {
    const router = makeRouter()
    const push = vi.spyOn(router, 'push')
    const w = mount(AppTopBar, {
      props: { collapsed: false },
      global: { plugins: [router, i18n] },
    })
    const onCommand = (w.vm as unknown as { onCommand: (p: string) => void }).onCommand
    onCommand('/folders')
    expect(push).toHaveBeenCalledWith('/folders')
  })
})
