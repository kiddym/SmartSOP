import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import { useAuthStore } from '@/store/auth'
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
      { path: '/platform/users', component: { template: '<div/>' } },
      { path: '/platform/roles', component: { template: '<div/>' } },
      { path: '/platform/teams', component: { template: '<div/>' } },
      { path: '/platform/settings', component: { template: '<div/>' } },
      { path: '/platform/currencies', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

function setUser(roleCode: string | null): void {
  const store = useAuthStore()
  store.user = {
    id: 'u1',
    email: 'a@b.com',
    name: 'A',
    company_id: 'c1',
    role_code: roleCode,
    permissions: [],
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
  it('collapsed=false：5 个 group-label（SOP/维护/供应/洞察/平台）+ SOP 项目可见', async () => {
    const w = await mountSidebar('/procedures/library')
    const labels = w.findAll('.menu-group-label')
    expect(labels.length).toBe(5)
    const labelText = labels.map((l) => l.text())
    expect(labelText).toEqual(['SOP', '维护', '供应', '洞察', '平台'])
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

  it('在 /settings 时 activeMenu 为空字符串（⚙ 页面不在侧栏高亮）', async () => {
    const w = await mountSidebar('/settings')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('')
  })
})
