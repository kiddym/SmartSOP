import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBillingStore } from '@/store/billing'

// 验证「按 feature 判断菜单项是否锁定」的纯逻辑。
// AppSidebar 用 billing.hasFeature 决定 locked；此处测该判定接线。
describe('sidebar feature lock', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('free 档下高级模块判为 locked', () => {
    const billing = useBillingStore()
    billing.subscription = {
      plan: 'free',
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 3,
      features: [],
      catalog: [],
    }
    expect(billing.hasFeature('meters')).toBe(false)
    expect(billing.hasFeature('analytics')).toBe(false)
  })

  it('pro 档下高级模块解锁', () => {
    const billing = useBillingStore()
    billing.subscription = {
      plan: 'pro',
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 15,
      features: ['meters', 'analytics', 'preventive_maintenance', 'purchasing', 'sop'],
      catalog: [],
    }
    expect(billing.hasFeature('meters')).toBe(true)
    expect(billing.hasFeature('purchasing')).toBe(true)
  })
})
