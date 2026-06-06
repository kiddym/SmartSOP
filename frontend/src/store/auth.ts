import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import * as authStorage from '@/utils/authStorage'
import type { CurrentUser, LoginPayload, RegisterPayload } from '@/types/auth'

interface State {
  user: CurrentUser | null
  loading: boolean
  _bootstrapPromise: Promise<void> | null
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({
    user: null,
    loading: false,
    _bootstrapPromise: null,
  }),

  getters: {
    isAuthenticated: (s): boolean => s.user !== null,
    roleCode: (s): string | null => s.user?.role_code ?? null,
    permissionCodes: (s): string[] => s.user?.permissions ?? [],
    hasPermission(): (code: string) => boolean {
      const role = this.user?.role_code
      const codes = this.user?.permissions ?? []
      return (code: string): boolean => role === 'super_admin' || codes.includes(code)
    },
  },

  actions: {
    async login(payload: LoginPayload): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.login(payload)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },

    async register(payload: RegisterPayload): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.register(payload)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },

    async acceptInvite(token: string, name: string, password: string): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.acceptInvite(token, name, password)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },

    async loadMe(): Promise<void> {
      this.user = await authApi.fetchMe()
      // 加载公司订阅供 feature 门控（失败不阻塞登录）。
      // 动态 import 避免 store 间循环依赖。
      try {
        const { useBillingStore } = await import('./billing')
        await useBillingStore().loadSubscription()
      } catch {
        // 订阅加载失败不阻断主流程
      }
      // 加载公司设置供导航模块显隐（失败不阻塞登录；失败时侧栏降级为全部显示）。
      try {
        const { useCompanySettingsStore } = await import('./companySettings')
        await useCompanySettingsStore().loadSettings()
      } catch {
        // 公司设置加载失败不阻断主流程
      }
    },

    logout(): void {
      authStorage.clearTokens()
      this.user = null
      this._bootstrapPromise = null
      void import('./notifications').then(({ useNotificationStore }) => {
        const n = useNotificationStore()
        n.stopPolling()
        n.$reset()
      })
    },

    bootstrap(): Promise<void> {
      if (this._bootstrapPromise) return this._bootstrapPromise
      this._bootstrapPromise = this._doBootstrap()
      return this._bootstrapPromise
    },

    async _doBootstrap(): Promise<void> {
      const refreshToken = authStorage.getRefreshToken()
      if (!refreshToken) return
      try {
        const pair = await authApi.refresh(refreshToken)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } catch {
        authStorage.clearTokens()
        this.user = null
      }
    },

    _applyTokens(access: string, refresh: string): void {
      authStorage.setAccessToken(access)
      authStorage.setRefreshToken(refresh)
    },
  },
})
