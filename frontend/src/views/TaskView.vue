<template>
  <div class="task-view">
    <div class="view-header">
      <h1>任务管理</h1>
      <button class="create-btn" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? '取消' : '创建任务' }}
      </button>
    </div>

    <div v-if="showCreateForm" class="create-section">
      <TaskCreate 
        @created="handleTaskCreated"
        @error="handleError"
      />
    </div>

    <div class="list-section">
      <TaskList 
        :tasks="tasks"
        :isLoading="isLoading"
        @delete="handleDelete"
      />
    </div>

    <div v-if="error" class="error-message" @click="clearError">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/taskStore'
import TaskList from '@/components/TaskList.vue'
import TaskCreate from '@/components/TaskCreate.vue'

const taskStore = useTaskStore()
const { tasks, isLoading, error } = storeToRefs(taskStore)

const showCreateForm = ref(false)

onMounted(() => {
  taskStore.fetchTasks()
  taskStore.startPolling()
})

onUnmounted(() => {
  taskStore.stopPolling()
})

const handleTaskCreated = async (taskData) => {
  try {
    await taskStore.createTask(taskData)
    showCreateForm.value = false
  } catch (err) {
    console.error('创建任务失败:', err)
  }
}

const handleDelete = async (taskId) => {
  if (confirm('确定要删除这个任务吗？')) {
    try {
      await taskStore.deleteTask(taskId)
    } catch (err) {
      console.error('删除任务失败:', err)
    }
  }
}

const handleError = (message) => {
  console.error('错误:', message)
}

const clearError = () => {
  taskStore.clearError()
}
</script>

<style scoped>
.task-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.view-header h1 {
  font-size: 32px;
  color: #333;
  margin: 0;
}

.create-btn {
  padding: 10px 20px;
  background-color: #2196f3;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.create-btn:hover {
  background-color: #1976d2;
}

.create-section {
  margin-bottom: 30px;
}

.list-section {
  margin-bottom: 20px;
}

.error-message {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background-color: #f44336;
  color: white;
  padding: 15px 30px;
  border-radius: 4px;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}
</style>
