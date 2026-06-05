import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  getSubscription: vi.fn(),
  createCheckoutSession: vi.fn(),
  createPortalSession: vi.fn(),
}))
vi.mock('@/api/billing', () => api)

import { useBillingStore } from '@/store/billing'

const MOCK_FREE = {
  plan: 'free',
  subscription_status: 'active',
  seat_used: 1,
  seat_limit: 3,
  features: [],
  catalog: [
    { plan: 'free', seat_limit: 3, features: [] },
    { plan: 'pro', seat_limit: 15, features: ['meters', 'analytics'] },
    { plan: 'enterprise', seat_limit: null, features: ['meters', 'analytics'] },
  ],
}

describe('useBillingStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getSubscription.mockReset().mockResolvedValue(MOCK_FREE)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('loadSubscription 拉取并存订阅', async () => {
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.subscription).toEqual(MOCK_FREE)
  })

  it('hasFeature 按 features 集合判定', async () => {
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.hasFeature('meters')).toBe(false) // free 未解锁
  })

  it('hasFeature 在 pro 下解锁', async () => {
    api.getSubscription.mockResolvedValue({
      ...MOCK_FREE,
      plan: 'pro',
      features: ['meters', 'analytics'],
    })
    const store = useBillingStore()
    await store.loadSubscription()
    expect(store.hasFeature('meters')).toBe(true)
    expect(store.hasFeature('sop')).toBe(false)
  })

  it('未加载时 hasFeature 返回 false（安全默认）', () => {
    const store = useBillingStore()
    expect(store.hasFeature('meters')).toBe(false)
  })

  it('startCheckout 跳转到返回的 url', async () => {
    api.createCheckoutSession.mockResolvedValue({ url: 'https://checkout/x' })
    const assign = vi.fn()
    vi.stubGlobal('window', { ...window, location: { assign } })
    const store = useBillingStore()
    await store.startCheckout()
    expect(assign).toHaveBeenCalledWith('https://checkout/x')
  })

  it('openPortal 跳转到门户 url', async () => {
    api.createPortalSession.mockResolvedValue({ url: 'https://portal/p' })
    const assign = vi.fn()
    vi.stubGlobal('window', { ...window, location: { assign } })
    const store = useBillingStore()
    await store.openPortal()
    expect(assign).toHaveBeenCalledWith('https://portal/p')
  })

  it('pollUntilPlanChange 在 plan 翻新后停止', async () => {
    let plan = 'free'
    api.getSubscription.mockImplementation(async () => ({
      plan,
      subscription_status: 'active',
      seat_used: 1,
      seat_limit: 3,
      features: [],
      catalog: [],
    }))
    const store = useBillingStore()
    await store.loadSubscription()
    setTimeout(() => {
      plan = 'pro'
    }, 0)
    const result = await store.pollUntilPlanChange('free', 5, 1)
    expect(result).toBe(true)
    expect(store.subscription?.plan).toBe('pro')
  })

  it('pollUntilPlanChange 耗尽返回 false', async () => {
    api.getSubscription.mockResolvedValue({
      ...MOCK_FREE,
      plan: 'free',
    })
    const store = useBillingStore()
    await store.loadSubscription()
    const result = await store.pollUntilPlanChange('free', 2, 1)
    expect(result).toBe(false)
  })
})
