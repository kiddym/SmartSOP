import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'

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
      { path: '/', component: { template: '<div/>' } },
    ],
  })
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
