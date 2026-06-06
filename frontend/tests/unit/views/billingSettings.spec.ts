import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  getSubscription: vi.fn(),
  createPortalSession: vi.fn(),
  createCheckoutSession: vi.fn(),
}))
vi.mock('@/api/billing', () => api)
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/composables/usePermission', () => ({
  usePermission: () => ({ hasPermission: () => false }),
}))

import SettingsView from '@/views/billing/SettingsView.vue'

const SUB = {
  plan: 'pro',
  subscription_status: 'active',
  seat_used: 4,
  seat_limit: 15,
  features: ['meters', 'analytics'],
  catalog: [],
}

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getSubscription.mockReset().mockResolvedValue(SUB)
  })

  it('展示当前档位与座席用量', async () => {
    // el-card/el-tag 用渲染插槽的 stub，否则卡片内文本（pro/座席）不会出现在 text()。
    const slotStub = { template: '<div><slot /></div>' }
    const wrapper = mount(SettingsView, {
      global: {
        stubs: {
          'el-progress': true,
          'el-tag': slotStub,
          'el-card': slotStub,
          'router-link': slotStub,
        },
      },
    })
    await vi.waitFor(() => expect(api.getSubscription).toHaveBeenCalled())
    await wrapper.vm.$nextTick()
    // 套餐 / 功能码已中文化展示（pro → 专业版，feature key → 中文名）。
    expect(wrapper.text()).toContain('专业版')
    expect(wrapper.text()).toContain('计量')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('15')
  })
})
