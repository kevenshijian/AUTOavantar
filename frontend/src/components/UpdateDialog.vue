<template>
  <el-dialog
    v-model="visible"
    title="发现新版本"
    width="450px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    center
  >
    <div class="update-content">
      <el-icon class="update-icon" :size="48">
        <Upload />
      </el-icon>
      <h3>AUTOavantar 有新版本可用</h3>

      <div class="version-info">
        <div class="version-row">
          <span class="label">当前版本:</span>
          <span class="value current">{{ localVersion }}</span>
        </div>
        <div class="version-row">
          <span class="label">最新版本:</span>
          <span class="value latest">{{ remoteVersion }}</span>
        </div>
      </div>

      <p class="update-hint">建议更新以获得最新功能和修复</p>
    </div>

    <template #footer>
      <el-button @click="handleDefer">
        稍后提醒
      </el-button>
      <el-button type="primary" @click="handleUpdate">
        立即更新
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Upload } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  localVersion: {
    type: String,
    default: '1.0.0'
  },
  remoteVersion: {
    type: String,
    default: '1.0.0'
  }
})

const emit = defineEmits(['update:modelValue', 'update', 'defer'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const handleUpdate = () => {
  emit('update')
  visible.value = false
}

const handleDefer = () => {
  emit('defer')
  visible.value = false
}
</script>

<style scoped>
.update-content {
  text-align: center;
  padding: 20px;
}

.update-icon {
  color: #409EFF;
  margin-bottom: 16px;
}

.update-content h3 {
  font-size: 18px;
  color: #303133;
  margin-bottom: 20px;
}

.version-info {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.version-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
}

.version-row .label {
  color: #909399;
  font-size: 14px;
}

.version-row .value {
  font-size: 14px;
  font-weight: 500;
}

.version-row .value.current {
  color: #909399;
}

.version-row .value.latest {
  color: #67C23A;
}

.update-hint {
  font-size: 14px;
  color: #606266;
}

/* 暗色主题 */
.dark-theme .update-content h3 {
  color: #e6edf3;
}

.dark-theme .version-info {
  background: #161b22;
}

.dark-theme .version-row .label {
  color: #8b949e;
}

.dark-theme .version-row .value.current {
  color: #8b949e;
}

.dark-theme .update-hint {
  color: #8b949e;
}
</style>
