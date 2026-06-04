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
  },
})
