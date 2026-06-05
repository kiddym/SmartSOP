import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PlansView from '@/views/billing/PlansView.vue'
import { useBillingStore } from '@/store/billing'

vi.mock('@/composables/usePermission', () => ({
  usePermission: () => ({ hasPermission: () => true }),
}))

const slot = { template: '<div><slot /></div>' }

describe('PlansView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('pro 卡片对有权用户显示订阅按钮', async () => {
    const store = useBillingStore()
    store.subscription = {
      plan: 'free',
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 3,
      features: [],
      catalog: [
        { plan: 'free', seat_limit: 3, features: [] },
        { plan: 'pro', seat_limit: 15, features: ['meters'] },
      ],
    }
    const wrapper = mount(PlansView, {
      global: { stubs: { 'el-card': slot, 'el-tag': slot, 'el-button': slot } },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('订阅')
  })

  it('enterprise 卡片显示联系销售文案', async () => {
    const store = useBillingStore()
    store.subscription = {
      plan: 'free',
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 3,
      features: [],
      catalog: [
        { plan: 'free', seat_limit: 3, features: [] },
        { plan: 'enterprise', seat_limit: null, features: ['meters', 'analytics'] },
      ],
    }
    const wrapper = mount(PlansView, {
      global: { stubs: { 'el-card': slot, 'el-tag': slot, 'el-button': slot } },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('联系销售')
  })
})
