<template>
  <div class="task-list-page">
    <!-- 页面标题和操作按钮 -->
    <div class="page-header">
      <h2>任务列表</h2>
      <el-button type="primary" @click="createTask">
        <el-icon><Plus /></el-icon>
        创建任务
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="任务状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable>
            <el-option label="等待中" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="任务名称">
          <el-input 
            v-model="filterForm.keyword" 
            placeholder="搜索任务名称" 
            clearable
            style="width: 200px;"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleFilter">
            <el-icon><Search /></el-icon>
            筛选
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="list-card" shadow="never">
      <el-table 
        :data="filteredTasks" 
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="任务名称" min-width="200">
          <template #default="{ row }">
            <div class="task-name-cell">
              <el-link 
                type="primary" 
                @click="viewTask(row.task_id)"
                :underline="false"
              >
                {{ row.name }}
              </el-link>
              <el-tag v-if="row.use_llm_generate" size="small" type="info" class="ml-2">
                AI生成
              </el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="dark">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="current_stage" label="当前阶段" min-width="150">
          <template #default="{ row }">
            <span class="stage-text">{{ row.current_stage || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="progress" label="进度" width="200">
          <template #default="{ row }">
            <el-progress 
              :percentage="Math.round(row.progress)"
              :status="row.status === 'failed' ? 'exception' : ''"
              :striped="row.status === 'processing'"
            />
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'processing' || row.status === 'pending'"
              type="warning" 
              size="small"
              @click="pauseTask(row)"
            >
              暂停
            </el-button>
            
            <el-button 
              v-if="row.status === 'paused'"
              type="success" 
              size="small"
              @click="resumeTask(row)"
            >
              恢复
            </el-button>
            
            <el-button 
              v-if="row.status === 'pending' && row.progress > 0"
              type="primary" 
              size="small"
              @click="restartFromCheckpoint(row)"
            >
              从检查点重启
            </el-button>
            
            <el-button 
              v-if="row.status === 'failed'"
              type="primary" 
              size="small"
              @click="retryTask(row)"
            >
              重试
            </el-button>
            
            <el-button 
              v-if="row.status === 'completed' && row.output_path"
              type="success" 
              size="small"
              @click="downloadTask(row)"
            >
              下载
            </el-button>
            
            <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, row)">
              <el-button type="text" size="small">
                更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="view">查看详情</el-dropdown-item>
                  <el-dropdown-item command="logs">查看日志</el-dropdown-item>
                  <el-dropdown-item v-if="row.status !== 'processing'" command="delete" divided>
                    删除任务
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi } from '@/services/api'
import websocketService from '@/services/websocket'

const router = useRouter()
const taskStore = useTaskStore()

const loading = ref(false)
const selectedTasks = ref([])
const unsubscribeCallbacks = ref([])

// 筛选表单
const filterForm = reactive({
  status: '',
  keyword: ''
})

// 分页配置
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

