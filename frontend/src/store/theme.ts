import { defineStore } from 'pinia'

// 主题：默认暗（design-system.md 定义的产品本色），可一键切浅并持久化。
// 暗/浅两套令牌值挂在 tokens.css 的 :root（浅）与 html.dark（暗）；
// Element Plus 暗模式 css-vars 与 element-overrides.css 同样以 html.dark 为开关。
// 故切换只需 toggle <html> 的 dark class，壳层组件（已全部走 var()）零改动。

const STORAGE_KEY = 'theme'

interface State {
  isDark: boolean
}

// 把主题写到 <html class="dark">（所有暗色规则的统一开关）。
function applyClass(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark)
}

export const useThemeStore = defineStore('theme', {
  state: (): State => ({ isDark: true }),
  actions: {
    // 启动读偏好：仅当用户显式选过 'light' 才切浅，否则保持默认暗。
    bootstrap(): void {
      this.isDark = localStorage.getItem(STORAGE_KEY) !== 'light'
      applyClass(this.isDark)
    },
    setDark(value: boolean): void {
      this.isDark = value
      localStorage.setItem(STORAGE_KEY, value ? 'dark' : 'light')
      applyClass(value)
    },
    toggle(): void {
      this.setDark(!this.isDark)
    },
  },
})
