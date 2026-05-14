<template>
  <el-dialog
    v-model="visible"
    title="选择视频素材"
    width="800px"
    :close-on-click-modal="false"
  >
    <div class="video-selector">
      <!-- 素材类型标签 -->
      <el-tabs v-model="activeTab">
        <el-tab-pane label="角色素材" name="character">
          <MaterialGrid
            :materials="characterMaterials"
            type="character"
            @select="selectMaterial"
          />
        </el-tab-pane>
        <el-tab-pane label="场景素材" name="scene">
          <MaterialGrid
            :materials="sceneMaterials"
            type="scene"
            @select="selectMaterial"
          />
        </el-tab-pane>
      </el-tabs>

      <!-- 视频类型选择 -->
      <div class="video-type-section">
        <span class="label">视频类型：</span>
        <el-radio-group v-model="selectedVideoType">
          <el-radio-button label="opening">开场视频</el-radio-button>
          <el-radio-button label="loop">循环视频</el-radio-button>
          <el-radio-button label="ending">结束视频</el-radio-button>
          <el-radio-button label="scene">场景视频</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :disabled="!selectedMaterial" @click="confirm">
        确认选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMaterialStore } from '@/stores/materialStore'
import MaterialGrid from './MaterialGrid.vue'

const props = defineProps({
  modelValue: Boolean,
  videoType: {
    type: String,
    default: 'opening'
  }
})

const emit = defineEmits(['update:modelValue', 'select'])

const materialStore = useMaterialStore()

// 弹窗可见性
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 当前选中的标签
const activeTab = ref('character')

// 选中的素材
const selectedMaterial = ref(null)

// 视频类型
const selectedVideoType = ref(props.videoType)

// 角色素材
const characterMaterials = computed(() => {
  return materialStore.materials.roles || []
})

// 场景素材
const sceneMaterials = computed(() => {
  return materialStore.materials.scenes || []
})

// 选择素材
const selectMaterial = (material) => {
  selectedMaterial.value = material
}

// 确认选择
const confirm = () => {
  if (selectedMaterial.value) {
    emit('select', {
      ...selectedMaterial.value,
      videoType: selectedVideoType.value
    })
    close()
  }
}

// 关闭弹窗
const close = () => {
  visible.value = false
  selectedMaterial.value = null
  selectedVideoType.value = props.videoType
}

// 监听弹窗打开
watch(() => props.modelValue, (val) => {
  if (val) {
    materialStore.loadMaterials()
    selectedMaterial.value = null
    selectedVideoType.value = props.videoType
  }
})

// 监听视频类型变化
watch(() => props.videoType, (val) => {
  selectedVideoType.value = val
})
</script>

<style scoped>
.video-selector {
  min-height: 400px;
}

.video-type-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.label {
  font-weight: 500;
  color: #606266;
}
</style>