<template>
  <div class="smart-cut-view">
    <el-card class="page-header">
      <h1>智能裁剪</h1>
      <p class="description">上传视频，智能识别分割点，快速提取精彩片段</p>
    </el-card>

    <!-- 上传区域 -->
    <el-card v-if="!videoInfo" class="upload-section">
      <el-upload
        ref="uploadRef"
        class="video-uploader"
        drag
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleFileChange"
        accept=".mp4,.avi,.mov,.mkv"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽视频文件到此处，或 <em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 mp4、avi、mov 格式，最大 2GB
          </div>
        </template>
      </el-upload>
    </el-card>

    <!-- 上传进度 -->
    <el-card v-if="uploading" class="upload-progress">
      <div class="progress-content">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>正在上传视频...</span>
        <el-progress :percentage="uploadProgress" :stroke-width="8" />
      </div>
    </el-card>

    <!-- 视频预览和配置 -->
    <div v-if="videoInfo && !uploading" class="video-section">
      <!-- 左侧：视频预览 -->
      <el-card class="video-preview">
        <template #header>
          <div class="card-header">
            <span>视频预览</span>
            <el-button type="primary" text @click="resetUpload">
              <el-icon><RefreshLeft /></el-icon>
              重新选择
            </el-button>
          </div>
        </template>

        <div class="video-container">
          <video
            ref="videoPlayer"
            :src="videoUrl"
            controls
            class="video-player"
            @loadedmetadata="handleVideoLoaded"
          ></video>
        </div>

        <div class="video-info">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文件名">{{ videoInfo.video_name }}</el-descriptions-item>
            <el-descriptions-item label="时长">{{ formatDuration(videoInfo.duration) }}</el-descriptions-item>
            <el-descriptions-item label="分辨率">{{ videoInfo.width }} × {{ videoInfo.height }}</el-descriptions-item>
            <el-descriptions-item label="帧率">{{ videoInfo.fps }} fps</el-descriptions-item>
            <el-descriptions-item label="总帧数">{{ videoInfo.total_frames }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-card>

      <!-- 右侧：参数配置 -->
      <el-card class="config-panel">
        <template #header>
          <span>裁剪配置</span>
        </template>

        <el-form :model="config" label-width="120px">
          <el-form-item label="场景识别">
            <el-tag type="success" effect="plain">默认开启</el-tag>
            <span class="config-hint">检测镜头切换点</span>
          </el-form-item>

          <el-divider content-position="left">增强识别</el-divider>

          <el-form-item label="光线明暗">
            <el-switch v-model="config.enable_brightness" />
            <span class="config-hint">检测亮度变化</span>
          </el-form-item>

          <el-form-item label="肢体动作">
            <el-switch v-model="config.enable_pose" />
            <span class="config-hint">检测姿态变化</span>
          </el-form-item>

          <el-form-item label="手势变化">
            <el-switch v-model="config.enable_motion" />
            <span class="config-hint">检测手势动作</span>
          </el-form-item>

          <el-form-item label="说话停顿">
            <el-switch v-model="config.enable_silence" />
            <span class="config-hint">检测静音点</span>
          </el-form-item>

          <el-divider content-position="left">参数设置</el-divider>

          <el-form-item label="最短片段时长">
            <el-slider
              v-model="config.min_segment_duration"
              :min="3"
              :max="240"
              :step="1"
              show-input
              :format-tooltip="(val) => `${val} 秒`"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="processing"
              @click="startCutting"
            >
              <el-icon><Scissor /></el-icon>
              开始裁剪
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- 裁剪进度 -->
    <el-card v-if="processing" class="cutting-progress">
      <div class="progress-header">
        <span>正在智能裁剪...</span>
        <el-tag :type="progressStatus === 'exception' ? 'danger' : 'info'">{{ progressInfo.current_stage || '准备中...' }}</el-tag>
      </div>
      <el-progress
        :percentage="progressInfo.progress"
        :status="progressStatus"
        :stroke-width="12"
      />
      <div class="progress-details">
        <span>已处理：{{ progressInfo.processed_frames }} / {{ progressInfo.total_frames }} 帧</span>
        <span v-if="progressInfo.estimated_time">预计剩余：{{ progressInfo.estimated_time }}</span>
      </div>
      <!-- 失败时显示重试按钮 -->
      <div v-if="taskFailed" class="progress-error">
        <el-alert type="error" :closable="false">
          <template #title>
            <span>裁剪失败：{{ errorMessage }}</span>
          </template>
        </el-alert>
        <el-button type="primary" @click="retryCutting" style="margin-top: 12px;">
          <el-icon><RefreshLeft /></el-icon>
          重试
        </el-button>
      </div>
    </el-card>

    <!-- 片段预览 -->
    <el-card v-if="segments.length > 0" class="segments-section">
      <template #header>
        <div class="card-header">
          <span>裁剪片段（共 {{ segments.length }} 个）</span>
          <div>
            <el-button type="primary" text @click="resetUpload">
              <el-icon><RefreshLeft /></el-icon>
              重新裁剪
            </el-button>
          </div>
        </div>
      </template>

      <div class="segments-grid">
        <div
          v-for="seg in segments"
          :key="seg.segment_id"
          class="segment-card"
          :class="{ 'segment-selected': selectedSegments.includes(seg.segment_id) }"
          @click="previewSegment(seg)"
        >
          <div class="segment-thumbnail">
            <img :src="`/files/${seg.thumbnail}`" :alt="seg.reason_label" />
            <span class="segment-duration">{{ formatDuration(seg.duration) }}</span>
            <el-tag class="segment-reason" :type="getReasonTagType(seg.reason)" size="small">
              {{ seg.reason_label }}
            </el-tag>
            <el-button
              class="segment-select-btn"
              :type="selectedSegments.includes(seg.segment_id) ? 'primary' : 'default'"
              size="small"
              circle
              @click.stop="toggleSegmentSelect(seg.segment_id)"
            >
              <el-icon>
                <component :is="selectedSegments.includes(seg.segment_id) ? 'Check' : 'Plus'" />
              </el-icon>
            </el-button>
          </div>
          <div class="segment-info">
            <span>{{ formatDuration(seg.start_time) }} - {{ formatDuration(seg.end_time) }}</span>
          </div>
        </div>
      </div>

      <!-- 批量操作 -->
      <div v-if="selectedSegments.length > 0" class="batch-actions">
        <el-button type="primary" @click="batchAddToPending">
          批量添加（{{ selectedSegments.length }} 个）
        </el-button>
        <el-button @click="clearSelection">取消选择</el-button>
      </div>
    </el-card>

    <!-- 片段预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewSegmentInfo?.reason_label || '片段预览'"
      width="600px"
      destroy-on-close
    >
      <div class="preview-dialog-content">
        <video
          v-if="previewSegmentInfo"
          :src="`/files/${previewSegmentInfo.video_path}`"
          controls
          class="preview-video"
        ></video>
        <div v-if="previewSegmentInfo" class="preview-info">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="时长">{{ formatDuration(previewSegmentInfo.duration) }}</el-descriptions-item>
            <el-descriptions-item label="时间范围">{{ formatDuration(previewSegmentInfo.start_time) }} - {{ formatDuration(previewSegmentInfo.end_time) }}</el-descriptions-item>
            <el-descriptions-item label="分割原因">{{ previewSegmentInfo.reason_label }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="addToPending(previewSegmentInfo)">添加到待处理</el-button>
        <el-button type="success" @click="extractAudio(previewSegmentInfo)">提取音频</el-button>
      </template>
    </el-dialog>

    <!-- 待处理列表 -->
    <el-card v-if="pendingSegments.length > 0" class="pending-section">
      <template #header>
        <div class="card-header">
          <span>待处理片段（{{ pendingSegments.length }} 个）</span>
          <el-button type="danger" text @click="clearPending">
            <el-icon><Delete /></el-icon>
            清空
          </el-button>
        </div>
      </template>

      <div class="pending-list">
        <div v-for="seg in pendingSegments" :key="seg.segment_id" class="pending-item">
          <div class="pending-thumbnail">
            <img :src="`/files/${seg.thumbnail}`" :alt="seg.reason_label" />
          </div>
          <div class="pending-info">
            <span class="pending-name">{{ seg.segment_id }}</span>
            <span class="pending-duration">{{ formatDuration(seg.duration) }}</span>
          </div>
          <el-button type="danger" size="small" circle @click="removeFromPending(seg.segment_id)">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="pending-actions">
        <el-button type="primary" @click="showMergeDialog">
          <el-icon><VideoPlay /></el-icon>
          合成视频
        </el-button>
        <el-button @click="saveToMaterial">
          <el-icon><FolderAdd /></el-icon>
          保存到素材库
        </el-button>
      </div>
    </el-card>

    <!-- 合成配置弹窗 -->
    <el-dialog
      v-model="mergeDialogVisible"
      title="合成视频配置"
      width="500px"
      destroy-on-close
    >
      <el-form :model="mergeConfig" label-width="100px">
        <el-form-item label="输出名称">
          <el-input v-model="mergeConfig.output_name" placeholder="请输入输出文件名" />
        </el-form-item>
        <el-form-item label="分辨率">
          <el-radio-group v-model="mergeConfig.resolution">
            <el-radio-button value="720p">720p</el-radio-button>
            <el-radio-button value="1080p">1080p</el-radio-button>
            <el-radio-button value="2K">2K</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="帧率">
          <el-radio-group v-model="mergeConfig.fps">
            <el-radio-button :value="30">30 fps</el-radio-button>
            <el-radio-button :value="60">60 fps</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="转场效果">
          <el-select v-model="mergeConfig.transition" placeholder="请选择转场效果">
            <el-option value="none" label="无转场" />
            <el-option value="fade" label="淡入淡出" />
            <el-option value="wipe" label="擦除" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="merging" @click="mergeVideos">
          开始合成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UploadFilled,
  Loading,
  RefreshLeft,
  Scissor,
  Check,
  Plus,
  Delete,
  Close,
  VideoPlay,
  FolderAdd
} from '@element-plus/icons-vue'
import { smartCutApi } from '@/services/api'

const router = useRouter()

// 当前任务ID
const currentTaskId = ref('')

// WebSocket 连接
const ws = ref(null)
const wsConnected = ref(false)

// 上传相关
const uploadRef = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)

