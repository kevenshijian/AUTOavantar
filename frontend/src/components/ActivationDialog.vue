<template>
  <el-dialog
    v-model="visible"
    title="系统激活"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
  >
    <div v-if="!isActivated" class="activation-form">
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span>机器码：</span>
            <el-button text type="primary" @click="copyMachineCode">
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>
        </template>
        <code style="font-size: 16px; letter-spacing: 2px;">{{ machineCode }}</code>
      </el-alert>

      <el-form :model="form" label-width="100px">
        <el-form-item label="激活码：">
          <el-input
            v-model="form.activationCode"
            placeholder="请输入激活码"
            clearable
          />
        </el-form-item>
      </el-form>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        style="margin-top: 10px"
      />
    </div>

    <div v-else class="activation-success">
      <el-result
        icon="success"
        title="激活成功"
        :sub-title="`剩余配额：${remainingQuota}/${maxQuota}`"
      />
    </div>

    <template #footer>
      <span v-if="!isActivated" class="dialog-footer">
        <el-button @click="handleClose">稍后激活</el-button>
        <el-button type="primary" @click="handleActivate" :loading="loading">
          激活
        </el-button>
      </span>
      <span v-else class="dialog-footer">
        <el-button type="primary" @click="handleClose">开始使用</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument } from '@element-plus/icons-vue'
import { licenseApi } from '@/services/api'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'activated'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const machineCode = ref('')
const isActivated = ref(false)
const remainingQuota = ref(0)
const maxQuota = ref(0)
const errorMessage = ref('')

const form = ref({
  activationCode: ''
})

const fetchStatus = async () => {
  try {
    // licenseApi.getStatus() 返回的已经是 response.data（经过拦截器处理）
    const response = await licenseApi.getStatus()
    machineCode.value = response.machine_code
    isActivated.value = response.is_activated
    remainingQuota.value = response.remaining_quota
    maxQuota.value = response.max_quota
  } catch (error) {
    console.error('获取许可证状态失败:', error)
  }
}

const handleActivate = async () => {
  if (!form.value.activationCode.trim()) {
    errorMessage.value = '请输入激活码'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    // licenseApi.activate() 返回的已经是 response.data（经过拦截器处理）
    const response = await licenseApi.activate(form.value.activationCode.trim())

    if (response.success) {
      isActivated.value = true
      remainingQuota.value = response.remaining_quota
      maxQuota.value = response.max_quota
      ElMessage.success('激活成功！')
      emit('activated')
    } else {
      errorMessage.value = response.message
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || '激活失败，请检查激活码'
  } finally {
    loading.value = false
  }
}

const copyMachineCode = async () => {
  try {
    await navigator.clipboard.writeText(machineCode.value)
    ElMessage.success('机器码已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const handleClose = () => {
  visible.value = false
}

onMounted(() => {
  fetchStatus()
})
</script>

<style scoped>
.activation-form {
  padding: 10px 0;
}

.activation-success {
  padding: 20px 0;
}

code {
  background: #f5f7fa;
  padding: 5px 10px;
  border-radius: 4px;
  display: block;
  margin-top: 10px;
}
</style>
