<template>
  <div class="video-uploader">
    <div 
      class="upload-area"
      :class="{ 'drag-over': isDragOver }"
      @dragover.prevent="isDragOver = true"
      @dragleave="isDragOver = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input 
        ref="fileInput"
        type="file"
        accept="video/*"
        @change="handleFileSelect"
        style="display: none"
      />
      <div v-if="!selectedFile" class="upload-placeholder">
        <div class="upload-icon">📹</div>
        <div class="upload-text">
          点击或拖拽上传视频文件
        </div>
        <div class="upload-hint">
          支持格式: MP4, AVI, MOV, MKV
        </div>
      </div>
      <div v-else class="file-info">
        <div class="file-icon">🎬</div>
        <div class="file-name">{{ selectedFile.name }}</div>
        <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
        <button class="remove-btn" @click.stop="removeFile">×</button>
      </div>
    </div>
    <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${uploadProgress}%` }"></div>
      </div>
      <div class="progress-text">上传中: {{ uploadProgress.toFixed(1) }}%</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadAPI } from '@/api/upload'

const props = defineProps({
  groupType: {
    type: String,
    default: 'scene'
  }
})

const emit = defineEmits(['uploaded', 'error'])

const fileInput = ref(null)
const selectedFile = ref(null)
const uploadProgress = ref(0)
const isDragOver = ref(false)

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    processFile(file)
  }
}

const handleDrop = (event) => {
  isDragOver.value = false
  const file = event.dataTransfer.files[0]
  if (file && file.type.startsWith('video/')) {
    processFile(file)
  }
}

const processFile = (file) => {
  selectedFile.value = file
  uploadFile(file)
}

const uploadFile = async (file) => {
  uploadProgress.value = 1
  
  try {
    const response = await uploadAPI.uploadVideo(file, props.groupType)
    
    if (response.code === 200) {
      emit('uploaded', response.data)
    } else {
      throw new Error(response.message || '上传失败')
    }
  } catch (error) {
    console.error('上传失败:', error)
    emit('error', error.message)
    selectedFile.value = null
  } finally {
    uploadProgress.value = 0
  }
}

const removeFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<style scoped>
.video-uploader {
  width: 100%;
}

.upload-area {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: #2196f3;
  background-color: #f5f5f5;
}

.upload-area.drag-over {
  border-color: #2196f3;
  background-color: #e3f2fd;
}

.upload-placeholder {
  color: #666;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.upload-text {
  font-size: 16px;
  margin-bottom: 5px;
}

.upload-hint {
  font-size: 12px;
  color: #999;
}

.file-info {
  position: relative;
}

.file-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.file-name {
  font-size: 14px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: #666;
}

.remove-btn {
  position: absolute;
  top: -10px;
  right: -10px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: #f44336;
  color: white;
  border: none;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.remove-btn:hover {
  background-color: #d32f2f;
}

.upload-progress {
  margin-top: 10px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background-color: #e0e0e0;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #2196f3;
  transition: width 0.3s;
}

.progress-text {
  margin-top: 5px;
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>
