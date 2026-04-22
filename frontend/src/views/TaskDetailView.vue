<template>
  <div class="task-detail-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="$router.push('/')">
          <el-icon><ArrowLeft /></el-icon>
          返回主页
        </el-button>
        <h2>{{ task.name || '任务详情' }}</h2>
        <el-tag :type="getStatusType(task.status)" size="large" effect="dark">
          {{ getStatusText(task.status) }}
        </el-tag>
      </div>
      <div class="header-actions">
        <template v-if="task.status === 'processing' || task.status === 'pending'">
          <el-button type="warning" @click="pauseTask">
            <el-icon><VideoPause /></el-icon>
            暂停
          </el-button>
        </template>
        <template v-if="task.status === 'paused'">
          <el-button type="success" @click="resumeTask">
            <el-icon><VideoPlay /></el-icon>
            恢复
          </el-button>
        </template>
        <template v-if="task.status === 'failed'">
          <el-button type="primary" @click="retryTask">
            <el-icon><RefreshRight /></el-icon>
            重试
          </el-button>
        </template>
        <el-button type="danger" plain @click="deleteTask">
          <el-icon><Delete /></el-icon>
          删除
        </el-button>
      </div>
    </div>

    <el-row :gutter="24">
      <!-- 左侧：进度和日志 -->
      <el-col :xs="24" :lg="16">
        <!-- 进度卡片 -->
        <el-card class="progress-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>处理进度</span>
              <el-tag v-if="wsConnected" type="success" size="small">
                <el-icon><Connection /></el-icon>
                实时连接
              </el-tag>
              <el-tag v-else type="info" size="small">
                <el-icon><Connection /></el-icon>
                离线
              </el-tag>
            </div>
          </template>

          <div class="progress-section">
            <el-progress 
              :percentage="Math.round(task.progress)"
              :status="task.status === 'failed' ? 'exception' : ''"
              :stroke-width="24"
              striped
              striped-flow
              :duration="task.status === 'processing' ? 2 : 0"
            />
            <div class="progress-info">
              <span class="stage">{{ task.current_stage || '等待开始' }}</span>
              <span class="percentage">{{ Math.round(task.progress) }}%</span>
            </div>
          </div>

          <!-- 处理步骤 -->
          <el-steps :active="currentStep" finish-status="success" class="process-steps">
            <el-step title="预处理" description="视频预处理" />
            <el-step title="文案生成" description="LLM生成文案" />
            <el-step title="语音合成" description="TTS语音合成" />
            <el-step title="视频生成" description="HeyGem生成" />
            <el-step title="后期处理" description="字幕/BGM合成" />
          </el-steps>
        </el-card>

        <!-- 日志输出 -->
        <el-card class="log-card" shadow="hover" style="margin-top: 20px;">
          <template #header>
            <div class="card-header">
              <span>执行日志</span>
              <div>
                <el-button text size="small" @click="clearLogs">
                  <el-icon><Delete /></el-icon>
                  清空
                </el-button>
                <el-button text size="small" @click="refreshLogs">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
            </div>
          </template>

          <div class="log-container" ref="logContainer">
            <div 
              v-for="(log, index) in logs" 
              :key="index"
              class="log-line"
              :class="log.type"
            >
              <span class="log-time">[{{ log.time }}]</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
            <div v-if="logs.length === 0" class="log-empty">
              暂无日志
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：任务信息 -->
      <el-col :xs="24" :lg="8">
        <!-- 基本信息 -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>基本信息</span>
            </div>
          </template>

          <div class="info-list">
            <div class="info-item">
              <span class="label">任务ID</span>
              <span class="value">{{ task.task_id }}</span>
            </div>
            <div class="info-item">
              <span class="label">创建时间</span>
              <span class="value">{{ formatDate(task.created_at) }}</span>
            </div>
            <div class="info-item">
              <span class="label">更新时间</span>
              <span class="value">{{ formatDate(task.updated_at) }}</span>
            </div>
            <div class="info-item" v-if="task.completed_at">
              <span class="label">完成时间</span>
              <span class="value">{{ formatDate(task.completed_at) }}</span>
            </div>
            <div class="info-item" v-if="task.error_message">
              <span class="label">错误信息</span>
              <span class="value error">{{ task.error_message }}</span>
            </div>
          </div>
        </el-card>

        <!-- 配置信息 -->
        <el-card class="config-card" shadow="hover" style="margin-top: 20px;">
          <template #header>
            <div class="card-header">
              <span>配置参数</span>
            </div>
          </template>

          <div class="config-list">
            <div class="config-item">
              <span class="label">文案模式</span>
              <el-tag size="small" :type="task.use_llm_generate ? 'success' : 'info'">
                {{ task.use_llm_generate ? 'AI生成' : '手动输入' }}
              </el-tag>
            </div>
            <div class="config-item">
              <span class="label">语速</span>
              <span class="value">{{ task.tts_speed }}x</span>
            </div>
            <div class="config-item">
              <span class="label">情感权重</span>
              <span class="value">{{ task.tts_emo_weight }}</span>
            </div>
            <div class="config-item">
              <span class="label">字幕</span>
              <el-tag size="small" :type="task.enable_subtitle ? 'success' : 'info'">
                {{ task.enable_subtitle ? '启用' : '禁用' }}
              </el-tag>
            </div>
            <div class="config-item">
              <span class="label">BGM</span>
              <el-tag size="small" :type="task.enable_bgm ? 'success' : 'info'">
                {{ task.enable_bgm ? '启用' : '禁用' }}
              </el-tag>
            </div>
            <div class="config-item" v-if="task.enable_bgm">
              <span class="label">BGM音量</span>
              <span class="value">{{ Math.round(task.bgm_volume * 100) }}%</span>
            </div>
            <div class="config-item">
              <span class="label">降噪</span>
              <el-tag size="small" :type="task.enable_denoise ? 'success' : 'info'">
                {{ task.enable_denoise ? '启用' : '禁用' }}
              </el-tag>
            </div>
          </div>
        </el-card>

        <!-- 输出文件 -->
        <el-card class="output-card" shadow="hover" style="margin-top: 20px;" v-if="task.output_path">
          <template #header>
            <div class="card-header">
              <span>输出文件</span>
            </div>
          </template>

          <div class="output-section">
            <video 
              v-if="task.output_path"
              :src="getFileUrl(task.output_path)" 
              controls
              class="output-video"
            />
            <div class="output-actions">
              <el-button type="primary" @click="downloadOutput">
                <el-icon><Download /></el-icon>
                下载视频
              </el-button>
              <el-button @click="copyLink">
                <el-icon><Link /></el-icon>
                复制链接
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import websocketService from '@/services/websocket'
import { taskApi } from '@/services/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

