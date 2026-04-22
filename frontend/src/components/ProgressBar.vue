<template>
  <div class="progress-bar">
    <div class="progress-track">
      <div 
        class="progress-fill" 
        :style="{ width: `${progress}%` }"
        :class="statusClass"
      ></div>
    </div>
    <div class="progress-text">
      <span class="progress-value">{{ progress.toFixed(1) }}%</span>
      <span class="progress-status">{{ statusText }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: {
    type: Number,
    default: 0,
    validator: (value) => value >= 0 && value <= 100
  },
  status: {
    type: String,
    default: 'pending'
  }
})

const statusClass = computed(() => {
  switch (props.status) {
    case 'completed':
      return 'status-completed'
    case 'failed':
      return 'status-failed'
    case 'pending':
      return 'status-pending'
    default:
      return 'status-running'
  }
})

const statusText = computed(() => {
  switch (props.status) {
    case 'pending':
      return '等待中'
    case 'preprocessing':
      return '视频预处理中'
    case 'script_generating':
      return '文案生成中'
    case 'tts_synthesizing':
      return '语音合成中'
    case 'heygem_generating':
      return '视频生成中'
    case 'post_processing':
      return '后期处理中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    default:
      return '未知状态'
  }
})
</script>

<style scoped>
.progress-bar {
  width: 100%;
}

.progress-track {
  width: 100%;
  height: 8px;
  background-color: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease;
  border-radius: 4px;
}

.status-pending {
  background-color: #9e9e9e;
}

.status-running {
  background-color: #2196f3;
  animation: pulse 1.5s infinite;
}

.status-completed {
  background-color: #4caf50;
}

.status-failed {
  background-color: #f44336;
}

.progress-text {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.progress-value {
  font-weight: bold;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}
</style>
