import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './assets/styles/tokens.css'
import './assets/styles/main.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useAuthStore } from '@/store/auth'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
void useAuthStore(pinia).bootstrap() // 预热（不阻塞 mount；守卫会 await 同一 Promise）
app.use(router)
app.use(ElementPlus, { locale: zhCn }) // EP 内置组件文案中文化（el-table 空态/分页/日期选择等）
app.use(i18n)

app.mount('#app')
