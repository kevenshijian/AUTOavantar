<template>
  <div class="task-item" :class="statusClass">
    <div class="task-header">
      <div class="task-name">{{ task.name }}</div>
      <div class="task-actions">
        <button 
          v-if="canDelete" 
          class="action-btn delete-btn"
          @click="$emit('delete', task.task_id)"
          title="删除任务"
        >
          🗑️
        </button>
      </div>
    </div>
    
    <div class="task-info">
      <div class="info-item">
        <span class="info-label">任务ID:</span>
        <span class="info-value">{{ task.task_id }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">创建时间:</span>
        <span class="info-value">{{ formatTime(task.created_at) }}</span>
      </div>
      <div v-if="task.current_stage" class="info-item">
        <span class="info-label">当前阶段:</span>
        <span class="info-value">{{ task.current_stage }}</span>
      </div>
    </div>

    <div class="task-progress">
      <ProgressBar 
        :progress="task.progress * 100" 
        :status="task.status"
      />
    </div>

    <div v-if="task.error_message" class="task-error">
      <strong>错误信息:</strong> {{ task.error_message }}
    </div>

    <div v-if="task.output_path && task.status === 'completed'" class="task-output">
      <strong>输出文件:</strong> 
      <a :href="`/files/${task.output_path}`" target="_blank">查看视频</a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ProgressBar from './ProgressBar.vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  }
})

defineEmits(['delete'])

const statusClass = computed(() => {
  return `status-${props.task.status}`
})

const canDelete = computed(() => {
  return ['pending', 'completed', 'failed'].includes(props.task.status)
})

const formatTime = (isoString) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.task-item {
  background-color: white;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #ccc;
}

.status-pending {
  border-left-color: #9e9e9e;
}

.status-preprocessing,
.status-script_generating,
.status-tts_synthesizing,
.status-heygem_generating,
.status-post_processing {
  border-left-color: #2196f3;
}

.status-completed {
  border-left-color: #4caf50;
}

.status-failed {
  border-left-color: #f44336;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-name {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.action-btn:hover {
  background-color: #f5f5f5;
}

.delete-btn:hover {
  background-color: #ffebee;
}

.task-info {
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  margin-bottom: 4px;
  font-size: 14px;
}

.info-label {
  color: #666;
  min-width: 80px;
}

.info-value {
  color: #333;
}

.task-progress {
  margin-bottom: 12px;
}

.task-error {
  padding: 8px;
  background-color: #ffebee;
  border-radius: 4px;
  color: #c62828;
  font-size: 14px;
  margin-bottom: 12px;
}

.task-output {
  padding: 8px;
  background-color: #e8f5e9;
  border-radius: 4px;
  font-size: 14px;
}

.task-output a {
  color: #2e7d32;
  text-decoration: none;
  margin-left: 8px;
}

.task-output a:hover {
  text-decoration: underline;
}
</style>
