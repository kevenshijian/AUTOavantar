<template>
  <div id="app" :class="{ 'dark-theme': isDarkTheme }">
    <el-container class="layout-container">
      <!-- 主内容区 -->
      <el-container class="main-container">
        <!-- 顶部导航 -->
        <el-header class="header">
          <div class="header-left">
            <div class="logo" @click="toggleTheme" title="点击切换主题">
              <svg class="logo-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="40" height="40" rx="8" fill="url(#logoGrad)"/>
                <path d="M12 14L20 10L28 14V26L20 30L12 26V14Z" stroke="white" stroke-width="2" fill="none"/>
                <circle cx="20" cy="20" r="4" fill="white"/>
                <defs>
                  <linearGradient id="logoGrad" x1="0" y1="0" x2="40" y2="40">
                    <stop stop-color="#00d9ff"/>
                    <stop offset="1" stop-color="#00ff88"/>
                  </linearGradient>
                </defs>
              </svg>
              <span class="logo-text">AUTO<span class="highlight">Avantar</span></span>
            </div>
          </div>
          <div class="header-right">
            <!-- 动态导航按钮 -->
            <template v-if="currentRoute === 'Dashboard'">
              <el-button type="primary" plain @click="$router.push('/materials')">
                <el-icon><Collection /></el-icon>
                素材库
              </el-button>
              <el-button type="info" plain @click="$router.push('/settings')">
                <el-icon><Setting /></el-icon>
                设置
              </el-button>
            </template>
            
            <template v-else-if="currentRoute === 'Materials'">
              <el-button type="primary" plain @click="$router.push('/')">
                <el-icon><HomeFilled /></el-icon>
                主页
              </el-button>
              <el-button type="info" plain @click="$router.push('/settings')">
                <el-icon><Setting /></el-icon>
                设置
              </el-button>
            </template>
            
            <template v-else-if="currentRoute === 'Settings'">
              <el-button type="primary" plain @click="$router.push('/')">
                <el-icon><HomeFilled /></el-icon>
                主页
              </el-button>
              <el-button type="info" plain @click="$router.push('/materials')">
                <el-icon><Collection /></el-icon>
                素材库
              </el-button>
            </template>
            
            <template v-else>
              <!-- 其他页面显示主页和素材库 -->
              <el-button type="primary" plain @click="$router.push('/')">
                <el-icon><HomeFilled /></el-icon>
                主页
              </el-button>
              <el-button type="info" plain @click="$router.push('/materials')">
                <el-icon><Collection /></el-icon>
                素材库
              </el-button>
            </template>
            
            <!-- 主题切换图标 -->
            <el-button 
              circle 
              class="theme-toggle-btn"
              @click="toggleTheme"
              :title="isDarkTheme ? '切换到亮色主题' : '切换到暗色主题'"
            >
              <el-icon>
                <Sunny v-if="isDarkTheme" />
                <Moon v-else />
              </el-icon>
            </el-button>
            
            <el-badge :value="pendingTasks" class="task-badge" v-if="pendingTasks > 0">
              <el-icon size="20"><Bell /></el-icon>
            </el-badge>
          </div>
        </el-header>

        <!-- 内容区域 -->
        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade-transform" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>

        <!-- 页脚 -->
        <el-footer class="footer">
          <span>© 2025 AUTOavantar - 数字人视频生成系统</span>
        </el-footer>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { wsManager } from '@/utils/websocket'
import websocketService from '@/services/websocket'
import { ElMessage } from 'element-plus'
import { Collection, Setting, HomeFilled, Bell, Sunny, Moon } from '@element-plus/icons-vue'

const route = useRoute()
const taskStore = useTaskStore()

const pendingTasks = computed(() => taskStore.pendingCount)

const currentRoute = computed(() => {
  return route.name || ''
})

const isDarkTheme = ref(false)

const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)')

const savedTheme = localStorage.getItem('theme')
if (savedTheme) {
  isDarkTheme.value = savedTheme === 'dark'
} else {
  isDarkTheme.value = prefersDarkScheme.matches
}

const toggleTheme = () => {
  isDarkTheme.value = !isDarkTheme.value
  localStorage.setItem('theme', isDarkTheme.value ? 'dark' : 'light')
  console.log('Theme toggled to:', isDarkTheme.value ? 'dark' : 'light')
  console.log('Body classes:', document.body.className)
}

const checkThemeStatus = () => {
  console.log('Current isDarkTheme:', isDarkTheme.value)
  console.log('Body classes:', document.body.className)
  console.log('App element classes:', document.getElementById('app').className)
}

watch(isDarkTheme, (newValue) => {
  if (newValue) {
    document.body.classList.add('dark-theme')
    console.log('Body dark-theme class added')
  } else {
    document.body.classList.remove('dark-theme')
    console.log('Body dark-theme class removed')
  }
  console.log('Current body classes:', document.body.className)
}, { immediate: true })

provide('isDarkTheme', isDarkTheme)
provide('toggleTheme', toggleTheme)

