import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import PartsHubView from '@/views/inventory/PartsHubView.vue'

// 子视图依赖大量 api；用 stub 隔离，只验 Hub 的 tab/路由编排。
vi.mock('@/views/inventory/PartsView.vue', () => ({
  default: { name: 'PartsView', props: ['embedded'], template: '<div class="stub-parts" />' },
}))
vi.mock('@/views/inventory/MultiPartsView.vue', () => ({
  default: { name: 'MultiPartsView', props: ['embedded'], template: '<div class="stub-kits" />' },
}))

function makeRouter(path: string): Router {
  return createRouter({
    history: createMemoryHistory(path),
    routes: [
      { path: '/inventory/parts', name: 'inventory-parts', component: PartsHubView },
      { path: '/inventory/parts/kits', name: 'inventory-multi-parts', component: PartsHubView },
    ],
  })
}

async function mountHub(path: string) {
  setActivePinia(createPinia())
  const router = makeRouter(path)
  await router.push(path)
  await router.isReady()
  return { w: mount(PartsHubView, { global: { plugins: [router] } }), router }
}

describe('PartsHubView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('两个 tab：备件库存 / 多备件套件', async () => {
    const { w } = await mountHub('/inventory/parts')
    expect(w.text()).toContain('备件库存')
    expect(w.text()).toContain('多备件套件')
  })

  it('/inventory/parts 激活备件 tab，渲染 PartsView(embedded)', async () => {
    const { w } = await mountHub('/inventory/parts')
    expect(w.find('.stub-parts').exists()).toBe(true)
  })

  it('/inventory/parts/kits 激活套件 tab，渲染 MultiPartsView(embedded)', async () => {
    const { w } = await mountHub('/inventory/parts/kits')
    expect(w.find('.stub-kits').exists()).toBe(true)
  })

  it('切到套件 tab 时 push 到 /inventory/parts/kits', async () => {
    const { w, router } = await mountHub('/inventory/parts')
    const kitsTab = w.findAll('.el-tabs__item').find((t) => t.text().includes('多备件套件'))!
    await kitsTab.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/inventory/parts/kits')
  })
})