// 过滤后的任务列表
const filteredTasks = computed(() => {
  let result = taskStore.tasks
  
  if (filterForm.status) {
    result = result.filter(t => t.status === filterForm.status)
  }
  
  if (filterForm.keyword) {
    const keyword = filterForm.keyword.toLowerCase()
    result = result.filter(t => t.name.toLowerCase().includes(keyword))
  }
  
  // 分页
  const start = (pagination.page - 1) * pagination.pageSize
  const end = start + pagination.pageSize
  pagination.total = result.length
  
  return result.slice(start, end)
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

// 创建任务
const createTask = () => {
  router.push('/tasks/create')
}

// 查看任务
const viewTask = (taskId) => {
  router.push(`/tasks/${taskId}`)
}

// 暂停任务
const pauseTask = async (row) => {
  try {
    await taskApi.control(row.task_id, 'pause')
    ElMessage.success('任务已暂停')
    await taskStore.fetchTasks()
  } catch (error) {
    ElMessage.error('暂停失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

// 恢复任务
const resumeTask = async (row) => {
  try {
    await taskApi.control(row.task_id, 'resume')
    ElMessage.success('任务已恢复')
    await taskStore.fetchTasks()
    try {
      await websocketService.connect(row.task_id)
    } catch (error) {
      console.error(`连接任务 ${row.task_id} WebSocket 失败:`, error)
    }
  } catch (error) {
    ElMessage.error('恢复失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

// 重试任务
const retryTask = async (row) => {
  try {
    await taskApi.control(row.task_id, 'retry')
    ElMessage.success('任务已重试')
    await taskStore.fetchTasks()
    try {
      await websocketService.connect(row.task_id)
    } catch (error) {
      console.error(`连接任务 ${row.task_id} WebSocket 失败:`, error)
    }
  } catch (error) {
    ElMessage.error('重试失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const restartFromCheckpoint = async (row) => {
  try {
    await ElMessageBox.confirm(
      `任务将从检查点重启，当前进度: ${row.progress}%，阶段: ${row.current_stage || '未知'}。是否继续？`,
      '从检查点重启',
      {
        type: 'info',
        confirmButtonText: '重启',
        cancelButtonText: '取消'
      }
    )
    
    await taskApi.control(row.task_id, 'restart_checkpoint')
    ElMessage.success('任务已从检查点重启')
    await taskStore.fetchTasks()
    try {
      await websocketService.connect(row.task_id)
    } catch (error) {
      console.error(`连接任务 ${row.task_id} WebSocket 失败:`, error)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('从检查点重启失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
    }
  }
}

// 删除任务
const deleteTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？', '提示', {
      type: 'warning'
    })
    
    await taskApi.delete(row.task_id)
    ElMessage.success('删除成功')
    await taskStore.fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
    }
  }
}

// 处理更多命令
const handleCommand = (command, row) => {
  switch (command) {
    case 'view':
      viewTask(row.task_id)
      break
    case 'logs':
      viewLogs(row)
      break
    case 'delete':
      deleteTask(row)
      break
  }
}

// 查看日志
const viewLogs = (row) => {
  // TODO: 实现日志查看功能
  ElMessage.info('日志功能开发中...')
}

// 下载任务
const downloadTask = (row) => {
  if (row.output_path) {
    const url = `/files/${row.output_path}`
    const link = document.createElement('a')
    link.href = url
    link.download = row.output_path.split('/').pop() || 'video.mp4'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// 筛选
const handleFilter = async () => {
  pagination.page = 1
  await taskStore.fetchTasks()
}

// 重置筛选
const resetFilter = async () => {
  filterForm.status = ''
  filterForm.keyword = ''
  await handleFilter()
}

// 分页大小变化
const handleSizeChange = (size) => {
  pagination.pageSize = size
}

// 页码变化
const handleCurrentChange = (page) => {
  pagination.page = page
}

// 选择变化
const handleSelectionChange = (selection) => {
  selectedTasks.value = selection
}

const connectToRunningTasks = async () => {
  const runningTasks = taskStore.tasks.filter(t => 
    ['pending', 'processing', 'running', 'queued'].includes(t.status)
  )
  
  for (const task of runningTasks) {
    try {
      await websocketService.connect(task.task_id)
    } catch (error) {
      console.error(`连接任务 ${task.task_id} WebSocket 失败:`, error)
    }
  }
}

const setupWebSocketListeners = () => {
  const unsubscribeStatus = websocketService.onStatusUpdate((message) => {
    taskStore.updateTaskFromWebSocket(message)
  })
  unsubscribeCallbacks.value.push(unsubscribeStatus)

  const unsubscribeCompleted = websocketService.onCompleted((message) => {
    taskStore.updateTaskFromWebSocket({
      task_id: message.task_id,
      status: 'completed',
      progress: 100,
      output_path: message.output_path
    })
    const task = taskStore.tasks.find(t => t.task_id === message.task_id)
    ElMessage.success(`任务 ${task?.name || message.task_id} 已完成`)
  })
  unsubscribeCallbacks.value.push(unsubscribeCompleted)

  const unsubscribeFailed = websocketService.onFailed((message) => {
    taskStore.updateTaskFromWebSocket({
      task_id: message.task_id,
      status: 'failed',
      error_message: message.message || message.error_message
    })
    const task = taskStore.tasks.find(t => t.task_id === message.task_id)
    ElMessage.error(`任务 ${task?.name || message.task_id} 失败: ${message.message || ''}`)
  })
  unsubscribeCallbacks.value.push(unsubscribeFailed)
}

const cleanupWebSocket = () => {
  unsubscribeCallbacks.value.forEach(unsubscribe => unsubscribe())
  unsubscribeCallbacks.value = []
  websocketService.disconnectAll()
}

onMounted(async () => {
  loading.value = true
  try {
    await taskStore.fetchTasks()
    setupWebSocketListeners()
    await connectToRunningTasks()
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  cleanupWebSocket()
})
</script>

<style scoped>
.task-list-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.filter-card {
  margin-bottom: 20px;
}

.list-card {
  min-height: 500px;
}

.task-name-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.ml-2 {
  margin-left: 8px;
}

.stage-text {
  color: #606266;
  font-size: 13px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

:deep(.el-dropdown) {
  vertical-align: middle;
  margin-left: 8px;
}
</style>
