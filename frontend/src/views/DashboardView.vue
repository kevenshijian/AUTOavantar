<template>
  <div class="dashboard-container" :class="{ 'dark-theme': isDarkTheme }">
    <div class="dashboard-content">
      <div class="section-top">
        <div class="action-panel">
          <el-card class="action-card" shadow="hover" @click="createTask">
            <div class="action-icon new">
              <el-icon><Plus /></el-icon>
            </div>
            <div class="action-text">
              <h3>新建任务</h3>
              <p>创建数字人视频生成任务</p>
            </div>
            <div class="action-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </el-card>
          
          <el-card class="action-card run" shadow="hover" @click="runAllPending">
            <div class="action-icon running">
              <el-icon><VideoPlay /></el-icon>
            </div>
            <div class="action-text">
              <h3>运行任务</h3>
              <p>执行所有等待中的任务</p>
            </div>
            <div class="action-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </el-card>
        </div>

        <div class="pending-panel">
          <div class="panel-header">
            <h4><el-icon><Clock /></el-icon> 等待运行</h4>
            <span class="count-badge">{{ pendingTasks.length }}</span>
          </div>
          <div class="task-list" v-if="pendingTasks.length > 0">
            <div 
              v-for="task in pendingTasks" 
              :key="task.task_id"
              class="task-item"
            >
              <div class="task-info">
                <span class="task-name">{{ task.name }}</span>
                <span class="task-time">{{ formatTime(task.created_at) }}</span>
              </div>
              <div class="task-actions">
                <el-button type="success" size="small" @click="startTask(task)">
                  <el-icon><VideoPlay /></el-icon>
                  开始
                </el-button>
                <el-button type="danger" size="small" plain @click="deleteTask(task)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无等待任务" :image-size="60" />
        </div>
      </div>

      <div class="section-middle" v-if="activeTasks.length > 0">
        <div class="panel-header">
          <h4><el-icon class="pulse"><Loading /></el-icon> 运行中</h4>
          <span class="count-badge running">{{ activeTasks.length }}</span>
        </div>
        <div class="running-grid">
          <div 
            v-for="task in activeTasks" 
            :key="task.task_id"
            class="running-card"
            :class="{ 'queued-card': task.status === 'queued' }"
          >
            <div class="running-header">
              <span class="task-name">{{ task.name }}</span>
              <el-tag size="small" :type="task.status === 'queued' ? 'info' : 'warning'" effect="dark">
                {{ task.status === 'queued' ? '等待中' : (task.current_stage || '处理中') }}
              </el-tag>
            </div>
            <div class="progress-section" v-if="task.status !== 'queued'">
              <el-progress 
                :percentage="Math.round(task.progress || 0)"
                :stroke-width="8"
                :striped="true"
                :striped-flow="true"
                status="success"
              />
              <span class="progress-text">{{ Math.round(task.progress || 0) }}%</span>
            </div>
            <div class="queued-info" v-else>
              <span class="queued-text">任务已提交，等待执行...</span>
            </div>
            <div class="running-actions">
              <el-button type="danger" size="small" plain @click="cancelTask(task)">
                <el-icon><Close /></el-icon>
                取消
              </el-button>
              <el-button type="primary" size="small" plain @click="priorityTask(task)" v-if="task.status === 'queued'">
                <el-icon><Top /></el-icon>
                插队
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="section-bottom">
        <div class="panel-header">
          <h4><el-icon><CircleCheck /></el-icon> 已完成任务</h4>
          <span class="count-badge completed">{{ completedTasks.length }}</span>
        </div>
        <div class="completed-grid" v-if="completedTasks.length > 0">
          <div 
            v-for="task in completedTasks" 
            :key="task.task_id"
            class="completed-card"
            :class="{ 'has-error': task.status === 'failed' }"
          >
            <div class="card-thumbnail">
              <video v-if="task.output_path && task.status !== 'failed'" :src="getVideoUrl(task.output_path)" muted @mouseenter="hoverVideo" @mouseleave="leaveVideo" />
              <div v-else class="error-placeholder">
                <el-icon><Warning /></el-icon>
                <span>生成失败</span>
              </div>
              <div class="card-overlay">
                <el-button type="primary" circle @click="previewTask(task)">
                  <el-icon><VideoPlay /></el-icon>
                </el-button>
              </div>
            </div>
            <div class="card-info">
              <span class="card-name">{{ task.name }}</span>
              <div class="card-meta">
                <el-tag v-if="task.status === 'completed'" size="small" type="success">已完成</el-tag>
                <el-tag v-else size="small" type="danger">失败</el-tag>
                <span class="card-time">{{ formatTime(task.completed_at || task.updated_at) }}</span>
              </div>
            </div>
            <div class="card-actions">
              <el-button type="success" size="small" circle @click="downloadTask(task)" :disabled="!task.output_path">
                <el-icon><Download /></el-icon>
              </el-button>
              <el-button type="danger" size="small" circle @click="deleteTaskResult(task)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无已完成任务" :image-size="80" />
      </div>
    </div>

    <el-dialog v-model="showPreview" title="视频预览" width="800px" center @close="closePreview">
      <div class="preview-container">
        <video 
          ref="previewVideoRef"
          v-if="previewUrl" 
          :src="previewUrl" 
          controls 
          autoplay 
          class="preview-video"
        />
      </div>
    </el-dialog>

    <a href="https://deerflow.tech" target="_blank" class="deerflow-badge">✦ Deerflow</a>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { taskApi } from '@/services/api'
