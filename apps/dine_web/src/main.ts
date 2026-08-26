import '@fontsource/noto-serif-sc/600.css'
import '@fontsource/noto-serif-sc/700.css'

import naive from 'naive-ui'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

import './styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
// 主题覆盖统一在 App.vue 的 NConfigProvider 中声明
app.use(naive)

app.mount('#app')
