import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
// 样式引入顺序（关键）：EP 基样式 → EP 暗模式 css-vars → tokens(令牌+html.dark 覆盖+.paper)
// → fonts(@font-face 自托管 Space Grotesk/DM Sans) → element-overrides(把 --el-* 重映射到令牌，
// 须在 EP 暗 css-vars 之后) → main.css。
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './assets/styles/tokens.css'
import './assets/styles/fonts.css'
import './assets/styles/element-overrides.css'
import './assets/styles/main.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
useThemeStore(pinia).bootstrap() // 读主题偏好并在 mount 前应用 dark class（防 FOUC）
void useAuthStore(pinia).bootstrap() // 预热（不阻塞 mount；守卫会 await 同一 Promise）
app.use(router)
app.use(ElementPlus, { locale: zhCn }) // EP 内置组件文案中文化（el-table 空态/分页/日期选择等）
app.use(i18n)

app.mount('#app')
