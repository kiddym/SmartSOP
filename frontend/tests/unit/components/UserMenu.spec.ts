import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import i18n from '@/i18n'
import UserMenu from '@/components/UserMenu.vue'
import { useAuthStore } from '@/store/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
    ],
  })
}

describe('UserMenu', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('显示用户名', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'Neo', company_id: 'c', role_code: 'admin', permissions: [] }
    const w = mount(UserMenu, { global: { plugins: [ElementPlus, i18n, router] } })
    expect(w.text()).toContain('Neo')
  })

  it('无 name 时回退到 email', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: '', company_id: 'c', role_code: 'admin', permissions: [] }
    const w = mount(UserMenu, { global: { plugins: [ElementPlus, i18n, router] } })
    expect(w.text()).toContain('a@b.c')
  })

  // el-dropdown teleports its menu to document.body; the popper isn't attached in jsdom,
  // so we drive the exposed logout() directly instead of clicking [data-test="logout"].
  it('logout 调用 store.logout 并跳 /login', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const s = useAuthStore()
    s.user = { id: '1', email: 'a@b.c', name: 'Neo', company_id: 'c', role_code: 'admin', permissions: [] }
    const logoutSpy = vi.spyOn(s, 'logout')
    const push = vi.spyOn(router, 'push')
    const w = mount(UserMenu, { global: { plugins: [ElementPlus, i18n, router] } })
    await (w.vm as unknown as { logout: () => Promise<void> }).logout()
    await flushPromises()
    expect(logoutSpy).toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith({ name: 'login' })
  })
})
