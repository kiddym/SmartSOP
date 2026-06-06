import { defineStore } from 'pinia'

import { getCompanySettings } from '@/api/companySettings'
import type { CompanySettings } from '@/types/platform'

interface State {
  settings: CompanySettings | null
  loading: boolean
}

// 公司设置轻量缓存：供侧栏读取导航模块显隐开关。
// 设计原则：未加载 / 加载失败 → settings=null，显隐 getter 一律返回 true（降级为"全部显示"），
// 绝不因设置加载失败而隐藏导航。
export const useCompanySettingsStore = defineStore('companySettings', {
  state: (): State => ({ settings: null, loading: false }),
  getters: {
    // 某显隐开关是否为"显示"。未知（未加载/失败）时默认显示。
    isModuleVisible(): (key: keyof Pick<
      CompanySettings,
      'show_requests' | 'show_locations' | 'show_meters' | 'show_vendors_customers'
    >) => boolean {
      return (key) => this.settings?.[key] ?? true
    },
  },
  actions: {
    async loadSettings(): Promise<void> {
      this.loading = true
      try {
        this.settings = await getCompanySettings()
      } finally {
        this.loading = false
      }
    },
  },
})
