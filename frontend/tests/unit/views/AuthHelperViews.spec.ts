import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import ForgotPasswordView from '@/views/auth/ForgotPasswordView.vue'
import ResetPasswordView from '@/views/auth/ResetPasswordView.vue'
import AcceptInviteView from '@/views/auth/AcceptInviteView.vue'
import VerifyEmailView from '@/views/auth/VerifyEmailView.vue'
import * as authApi from '@/api/auth'
import { useAuthStore } from '@/store/auth'
import i18n from '@/i18n'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div/>' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/forgot-password', name: 'forgot-password', component: { template: '<div/>' } },
      { path: '/reset-password', name: 'reset-password', component: { template: '<div/>' } },
      { path: '/accept-invite', name: 'accept-invite', component: { template: '<div/>' } },
      { path: '/verify-email', name: 'verify-email', component: { template: '<div/>' } },
    ],
  })
}

describe('Auth helper views', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('ForgotPasswordView 提交调用 forgotPassword 并显示已发送', async () => {
    const router = makeRouter()
    await router.push('/forgot-password')
    await router.isReady()
    const spy = vi.spyOn(authApi, 'forgotPassword').mockResolvedValue()
    const w = mount(ForgotPasswordView, { global: { plugins: [ElementPlus, router, i18n] } })
    await w.find('input[type="email"]').setValue('x@y.com')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('x@y.com', '')
  })

  it('ResetPasswordView 从 query 取 token 并提交新密码', async () => {
    const router = makeRouter()
    await router.push('/reset-password?token=tok123')
    await router.isReady()
    const spy = vi.spyOn(authApi, 'resetPassword').mockResolvedValue()
    const push = vi.spyOn(router, 'push')
    const w = mount(ResetPasswordView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    const pwds = w.findAll('input[type="password"]')
    await pwds[0].setValue('newpw12345')
    await pwds[1].setValue('newpw12345')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('tok123', 'newpw12345')
    expect(push).toHaveBeenCalledWith({ name: 'login' })
  })

  it('ResetPasswordView 密码不一致不提交', async () => {
    const router = makeRouter()
    await router.push('/reset-password?token=tok123')
    await router.isReady()
    const spy = vi.spyOn(authApi, 'resetPassword').mockResolvedValue()
    const w = mount(ResetPasswordView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    const pwds = w.findAll('input[type="password"]')
    await pwds[0].setValue('newpw12345')
    await pwds[1].setValue('different99')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  it('AcceptInviteView 从 query 取 token 调用 store.acceptInvite 并跳首页', async () => {
    const router = makeRouter()
    await router.push('/accept-invite?token=inv999')
    await router.isReady()
    const s = useAuthStore()
    const spy = vi.spyOn(s, 'acceptInvite').mockResolvedValue()
    const push = vi.spyOn(router, 'push')
    const w = mount(AcceptInviteView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    await w.find('input[type="text"]').setValue('New Member')
    await w.find('input[type="password"]').setValue('memberpw1')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('inv999', 'New Member', 'memberpw1')
    expect(push).toHaveBeenCalledWith('/')
  })

  it('VerifyEmailView 有效 token 调用 verifyEmail 并显示成功', async () => {
    const router = makeRouter()
    await router.push('/verify-email?token=vtok1')
    await router.isReady()
    const spy = vi.spyOn(authApi, 'verifyEmail').mockResolvedValue()
    const w = mount(VerifyEmailView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('vtok1')
    expect(w.find('[data-test="verify-success"]').exists()).toBe(true)
  })

  it('VerifyEmailView 缺 token 直接失败、不调用接口', async () => {
    const router = makeRouter()
    await router.push('/verify-email')
    await router.isReady()
    const spy = vi.spyOn(authApi, 'verifyEmail').mockResolvedValue()
    const w = mount(VerifyEmailView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
    expect(w.find('[data-test="verify-failed"]').exists()).toBe(true)
  })

  it('VerifyEmailView 无效 token 显示失败', async () => {
    const router = makeRouter()
    await router.push('/verify-email?token=bad')
    await router.isReady()
    vi.spyOn(authApi, 'verifyEmail').mockRejectedValue(new Error('invalid'))
    const w = mount(VerifyEmailView, { global: { plugins: [ElementPlus, router, i18n] } })
    await flushPromises()
    expect(w.find('[data-test="verify-failed"]').exists()).toBe(true)
  })
})