let unsubscribeStatus = null
let unsubscribeCompleted = null
let unsubscribeFailed = null

const setupWebSocketListeners = () => {
  unsubscribeStatus = websocketService.onStatusUpdate((message) => {
    console.log('[App] 收到状态更新:', message)
    taskStore.updateTaskFromWebSocket(message)
  })

  unsubscribeCompleted = websocketService.onCompleted((message) => {
    console.log('[App] 任务完成:', message)
    taskStore.updateTaskFromWebSocket({
      task_id: message.task_id,
      status: 'completed',
      progress: 100,
      output_path: message.output_path
    })
    const task = taskStore.tasks.find(t => t.task_id === message.task_id)
    ElMessage.success(`任务 ${task?.name || message.task_id} 已完成`)
  })

  unsubscribeFailed = websocketService.onFailed((message) => {
    console.log('[App] 任务失败:', message)
    taskStore.updateTaskFromWebSocket({
      task_id: message.task_id,
      status: 'failed',
      error_message: message.error_message || message.message
    })
    const task = taskStore.tasks.find(t => t.task_id === message.task_id)
    ElMessage.error(`任务 ${task?.name || message.task_id} 失败`)
  })
}

const connectToRunningTasks = async () => {
  const runningTasks = taskStore.tasks.filter(t => 
    ['pending', 'processing', 'running', 'queued'].includes(t.status)
  )
  
  console.log('[App] 连接运行中的任务:', runningTasks.map(t => t.task_id))
  
  for (const task of runningTasks) {
    try {
      await websocketService.connect(task.task_id)
      console.log(`[App] 已连接任务 ${task.task_id}`)
    } catch (error) {
      console.error(`[App] 连接任务 ${task.task_id} WebSocket 失败:`, error)
    }
  }
}

onMounted(async () => {
  prefersDarkScheme.addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      isDarkTheme.value = e.matches
    }
  })

  // 初始化 WebSocket 可见性处理器
  websocketService.initVisibilityHandler()

  setupWebSocketListeners()

  await taskStore.fetchTasks()

  await connectToRunningTasks()

  taskStore.startPolling()

  console.log('[App] WebSocket 监听器已设置')
})

onUnmounted(() => {
  if (unsubscribeStatus) unsubscribeStatus()
  if (unsubscribeCompleted) unsubscribeCompleted()
  if (unsubscribeFailed) unsubscribeFailed()
  
  taskStore.stopPolling()
  
  console.log('[App] 组件卸载，但保持 WebSocket 连接')
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}

.logo {
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: opacity 0.3s;
}

.logo:hover {
  opacity: 0.8;
}

.logo-icon {
  width: 40px;
  height: 40px;
  margin-right: 12px;
}

.logo-text {
  color: #303133;
  font-size: 20px;
  font-weight: 600;
  white-space: nowrap;
}

.logo-text .highlight {
  background: linear-gradient(135deg, #00d9ff 0%, #00ff88 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.main-container {
  background-color: #f5f7fa;
  transition: background-color 0.3s ease;
}

.header {
  background-color: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 30px;
  height: 64px;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.theme-toggle-btn {
  margin-left: 10px;
}

.task-badge {
  cursor: pointer;
  margin-left: 10px;
}

.main-content {
  padding: 20px;
  overflow-y: auto;
  min-height: calc(100vh - 64px - 40px);
}

.footer {
  background-color: #fff;
  text-align: center;
  color: #909399;
  font-size: 12px;
  line-height: 40px;
  border-top: 1px solid #e4e7ed;
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

/* 暗色主题样式 */
.dark-theme .main-container {
  background-color: #0d1117;
}

.dark-theme .header {
  background-color: #161b22;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.dark-theme .logo-text {
  color: #e6edf3;
}

.dark-theme .footer {
  background-color: #161b22;
  color: #8b949e;
  border-top-color: #30363d;
}

/* 暗色主题下的Element Plus对话框样式 */
body.dark-theme .el-dialog {
  background: #1a1f26 !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.8) !important;
}

body.dark-theme .el-dialog__header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
  background: #1a1f26 !important;
}

body.dark-theme .el-dialog__title {
  color: #fff !important;
}

body.dark-theme .el-dialog__body {
  background: #1a1f26 !important;
  color: rgba(255, 255, 255, 0.8) !important;
}

body.dark-theme .el-dialog__footer {
  border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
  background: #1a1f26 !important;
}

/* 路由过渡动画 */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s ease;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>

<!-- 全局样式 -->
<style>
/* 暗色主题下的Element Plus对话框样式 - 全局 */
body.dark-theme .el-dialog {
  background: #1a1f26 !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.8) !important;
}

body.dark-theme .el-dialog__header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
  background: #1a1f26 !important;
}

body.dark-theme .el-dialog__title {
  color: #fff !important;
}

body.dark-theme .el-dialog__body {
  background: #1a1f26 !important;
  color: rgba(255, 255, 255, 0.8) !important;
}

body.dark-theme .el-dialog__footer {
  border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
  background: #1a1f26 !important;
}
</style>
