import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import LoginView from '@/views/auth/LoginView.vue'
import { useAuthStore } from '@/store/auth'
import i18n from '@/i18n'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/register', name: 'register', component: { template: '<div/>' } },
      { path: '/forgot-password', name: 'forgot-password', component: { template: '<div/>' } },
    ],
  })
}

describe('LoginView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('提交表单调用 store.login 并跳转 redirect', async () => {
    const router = makeRouter()
    await router.push('/login?redirect=/folders')
    await router.isReady()
    const s = useAuthStore()
    const loginSpy = vi.spyOn(s, 'login').mockResolvedValue()
    const push = vi.spyOn(router, 'push')

    const w = mount(LoginView, { global: { plugins: [ElementPlus, router, i18n] } })
    // el-input wraps the native <input> in an extra div; setValue on the wrapper
    // does not drive v-model. Target the inner <input> by type attribute instead —
    // same pattern used across the existing unit test suite (e.g. HeadingRulesView,
    // CreateFromWordDialog, StepFormFields).
    await w.find('input[type="email"]').setValue('x@y.com')
    await w.find('input[type="password"]').setValue('pw12345678')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(loginSpy).toHaveBeenCalledWith({ email: 'x@y.com', password: 'pw12345678' })
    expect(push).toHaveBeenCalledWith('/folders')
  })

  it('填写公司标识时将 company_slug 透传给 store.login', async () => {
    const router = makeRouter()
    await router.push('/login')
    await router.isReady()
    const s = useAuthStore()
    const loginSpy = vi.spyOn(s, 'login').mockResolvedValue()

    const w = mount(LoginView, { global: { plugins: [ElementPlus, router, i18n] } })
    await w.find('input[type="email"]').setValue('a@acme.com')
    await w.find('input[type="password"]').setValue('secret123')
    await w.find('[data-test="company-slug"]').setValue('acme')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(loginSpy).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'a@acme.com', password: 'secret123', company_slug: 'acme' }),
    )
  })
})
