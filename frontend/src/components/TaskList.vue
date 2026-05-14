<template>
  <div class="task-list">
    <div class="list-header">
      <h2>任务列表</h2>
      <div class="list-stats">
        <span class="stat-item">总计: {{ tasks.length }}</span>
        <span class="stat-item running">运行中: {{ runningCount }}</span>
        <span class="stat-item completed">完成: {{ completedCount }}</span>
        <span class="stat-item failed">失败: {{ failedCount }}</span>
      </div>
    </div>

    <div v-if="isLoading" class="loading">
      加载中...
    </div>

    <div v-else-if="tasks.length === 0" class="empty">
      <div class="empty-icon">📋</div>
      <div class="empty-text">暂无任务</div>
      <div class="empty-hint">点击上方"创建任务"开始使用</div>
    </div>

    <div v-else class="tasks">
      <TaskItem 
        v-for="task in tasks" 
        :key="task.task_id"
        :task="task"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import TaskItem from './TaskItem.vue'

const props = defineProps({
  tasks: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['delete'])

const runningCount = computed(() => {
  return props.tasks.filter(t => 
    ['preprocessing', 'script_generating', 'tts_synthesizing', 'heygem_generating', 'post_processing'].includes(t.status)
  ).length
})

const completedCount = computed(() => {
  return props.tasks.filter(t => t.status === 'completed').length
})

const failedCount = computed(() => {
  return props.tasks.filter(t => t.status === 'failed').length
})

const handleDelete = (taskId) => {
  emit('delete', taskId)
}
</script>

<style scoped>
.task-list {
  background-color: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.list-header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.list-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
  background-color: #f5f5f5;
  color: #666;
}

.stat-item.running {
  background-color: #e3f2fd;
  color: #1976d2;
}

.stat-item.completed {
  background-color: #e8f5e9;
  color: #388e3c;
}

.stat-item.failed {
  background-color: #ffebee;
  color: #d32f2f;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #666;
}

.empty {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-text {
  font-size: 18px;
  color: #666;
  margin-bottom: 10px;
}

.empty-hint {
  font-size: 14px;
  color: #999;
}

.tasks {
  max-height: 600px;
  overflow-y: auto;
}
</style>
