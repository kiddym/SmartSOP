import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import i18n from '@/i18n'
import RegisterView from '@/views/auth/RegisterView.vue'
import { useAuthStore } from '@/store/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/register', name: 'register', component: { template: '<div/>' } },
    ],
  })
}

describe('RegisterView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('完整填写提交：调用 store.register(snake_case payload) 并跳首页', async () => {
    const router = makeRouter()
    await router.push('/register')
    await router.isReady()
    const s = useAuthStore()
    const registerSpy = vi.spyOn(s, 'register').mockResolvedValue()
    const push = vi.spyOn(router, 'push')

    const w = mount(RegisterView, { global: { plugins: [ElementPlus, i18n, router] } })
    // el-input passes data-test through to the inner <input> element directly,
    // so [data-test="..."] selects the native input (confirmed: 4 inputs in DOM order,
    // no extra input from show-password which only adds a toggle button).
    await w.find('[data-test="companyName"]').setValue('Acme')
    await w.find('[data-test="name"]').setValue('Neo')
    await w.find('[data-test="email"]').setValue('neo@acme.com')
    await w.find('[data-test="password"]').setValue('pw12345678')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(registerSpy).toHaveBeenCalledWith({
      company_name: 'Acme', name: 'Neo', email: 'neo@acme.com', password: 'pw12345678',
    })
    expect(push).toHaveBeenCalledWith('/')
  })

  it('密码不足 8 位：不调用 store.register', async () => {
    const router = makeRouter()
    // router.isReady() only resolves after a push — must navigate before awaiting.
    await router.push('/register')
    await router.isReady()
    const s = useAuthStore()
    const registerSpy = vi.spyOn(s, 'register').mockResolvedValue()

    const w = mount(RegisterView, { global: { plugins: [ElementPlus, i18n, router] } })
    await w.find('[data-test="companyName"]').setValue('Acme')
    await w.find('[data-test="name"]').setValue('Neo')
    await w.find('[data-test="email"]').setValue('neo@acme.com')
    await w.find('[data-test="password"]').setValue('short')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(registerSpy).not.toHaveBeenCalled()
  })
})