// 视频信息
const videoInfo = ref(null)
const videoPlayer = ref(null)
const videoUrl = ref('')

// 配置
const config = reactive({
  min_segment_duration: 10,
  enable_brightness: false,
  enable_pose: false,
  enable_motion: false,
  enable_silence: false
})

// 处理状态
const processing = ref(false)
const taskFailed = ref(false)
const errorMessage = ref('')
const progressInfo = reactive({
  progress: 0,
  current_stage: '',
  processed_frames: 0,
  total_frames: 0,
  estimated_time: ''
})

// 片段列表
const segments = ref([])

// 选中的片段
const selectedSegments = ref([])

// 待处理列表
const pendingSegments = ref([])

// 预览弹窗
const previewDialogVisible = ref(false)
const previewSegmentInfo = ref(null)

// 合成弹窗
const mergeDialogVisible = ref(false)
const merging = ref(false)
const mergeConfig = reactive({
  output_name: '',
  resolution: '1080p',
  fps: 30,
  transition: 'none'
})

// 计算属性
const progressStatus = computed(() => {
  if (taskFailed.value) return 'exception'
  if (progressInfo.progress >= 100) return 'success'
  return ''
})

// WebSocket 连接
const connectWebSocket = (taskId) => {
  if (ws.value) {
    ws.value.close()
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/ws/${taskId}`

  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    wsConnected.value = true
    console.log('WebSocket 连接成功')
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    } catch (e) {
      console.error('解析 WebSocket 消息失败:', e)
    }
  }

  ws.value.onerror = (error) => {
    console.error('WebSocket 错误:', error)
    wsConnected.value = false
  }

  ws.value.onclose = () => {
    wsConnected.value = false
    console.log('WebSocket 连接关闭')
  }
}

// 处理 WebSocket 消息
const handleWebSocketMessage = (data) => {
  console.log('收到 WebSocket 消息:', data)

  switch (data.type) {
    case 'smart_cut_progress':
      progressInfo.progress = data.progress
      progressInfo.current_stage = data.current_stage
      progressInfo.processed_frames = data.processed_frames
      progressInfo.total_frames = data.total_frames
      break

    case 'smart_cut_completed':
      processing.value = false
      progressInfo.progress = 100
      segments.value = data.segments || []
      ElMessage.success(`裁剪完成，共 ${data.segments_count} 个片段`)
      // 关闭 WebSocket
      if (ws.value) {
        ws.value.close()
      }
      break

    case 'smart_cut_failed':
      processing.value = false
      taskFailed.value = true
      errorMessage.value = data.error_message
      ElMessage.error(`裁剪失败：${data.error_message}`)
      // 关闭 WebSocket
      if (ws.value) {
        ws.value.close()
      }
      break

    case 'connected':
      console.log('WebSocket 服务器确认连接')
      break
  }
}

// 方法
const handleFileChange = async (file) => {
  // 验证文件大小
  const maxSize = 2 * 1024 * 1024 * 1024 // 2GB
  if (file.raw.size > maxSize) {
    ElMessage.error('视频文件过大，请上传小于 2GB 的文件')
    return
  }

  // 验证文件格式
  const validFormats = ['.mp4', '.avi', '.mov', '.mkv']
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!validFormats.includes(ext)) {
    ElMessage.error('不支持的视频格式，请上传 mp4/avi/mov 文件')
    return
  }

  // 开始上传
  uploading.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('file', file.raw)

    // 模拟上传进度
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += 10
      }
    }, 200)

    const response = await smartCutApi.upload(formData)

    clearInterval(progressInterval)
    uploadProgress.value = 100

    if (response.code === 200) {
      videoInfo.value = response.data
      // 构建视频 URL
      videoUrl.value = `/files/${response.data.video_path}`

      ElMessage.success('视频上传成功')
    } else {
      throw new Error(response.message || '上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error.message || '上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

const handleVideoLoaded = () => {
  console.log('视频加载完成')
}

const resetUpload = () => {
  videoInfo.value = null
  videoUrl.value = ''
  uploadProgress.value = 0
  segments.value = []
  progressInfo.progress = 0
  progressInfo.current_stage = ''
  taskFailed.value = false
  errorMessage.value = ''
}

const startCutting = async () => {
  if (!videoInfo.value) {
    ElMessage.warning('请先上传视频')
    return
  }

  processing.value = true
  taskFailed.value = false
  errorMessage.value = ''
  progressInfo.progress = 0
  progressInfo.current_stage = '准备中...'

  try {
    const response = await smartCutApi.createTask({
      video_path: videoInfo.value.video_path,
      video_name: videoInfo.value.video_name,
      duration: videoInfo.value.duration,
      fps: videoInfo.value.fps,
      width: videoInfo.value.width,
      height: videoInfo.value.height,
      total_frames: videoInfo.value.total_frames,
      config: { ...config }
    })

    if (response.code === 200) {
      currentTaskId.value = response.data.task_id
      ElMessage.success('裁剪任务已创建')

      // 连接 WebSocket 接收进度更新
      connectWebSocket(response.data.task_id)
    } else {
      throw new Error(response.message || '创建任务失败')
    }
  } catch (error) {
    console.error('创建任务失败:', error)
    ElMessage.error(error.message || '创建任务失败')
    processing.value = false
  }
}

const retryCutting = () => {
  taskFailed.value = false
  errorMessage.value = ''
  startCutting()
}

const formatDuration = (seconds) => {
  if (!seconds) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

const getReasonTagType = (reason) => {
  const typeMap = {
    'scene_change': 'info',
    'silence': 'warning',
    'brightness': 'success',
    'motion': '',
    'pose': '',
    'default': ''
  }
  return typeMap[reason] || ''
}

// 片段操作
const previewSegment = (seg) => {
  previewSegmentInfo.value = seg
  previewDialogVisible.value = true
}

const toggleSegmentSelect = (segmentId) => {
  const index = selectedSegments.value.indexOf(segmentId)
  if (index > -1) {
    selectedSegments.value.splice(index, 1)
  } else {
    selectedSegments.value.push(segmentId)
  }
}

const clearSelection = () => {
  selectedSegments.value = []
}

const addToPending = (seg) => {
  if (!seg) return

  const exists = pendingSegments.value.find(s => s.segment_id === seg.segment_id)
  if (exists) {
    ElMessage.warning('该片段已在待处理列表中')
    return
  }

  pendingSegments.value.push(seg)
  ElMessage.success('已添加到待处理列表')
  previewDialogVisible.value = false
}

const removeFromPending = (segmentId) => {
  const index = pendingSegments.value.findIndex(s => s.segment_id === segmentId)
  if (index > -1) {
    pendingSegments.value.splice(index, 1)
  }
}

const clearPending = () => {
  pendingSegments.value = []
}

const batchAddToPending = () => {
  let addedCount = 0
  selectedSegments.value.forEach(segmentId => {
    const seg = segments.value.find(s => s.segment_id === segmentId)
    if (seg && !pendingSegments.value.find(s => s.segment_id === segmentId)) {
      pendingSegments.value.push(seg)
      addedCount++
    }
  })
  ElMessage.success(`已添加 ${addedCount} 个片段到待处理列表`)
  clearSelection()
}

const extractAudio = async (seg) => {
  if (!seg) return

  try {
    const response = await smartCutApi.extractAudio({
      segment_path: seg.video_path,
      name: `${seg.segment_id}_audio`
    })

    if (response.code === 200) {
      ElMessage.success('音频提取成功')
      // TODO: 跳转到素材库创建页面
    } else {
      throw new Error(response.message || '提取音频失败')
    }
  } catch (error) {
    console.error('提取音频失败:', error)
    ElMessage.error(error.message || '提取音频失败')
  }
}

// 合成相关
const showMergeDialog = () => {
  mergeConfig.output_name = `merged_${new Date().toISOString().slice(0, 10)}`
  mergeDialogVisible.value = true
}

const mergeVideos = async () => {
  if (pendingSegments.value.length === 0) {
    ElMessage.warning('请先添加片段到待处理列表')
    return
  }

  merging.value = true

  try {
    const response = await smartCutApi.merge({
      segments: pendingSegments.value.map(s => ({
        video_path: s.video_path,
        segment_id: s.segment_id
      })),
      output_name: mergeConfig.output_name,
      resolution: mergeConfig.resolution,
      fps: mergeConfig.fps,
      transition: mergeConfig.transition
    })

    if (response.code === 200) {
      ElMessage.success('视频合成成功')
      mergeDialogVisible.value = false
      // 显示合成结果
      ElMessage.info(`输出路径: ${response.data.output_path}`)
    } else {
      throw new Error(response.message || '合成失败')
    }
  } catch (error) {
    console.error('合成视频失败:', error)
    ElMessage.error(error.message || '合成失败')
  } finally {
    merging.value = false
  }
}

const saveToMaterial = () => {
  if (pendingSegments.value.length === 0) {
    ElMessage.warning('请先添加片段到待处理列表')
    return
  }

  // 使用 ElMessageBox 弹出选择框
  ElMessageBox.confirm(
    '请选择保存类型',
    '保存到素材库',
    {
      confirmButtonText: '角色',
      cancelButtonText: '场景',
      distinguishCancelAndClose: true,
      type: 'info'
    }
  ).then(() => {
    // 选择"角色"
    const videos = pendingSegments.value.map(s => ({
      path: s.video_path,
      name: s.segment_id,
      duration: s.duration
    }))
    router.push({
      path: '/materials',
      query: {
        action: 'create',
        type: 'character',
        videos: JSON.stringify(videos)
      }
    })
    ElMessage.success('已跳转到角色创建页面')
  }).catch((action) => {
    if (action === 'cancel') {
      // 选择"场景"
      const videos = pendingSegments.value.map(s => ({
        path: s.video_path,
        name: s.segment_id,
        duration: s.duration
      }))
      router.push({
        path: '/materials',
        query: {
          action: 'create',
          type: 'scene',
          videos: JSON.stringify(videos)
        }
      })
      ElMessage.success('已跳转到场景创建页面')
    }
    // 如果是 close（点击关闭按钮），不做任何操作
  })
}

// 组件卸载时关闭 WebSocket
onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
})
</script>

<style scoped>
.smart-cut-view {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
}

.page-header .description {
  margin: 0;
  color: #909399;
}

.upload-section {
  margin-bottom: 20px;
}

.video-uploader {
  width: 100%;
}

.video-uploader :deep(.el-upload-dragger) {
  width: 100%;
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-progress {
  margin-bottom: 20px;
}

.progress-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 0;
}

.video-section {
  display: flex;
  gap: 20px;
}

.video-preview {
  flex: 2;
}

.video-preview .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.video-container {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
}

.video-player {
  width: 100%;
  display: block;
}

.video-info {
  margin-top: 16px;
}

.config-panel {
  flex: 1;
}

.config-hint {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.cutting-progress {
  margin-top: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.progress-details {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  color: #909399;
  font-size: 14px;
}

.progress-error {
  margin-top: 16px;
}

.segments-section {
  margin-top: 20px;
}

.segments-section .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.segments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.segment-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s;
}

.segment-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.segment-thumbnail {
  position: relative;
  aspect-ratio: 16/9;
  background: #000;
}

.segment-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.segment-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.segment-reason {
  position: absolute;
  top: 8px;
  left: 8px;
}

.segment-select-btn {
  position: absolute;
  top: 8px;
  right: 8px;
}

.segment-selected {
  border-color: #409eff;
  border-width: 2px;
  box-shadow: 0 0 8px rgba(64, 158, 255, 0.3);
}

.segment-info {
  padding: 8px 12px;
  font-size: 12px;
  color: #606266;
}

.batch-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.preview-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-video {
  width: 100%;
  border-radius: 8px;
}

.preview-info {
  margin-top: 12px;
}

.pending-section {
  margin-top: 20px;
}

.pending-section .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.pending-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.pending-thumbnail {
  width: 80px;
  height: 45px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.pending-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pending-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pending-name {
  font-size: 14px;
  font-weight: 500;
}

.pending-duration {
  font-size: 12px;
  color: #909399;
}

.pending-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

/* 响应式 */
@media (max-width: 992px) {
  .video-section {
    flex-direction: column;
  }

  .segments-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }
}
</style>
