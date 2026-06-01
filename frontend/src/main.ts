import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
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
app.use(ElementPlus)
app.use(i18n)

app.mount('#app')