const taskId = computed(() => route.params.id)
const task = ref({})
const logs = ref([])
const wsConnected = ref(false)
const logContainer = ref(null)
const unsubscribeCallbacks = ref([])

// 当前步骤索引
const currentStep = computed(() => {
  const stageMap = {
    'preprocessing': 0,
    'script_generating': 1,
    'tts_synthesizing': 2,
    'heygem_generating': 3,
    'post_processing': 4
  }
  return stageMap[task.value.current_stage] ?? 0
})

// 状态类型映射
const getStatusType = (status) => {
  const map = {
    'pending': 'info',
    'processing': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'paused': 'info',
    'cancelled': 'info'
  }
  return map[status] || 'info'
}

// 状态文本映射
const getStatusText = (status) => {
  const map = {
    'pending': '等待中',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败',
    'paused': '已暂停',
    'cancelled': '已取消'
  }
  return map[status] || status
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 获取文件URL
const getFileUrl = (path) => {
  if (!path) return ''
  return `/files/${path}`
}

// 添加日志
const addLog = (message, type = 'info') => {
  const time = new Date().toLocaleTimeString('zh-CN')
  logs.value.push({ time, message, type })
  
  // 自动滚动到底部
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
  
  // 限制日志数量
  if (logs.value.length > 500) {
    logs.value = logs.value.slice(-500)
  }
}

// 清空日志
const clearLogs = () => {
  logs.value = []
}

// 刷新日志
const refreshLogs = async () => {
  try {
    const response = await taskApi.getLogs(taskId.value)
    if (response.data) {
      logs.value = response.data.logs.map(log => ({
        time: new Date().toLocaleTimeString('zh-CN'),
        message: log,
        type: 'info'
      }))
    }
  } catch (error) {
    ElMessage.error('获取日志失败')
  }
}

// 加载任务详情
const loadTask = async () => {
  try {
    const response = await taskApi.get(taskId.value)
    task.value = response.data
  } catch (error) {
    ElMessage.error('加载任务详情失败')
  }
}

// 连接WebSocket
const connectWebSocket = async () => {
  try {
    await websocketService.connect(taskId.value)
    wsConnected.value = true
    addLog('WebSocket 连接成功', 'success')
    
    // 订阅状态更新
    const unsubscribeStatus = websocketService.onStatusUpdate((message) => {
      task.value.status = message.status
      task.value.progress = message.progress
      task.value.current_stage = message.stage
      addLog(`[${message.status}] ${message.message || message.stage}`)
      
      // 任务完成
      if (message.status === 'completed') {
        task.value.output_path = message.output_path
        addLog('任务完成！', 'success')
        loadTask() // 刷新完整信息
      }
      
      // 任务失败
      if (message.status === 'failed') {
        task.value.error_message = message.message
        addLog(`任务失败: ${message.message}`, 'error')
      }
    })
    
    unsubscribeCallbacks.value.push(unsubscribeStatus)
  } catch (error) {
    wsConnected.value = false
    addLog('WebSocket 连接失败', 'error')
  }
}

// 暂停任务
const pauseTask = async () => {
  try {
    await taskApi.control(taskId.value, 'pause')
    ElMessage.success('任务已暂停')
  } catch (error) {
    ElMessage.error('暂停失败')
  }
}

// 恢复任务
const resumeTask = async () => {
  try {
    await taskApi.control(taskId.value, 'resume')
    ElMessage.success('任务已恢复')
  } catch (error) {
    ElMessage.error('恢复失败')
  }
}

// 重试任务
const retryTask = async () => {
  try {
    await taskApi.control(taskId.value, 'retry')
    ElMessage.success('任务已重试')
    clearLogs()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

// 删除任务
const deleteTask = async () => {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？', '提示', {
      type: 'warning'
    })
    
    await taskApi.delete(taskId.value)
    ElMessage.success('删除成功')
    router.push('/')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 下载输出
const downloadOutput = () => {
  if (task.value.output_path) {
    const url = getFileUrl(task.value.output_path)
    const link = document.createElement('a')
    link.href = url
    link.download = task.value.output_path.split('/').pop() || 'video.mp4'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// 复制链接
const copyLink = () => {
  const url = window.location.origin + getFileUrl(task.value.output_path)
  navigator.clipboard.writeText(url).then(() => {
    ElMessage.success('链接已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// 初始化
onMounted(async () => {
  await loadTask()
  await connectWebSocket()
  await refreshLogs()
})

// 清理
onUnmounted(() => {
  unsubscribeCallbacks.value.forEach(unsubscribe => unsubscribe())
  websocketService.disconnect()
})

// 监听任务ID变化
watch(taskId, async () => {
  websocketService.disconnect()
  unsubscribeCallbacks.value = []
  await loadTask()
  await connectWebSocket()
})
</script>

<style scoped>
.task-detail-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
  font-size: 24px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-section {
  padding: 20px 0;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}

.stage {
  font-size: 14px;
  color: #606266;
}

.percentage {
  font-size: 14px;
  font-weight: bold;
  color: #409EFF;
}

.process-steps {
  margin-top: 30px;
}

.log-container {
  height: 400px;
  overflow-y: auto;
  background-color: #1e1e1e;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.log-line {
  padding: 4px 0;
  line-height: 1.6;
}

.log-line.info {
  color: #d4d4d4;
}

.log-line.success {
  color: #4ec9b0;
}

.log-line.error {
  color: #f48771;
}

.log-line.warning {
  color: #dcdcaa;
}

.log-time {
  color: #858585;
  margin-right: 8px;
}

.log-message {
  word-break: break-all;
}

.log-empty {
  color: #666;
  text-align: center;
  padding: 40px;
}

.info-list,
.config-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item,
.config-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-item .label,
.config-item .label {
  color: #909399;
  font-size: 14px;
}

.info-item .value,
.config-item .value {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}

.info-item .value.error {
  color: #f56c6c;
}

.output-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.output-video {
  width: 100%;
  border-radius: 8px;
  background-color: #000;
}

.output-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
