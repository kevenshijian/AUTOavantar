import { createApp } from 'vue'
import router from './router'
import pinia from './stores'
import App from './App.vue'
import './assets/styles/main.css'

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 全局页面可见性处理
// 在页面不可见时添加 CSS 类，暂停所有动画
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    document.body.classList.add('page-hidden')
    console.log('[Main] 页面进入后台，暂停动画')
  } else {
    document.body.classList.remove('page-hidden')
    console.log('[Main] 页面重新可见，恢复动画')
  }
})

app.mount('#app')
