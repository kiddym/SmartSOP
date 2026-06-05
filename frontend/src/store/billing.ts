import { defineStore } from 'pinia'

import * as billingApi from '@/api/billing'
import type { Subscription } from '@/api/billing'

interface State {
  subscription: Subscription | null
  loading: boolean
}

export const useBillingStore = defineStore('billing', {
  state: (): State => ({ subscription: null, loading: false }),
  getters: {
    // feature 未加载时返回 false（安全默认：未知即锁）
    hasFeature(): (feature: string) => boolean {
      return (feature: string) => this.subscription?.features.includes(feature) ?? false
    },
    planName(): string {
      return this.subscription?.plan ?? 'free'
    },
  },
  actions: {
    async loadSubscription(): Promise<void> {
      this.loading = true
      try {
        this.subscription = await billingApi.getSubscription()
      } finally {
        this.loading = false
      }
    },
    async startCheckout(): Promise<void> {
      const { url } = await billingApi.createCheckoutSession()
      window.location.assign(url)
    },
    async openPortal(): Promise<void> {
      const { url } = await billingApi.createPortalSession()
      window.location.assign(url)
    },
    /** checkout 返回后轮询订阅直到 plan 翻新（webhook 异步）。
     * 返回 true 表示 plan 已变更，false 表示耗尽未变更。
     */
    async pollUntilPlanChange(prevPlan: string, maxTries = 8, intervalMs = 1500): Promise<boolean> {
      for (let i = 0; i < maxTries; i++) {
        await this.loadSubscription()
        if (this.subscription && this.subscription.plan !== prevPlan) return true
        await new Promise((res) => setTimeout(res, intervalMs))
      }
      return false
    },
  },
})
