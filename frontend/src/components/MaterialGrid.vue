<template>
  <div class="material-grid">
    <el-empty v-if="materials.length === 0" description="暂无素材" />
    
    <div v-else class="grid-container">
      <div
        v-for="material in materials"
        :key="material.id"
        class="material-item"
        :class="{ selected: selectedId === material.id }"
        @click="selectMaterial(material)"
      >
        <div class="material-preview">
          <img
            v-if="material.thumbnail || material.previewUrl"
            :src="material.thumbnail || material.previewUrl"
            :alt="material.name"
          />
          <div v-else class="placeholder">
            <el-icon :size="40"><VideoCamera v-if="type === 'video'" /><Picture v-else /></el-icon>
          </div>
        </div>
        
        <div class="material-info">
          <div class="material-name" :title="material.name">{{ material.name }}</div>
          <div v-if="material.duration" class="material-duration">
            {{ formatDuration(material.duration) }}
          </div>
        </div>
        
        <div v-if="selectedId === material.id" class="selected-indicator">
          <el-icon><Check /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { VideoCamera, Picture, Check } from '@element-plus/icons-vue'

const props = defineProps({
  materials: {
    type: Array,
    default: () => []
  },
  type: {
    type: String,
    default: 'video'
  }
})

const emit = defineEmits(['select'])

const selectedId = ref(null)

const selectMaterial = (material) => {
  selectedId.value = material.id
  emit('select', material)
}

const formatDuration = (seconds) => {
  if (!seconds) return ''
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.material-grid {
  padding: 10px;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 15px;
}

.material-item {
  position: relative;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #f5f7fa;
}

.material-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.material-item.selected {
  border-color: #409eff;
}

.material-preview {
  aspect-ratio: 16/9;
  overflow: hidden;
  background: #e4e7ed;
}

.material-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.material-info {
  padding: 10px;
}

.material-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.material-duration {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.selected-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: #409eff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}
</style>
