import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import i18n from '@/i18n'
import App from '@/App.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div class="biz"/>' }, meta: { requiresAuth: true } },
      { path: '/login', name: 'login', component: { template: '<div class="login"/>' } },
    ],
  })
}

describe('App shell switching', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('公开路由(/login)：无壳，不渲染顶栏/侧栏', async () => {
    const router = makeRouter()
    await router.push('/login')
    await router.isReady()
    const w = mount(App, { global: { plugins: [ElementPlus, i18n, router] } })
    expect(w.find('.app-topbar').exists()).toBe(false)
    expect(w.find('.app-aside').exists()).toBe(false)
    expect(w.find('.login').exists()).toBe(true)
  })

  it('业务路由(/)：渲染完整外壳（顶栏+侧栏）', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(App, { global: { plugins: [ElementPlus, i18n, router] } })
    expect(w.find('.app-topbar').exists()).toBe(true)
    expect(w.find('.app-aside').exists()).toBe(true)
  })
})
