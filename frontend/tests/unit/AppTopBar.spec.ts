import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import NotificationBell from '@/components/NotificationBell.vue'
import i18n from '@/i18n'
import { useThemeStore } from '@/store/theme'

// 最小路由 stub：只要 push 不报错即可
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/procedures/folders', component: { template: '<div/>' } },
      { path: '/admin/config/organization', component: { template: '<div/>' } },
      { path: '/admin/fields', component: { template: '<div/>' } },
      { path: '/admin/heading-rules', component: { template: '<div/>' } },
      { path: '/admin/audit-logs', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

function mountTopBar(props: Record<string, unknown> = {}) {
  return mount(AppTopBar, {
    props: { collapsed: false, ...props },
    global: { plugins: [makeRouter(), i18n], stubs: { NotificationBell: true } },
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

  it('不在顶栏渲染禁用的占位搜索框（全库搜索未上线前不占位）', () => {
    const w = mountTopBar()
    expect(w.find('input.topbar-search').exists()).toBe(false)
  })

  it('渲染主题切换按钮，点击切换暗/浅', async () => {
    const w = mountTopBar()
    const btn = w.find('.topbar-theme')
    expect(btn.exists()).toBe(true)
    const theme = useThemeStore()
    const before = theme.isDark
    await btn.trigger('click')
    expect(theme.isDark).toBe(!before)
  })

  it('顶栏含通知铃铛', () => {
    const w = mountTopBar()
    expect(w.findComponent(NotificationBell).exists()).toBe(true)
  })

  it('exposes MENU_COMMANDS 命令契约：5 项，路径与现行路由一致', () => {
    const w = mountTopBar()
    const commands = (w.vm as unknown as { MENU_COMMANDS: ReadonlyArray<{ group: string; label: string; path: string }> }).MENU_COMMANDS
    expect(commands).toHaveLength(5)
    expect(commands[0]).toEqual({ group: '配置', label: '文件夹配置', path: '/procedures/folders' })
    expect(commands[1]).toEqual({ group: '配置', label: '组织设置', path: '/admin/config/organization' })
    expect(commands[2]).toEqual({ group: '配置', label: '字段管理', path: '/admin/fields' })
    expect(commands[3]).toEqual({ group: '配置', label: '标题字典', path: '/admin/heading-rules' })
    expect(commands[4]).toEqual({ group: '历史', label: '审计日志', path: '/admin/audit-logs' })
  })

  it('onCommand 派发 router.push（mock router 验证路径）', async () => {
    const router = makeRouter()
    const push = vi.spyOn(router, 'push')
    const w = mount(AppTopBar, {
      props: { collapsed: false },
      global: { plugins: [router, i18n], stubs: { NotificationBell: true } },
    })
    const onCommand = (w.vm as unknown as { onCommand: (p: string) => void }).onCommand
    onCommand('/procedures/folders')
    expect(push).toHaveBeenCalledWith('/procedures/folders')
  })
})