import { ElMessage } from 'element-plus'
import websocketService from '@/services/websocket'

const isDarkTheme = inject('isDarkTheme', ref(false))

const router = useRouter()
const taskStore = useTaskStore()

const showPreview = ref(false)
const previewUrl = ref('')
const previewVideoRef = ref(null)

const allTasks = computed(() => taskStore.tasks)

const pendingTasks = computed(() => 
  allTasks.value.filter(t => t.status === 'pending')
)

const queuedTasks = computed(() => 
  allTasks.value.filter(t => t.status === 'queued')
)

const runningTasks = computed(() => 
  allTasks.value.filter(t => t.status === 'processing' || t.status === 'running')
)

const activeTasks = computed(() => 
  [...queuedTasks.value, ...runningTasks.value]
)

const completedTasks = computed(() => 
  allTasks.value.filter(t => t.status === 'completed' || t.status === 'failed')
)

const fetchTasks = async () => {
  try {
    await taskStore.fetchTasks()
  } catch (error) {
    console.error('获取任务列表失败:', error)
  }
}

const createTask = () => {
  router.push('/tasks/create')
}

const runAllPending = async () => {
  if (pendingTasks.value.length === 0) {
    ElMessage.warning('暂无等待运行的任务')
    return
  }
  
  try {
    for (const task of pendingTasks.value) {
      await taskApi.control(task.task_id, 'start')
      try {
        await websocketService.connect(task.task_id)
      } catch (error) {
        console.error(`连接任务 ${task.task_id} WebSocket 失败:`, error)
      }
    }
    
    ElMessage.success('任务已开始运行')
    await fetchTasks()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const startTask = async (task) => {
  try {
    await taskApi.control(task.task_id, 'start')
    ElMessage.success('任务已开始')
    await taskStore.fetchTasks()
    try {
      await websocketService.connect(task.task_id)
    } catch (error) {
      console.error(`连接任务 ${task.task_id} WebSocket 失败:`, error)
    }
  } catch (error) {
    ElMessage.error('启动失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const cancelTask = async (task) => {
  try {
    await taskApi.control(task.task_id, 'cancel')
    ElMessage.success('任务已取消')
    await fetchTasks()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const priorityTask = async (task) => {
  try {
    await taskApi.control(task.task_id, 'priority')
    ElMessage.success('任务已置顶')
    await fetchTasks()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const deleteTask = async (task) => {
  try {
    await taskApi.delete(task.task_id)
    ElMessage.success('删除成功')
    await fetchTasks()
  } catch (error) {
    ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const previewTask = (task) => {
  if (task.output_path) {
    previewUrl.value = getVideoUrl(task.output_path)
    showPreview.value = true
  }
}

const closePreview = () => {
  if (previewVideoRef.value) {
    previewVideoRef.value.pause()
    previewVideoRef.value.currentTime = 0
  }
  previewUrl.value = ''
}

const downloadTask = (task) => {
  if (task.output_path) {
    const url = getVideoUrl(task.output_path)
    const link = document.createElement('a')
    link.href = url
    link.download = task.output_path.split('/').pop() || 'video.mp4'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

const deleteTaskResult = async (task) => {
  try {
    await taskApi.delete(task.task_id)
    ElMessage.success('删除成功')
    await fetchTasks()
  } catch (error) {
    ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const getVideoUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `/files/${path.replace(/\\/g, '/')}`
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN')
}

const hoverVideo = (e) => {
  e.target.play()
}

const leaveVideo = (e) => {
  e.target.pause()
  e.target.currentTime = 0
}

onMounted(async () => {
  await fetchTasks()
  taskStore.startPolling()
})

onUnmounted(() => {
  taskStore.stopPolling()
})
</script>

<style scoped>
.dashboard-container {
  min-height: calc(100vh - 64px - 40px);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 50%, #eef2f6 100%);
  padding: 0;
  transition: background 0.3s ease;
}

.dark-theme .dashboard-container {
  background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #1a1f26 100%);
}

.dashboard-content {
  padding: 20px;
}

.section-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.action-panel {
  flex: 0 0 35%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-card {
  display: flex;
  align-items: center;
  padding: 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.dark-theme .action-card {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.action-card:hover {
  background: rgba(255, 255, 255, 1);
  transform: translateX(8px);
  border-color: rgba(64, 158, 255, 0.3);
}

.dark-theme .action-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(0, 217, 255, 0.3);
}

.action-card.run:hover {
  border-color: rgba(0, 255, 136, 0.3);
}

.action-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
}

.action-icon.new {
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.2), rgba(64, 158, 255, 0.05));
  border: 1px solid rgba(64, 158, 255, 0.3);
}

.dark-theme .action-icon.new {
  background: linear-gradient(135deg, rgba(0, 217, 255, 0.2), rgba(0, 217, 255, 0.05));
  border-color: rgba(0, 217, 255, 0.3);
}

.action-icon.new .el-icon {
  font-size: 28px;
  color: #409EFF;
}

.dark-theme .action-icon.new .el-icon {
  color: #00d9ff;
}

.action-icon.running {
  background: linear-gradient(135deg, rgba(103, 194, 58, 0.2), rgba(103, 194, 58, 0.05));
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.dark-theme .action-icon.running {
  background: linear-gradient(135deg, rgba(0, 255, 136, 0.2), rgba(0, 255, 136, 0.05));
  border-color: rgba(0, 255, 136, 0.3);
}

.action-icon.running .el-icon {
  font-size: 28px;
  color: #67c23a;
}

.dark-theme .action-icon.running .el-icon {
  color: #00ff88;
}

.action-text {
  flex: 1;
}

.action-text h3 {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  transition: color 0.3s ease;
}

.dark-theme .action-text h3 {
  color: #fff;
}

.action-text p {
  margin: 0;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.5);
  transition: color 0.3s ease;
}

.dark-theme .action-text p {
  color: rgba(255, 255, 255, 0.5);
}

.action-arrow {
  opacity: 0;
  transition: all 0.3s;
}

.action-card:hover .action-arrow {
  opacity: 1;
  transform: translateX(4px);
}

.action-arrow .el-icon {
  font-size: 20px;
  color: #409EFF;
  transition: color 0.3s ease;
}

.dark-theme .action-arrow .el-icon {
  color: #00d9ff;
}

.pending-panel {
  flex: 1;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  padding: 20px;
  max-height: 280px;
  overflow-y: auto;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.dark-theme .pending-panel {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.panel-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.3s ease;
}

.dark-theme .panel-header h4 {
  color: #fff;
}

.panel-header h4 .el-icon {
  font-size: 18px;
}

.panel-header h4 .pulse {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.count-badge {
  background: linear-gradient(135deg, #409EFF, #67c23a);
  color: #fff;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.dark-theme .count-badge {
  background: linear-gradient(135deg, #00d9ff, #00ff88);
  color: #0d1117;
}

.count-badge.running {
  background: linear-gradient(135deg, #e6a23c, #ff9f43);
}

.dark-theme .count-badge.running {
  background: linear-gradient(135deg, #ff9f43, #ffc107);
}

.count-badge.completed {
  background: linear-gradient(135deg, #909399, #a6a9ad);
}

.dark-theme .count-badge.completed {
  background: linear-gradient(135deg, #a29bfe, #6c5ce7);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 10px;
  transition: all 0.2s;
}

.dark-theme .task-item {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.06);
}

.task-item:hover {
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(0, 0, 0, 0.1);
}

.dark-theme .task-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.1);
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-name {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  transition: color 0.3s ease;
}

.dark-theme .task-name {
  color: #fff;
}

.task-time {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.4);
  transition: color 0.3s ease;
}

.dark-theme .task-time {
  color: rgba(255, 255, 255, 0.4);
}

.task-actions {
  display: flex;
  gap: 8px;
}

.section-middle {
  margin-bottom: 32px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.dark-theme .section-middle {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.running-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-top: 16px;
}

.running-card {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
}

.dark-theme .running-card {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
}

.running-card.queued-card {
  background: rgba(64, 158, 255, 0.08);
  border-color: rgba(64, 158, 255, 0.2);
}

.dark-theme .running-card.queued-card {
  background: rgba(0, 217, 255, 0.08);
  border-color: rgba(0, 217, 255, 0.2);
}

.queued-info {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 0;
  margin-bottom: 12px;
}

.queued-text {
  font-size: 14px;
  color: #909399;
}

.dark-theme .queued-text {
  color: #8b949e;
}

.running-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.running-header .task-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.dark-theme .running-header .task-name {
  color: #fff;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.progress-section :deep(.el-progress) {
  flex: 1;
}

.progress-section :deep(.el-progress__text) {
  color: #409EFF !important;
  font-weight: 600;
}

.dark-theme .progress-section :deep(.el-progress__text) {
  color: #00d9ff !important;
}

.progress-text {
  font-size: 14px;
  font-weight: 600;
  color: #409EFF;
  min-width: 45px;
  transition: color 0.3s ease;
}

.dark-theme .progress-text {
  color: #00d9ff;
}

.running-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.section-bottom {
  padding: 20px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.dark-theme .section-bottom {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.completed-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.completed-card {
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s;
}

.dark-theme .completed-card {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.08);
}

.completed-card:hover {
  transform: translateY(-4px);
  border-color: rgba(64, 158, 255, 0.3);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.dark-theme .completed-card:hover {
  border-color: rgba(0, 217, 255, 0.3);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.completed-card.has-error {
  border-color: rgba(245, 108, 108, 0.3);
}

.dark-theme .completed-card.has-error {
  border-color: rgba(255, 82, 82, 0.3);
}

.completed-card.has-error:hover {
  border-color: rgba(245, 108, 108, 0.5);
  box-shadow: 0 8px 24px rgba(245, 108, 108, 0.2);
}

.dark-theme .completed-card.has-error:hover {
  border-color: rgba(255, 82, 82, 0.5);
  box-shadow: 0 8px 24px rgba(255, 82, 82, 0.2);
}

.card-thumbnail {
  position: relative;
  aspect-ratio: 16/9;
  background: #f5f7fa;
  overflow: hidden;
  transition: background 0.3s ease;
}

.dark-theme .card-thumbnail {
  background: #1a1f26;
}

.card-thumbnail video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.error-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(0, 0, 0, 0.4);
  transition: color 0.3s ease;
}

.dark-theme .error-placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.error-placeholder .el-icon {
  font-size: 32px;
  color: #f56c6c;
}

.dark-theme .error-placeholder .el-icon {
  color: #ff5252;
}

.error-placeholder span {
  font-size: 12px;
}

.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.dark-theme .card-overlay {
  background: rgba(0, 0, 0, 0.6);
}

.completed-card:hover .card-overlay {
  opacity: 1;
}

.card-overlay .el-button {
  width: 48px;
  height: 48px;
}

.card-info {
  padding: 12px;
}

.card-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.3s ease;
}

.dark-theme .card-name {
  color: #fff;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-time {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.4);
  transition: color 0.3s ease;
}

.dark-theme .card-time {
  color: rgba(255, 255, 255, 0.4);
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  padding: 0 12px 12px;
}

.preview-container {
  display: flex;
  justify-content: center;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.preview-video {
  width: 100%;
  max-height: 450px;
}

.deerflow-badge {
  position: fixed;
  bottom: 20px;
  right: 20px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.3);
  text-decoration: none;
  transition: all 0.3s;
  z-index: 1000;
}

.dark-theme .deerflow-badge {
  color: rgba(255, 255, 255, 0.3);
}

.deerflow-badge:hover {
  color: #409EFF;
  text-shadow: 0 0 10px rgba(64, 158, 255, 0.5);
}

.dark-theme .deerflow-badge:hover {
  color: #00d9ff;
  text-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
}

:deep(.el-empty__description) {
  color: rgba(0, 0, 0, 0.4);
  transition: color 0.3s ease;
}

.dark-theme :deep(.el-empty__description) {
  color: rgba(255, 255, 255, 0.4);
}

:deep(.el-empty__image img) {
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.dark-theme :deep(.el-empty__image img) {
  opacity: 0.3;
}

@media (max-width: 1400px) {
  .completed-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 1100px) {
  .completed-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .running-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .section-top {
    flex-direction: column;
  }
  
  .action-panel {
    flex: none;
    width: 100%;
  }
  
  .completed-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
