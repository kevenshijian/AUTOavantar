<template>
  <div class="material-view">
    <h1>素材库</h1>

    <div class="tabs">
      <button 
        :class="{ active: activeTab === 'roles' }"
        @click="activeTab = 'roles'"
      >
        角色
      </button>
      <button 
        :class="{ active: activeTab === 'scenes' }"
        @click="activeTab = 'scenes'"
      >
        场景
      </button>
      <button 
        :class="{ active: activeTab === 'bgm' }"
        @click="activeTab = 'bgm'"
      >
        BGM
      </button>
    </div>

    <div v-if="isLoading" class="loading">
      加载中...
    </div>

    <div v-else class="material-content">
      <!-- 角色列表 -->
      <div v-if="activeTab === 'roles'" class="material-grid">
        <div 
          v-for="role in roles" 
          :key="role.role_id"
          class="material-card"
        >
          <div class="card-icon">👤</div>
          <div class="card-title">{{ role.role_name }}</div>
          <div class="card-desc">{{ role.description }}</div>
          <div class="card-meta">视频数量: {{ role.video_count }}</div>
        </div>
      </div>

      <!-- 场景列表 -->
      <div v-if="activeTab === 'scenes'" class="material-grid">
        <div 
          v-for="scene in scenes" 
          :key="scene.scene_id"
          class="material-card"
        >
          <div class="card-icon">🎬</div>
          <div class="card-title">{{ scene.scene_name }}</div>
          <div class="card-type">{{ scene.scene_type }}</div>
          <div class="card-desc">{{ scene.description }}</div>
          <div class="card-meta">视频数量: {{ scene.video_count }}</div>
        </div>
      </div>

      <!-- BGM 列表 -->
      <div v-if="activeTab === 'bgm'" class="material-grid">
        <div 
          v-for="bgm in bgms" 
          :key="bgm.bgm_id"
          class="material-card"
        >
          <div class="card-icon">🎵</div>
          <div class="card-title">{{ bgm.bgm_name }}</div>
          <div class="card-meta">时长: {{ formatDuration(bgm.duration) }}</div>
          <div class="card-desc">{{ bgm.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { materialAPI } from '@/api/materials'

const activeTab = ref('roles')
const roles = ref([])
const scenes = ref([])
const bgms = ref([])
const isLoading = ref(false)

onMounted(() => {
  loadMaterials()
})

const loadMaterials = async () => {
  isLoading.value = true
  try {
    const [rolesRes, scenesRes, bgmsRes] = await Promise.all([
      materialAPI.getRoles(),
      materialAPI.getScenes(),
      materialAPI.getBGM()
    ])

    roles.value = rolesRes
    scenes.value = scenesRes
    bgms.value = bgmsRes
  } catch (error) {
    console.error('加载素材失败:', error)
  } finally {
    isLoading.value = false
  }
}

const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.material-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

h1 {
  font-size: 32px;
  color: #333;
  margin-bottom: 30px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
}

.tabs button {
  padding: 10px 20px;
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.tabs button:hover {
  background-color: #f5f5f5;
}

.tabs button.active {
  background-color: #2196f3;
  color: white;
  border-color: #2196f3;
}

.loading {
  text-align: center;
  padding: 60px;
  color: #666;
}

.material-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.material-card {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.card-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 15px;
}

.card-title {
  font-size: 18px;
  font-weight: bold;
  color: #333;
  margin-bottom: 10px;
}

.card-type {
  font-size: 12px;
  color: #2196f3;
  background-color: #e3f2fd;
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 10px;
}

.card-desc {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
  line-height: 1.5;
}

.card-meta {
  font-size: 12px;
  color: #999;
}
</style>
