<template>
  <el-dialog
    v-model="visible"
    title="GPU 驱动提示"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    center
  >
    <div class="cuda-warning-content">
      <el-icon class="warning-icon" :size="64">
        <WarningFilled />
      </el-icon>
      <h3>检测到 GPU 驱动问题</h3>
      <p class="warning-message">{{ message }}</p>

      <div class="info-card" v-if="gpuInfo">
        <div class="info-row">
          <span class="label">GPU 型号:</span>
          <span class="value">{{ gpuInfo.gpu_name || '未知' }}</span>
        </div>
        <div class="info-row">
          <span class="label">显存大小:</span>
          <span class="value">{{ gpuInfo.gpu_memory_gb }}GB</span>
        </div>
        <div class="info-row">
          <span class="label">驱动版本:</span>
          <span class="value">{{ gpuInfo.driver_version || '未知' }}</span>
        </div>
        <div class="info-row">
          <span class="label">最低要求:</span>
          <span class="value required">{{ gpuInfo.minimum_driver }}+</span>
        </div>
      </div>

      <div class="action-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>请更新显卡驱动后重启应用以获得最佳体验</span>
      </div>
    </div>

    <template #footer>
      <el-button type="primary" @click="openDriverDownload">
        下载驱动
      </el-button>
      <el-button @click="handleClose">
        我知道了
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { WarningFilled, InfoFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  message: {
    type: String,
    default: ''
  },
  gpuInfo: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const openDriverDownload = () => {
  window.open('https://www.nvidia.cn/Download/index.aspx?lang=cn', '_blank')
}

const handleClose = () => {
  visible.value = false
  emit('close')
}
</script>

<style scoped>
.cuda-warning-content {
  text-align: center;
  padding: 20px;
}

.warning-icon {
  color: #e6a23c;
  margin-bottom: 16px;
}

.cuda-warning-content h3 {
  font-size: 18px;
  color: #303133;
  margin-bottom: 12px;
}

.warning-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 20px;
  line-height: 1.6;
}

.info-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  text-align: left;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e4e7ed;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row .label {
  color: #909399;
  font-size: 14px;
}

.info-row .value {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}

.info-row .value.required {
  color: #e6a23c;
}

.action-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: #909399;
}

/* 暗色主题 */
.dark-theme .cuda-warning-content h3 {
  color: #e6edf3;
}

.dark-theme .warning-message {
  color: #8b949e;
}

.dark-theme .info-card {
  background: #161b22;
}

.dark-theme .info-row {
  border-bottom-color: #30363d;
}

.dark-theme .info-row .label {
  color: #8b949e;
}

.dark-theme .info-row .value {
  color: #e6edf3;
}
</style>
