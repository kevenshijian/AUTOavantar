<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="800px"
    :close-on-click-modal="false"
  >
    <div class="audio-selector">
      <MaterialGrid
        :materials="audioMaterials"
        type="audio"
        @select="selectMaterial"
      />
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
  audioType: {
    type: String,
    default: 'single'
  }
})

const emit = defineEmits(['update:modelValue', 'select'])

const materialStore = useMaterialStore()

// 弹窗可见性
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 选中的素材
const selectedMaterial = ref(null)

// 弹窗标题
const dialogTitle = computed(() => {
  switch (props.audioType) {
    case 'left':
      return '选择左边说话人音频'
    case 'right':
      return '选择右边说话人音频'
    default:
      return '选择参考音频'
  }
})

// 音频素材
const audioMaterials = computed(() => {
  return materialStore.materials.audio || []
})

// 选择素材
const selectMaterial = (material) => {
  selectedMaterial.value = material
}

// 确认选择
const confirm = () => {
  if (selectedMaterial.value) {
    emit('select', selectedMaterial.value)
    close()
  }
}

// 关闭弹窗
const close = () => {
  visible.value = false
  selectedMaterial.value = null
}

// 监听弹窗打开
watch(() => props.modelValue, (val) => {
  if (val) {
    materialStore.loadMaterials()
    selectedMaterial.value = null
  }
})
</script>

<style scoped>
.audio-selector {
  min-height: 400px;
}
</style>