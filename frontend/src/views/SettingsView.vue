<template>
  <div class="settings-container" :class="{ 'dark-theme': isDarkTheme }">
    <div class="settings-content">
      <div class="page-header">
        <h2 class="page-title">系统设置</h2>
      </div>

      <el-form :model="settingsStore.settings" label-position="top">
        <!-- 激活管理卡片 -->
        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Lock /></el-icon>
              <span>系统激活</span>
            </div>
          </template>

          <div class="activation-section">
            <div class="activation-status">
              <div class="status-row">
                <span class="status-label">激活状态：</span>
                <el-tag :type="activationStatus.isActivated ? 'success' : 'warning'" size="large">
                  {{ activationStatus.isActivated ? '已激活' : '未激活' }}
                </el-tag>
              </div>

              <div class="status-row" v-if="activationStatus.isActivated">
                <span class="status-label">激活类型：</span>
                <el-tag type="info" size="small">{{ formatLicenseType(activationStatus.licenseType) }}</el-tag>
              </div>

              <div class="status-row" v-if="activationStatus.isActivated">
                <span class="status-label">有效期至：</span>
                <span class="status-value">{{ formatExpiresAt(activationStatus.expiresAt) }}</span>
              </div>

              <div class="status-row" v-if="!activationStatus.isActivated">
                <span class="status-label">剩余配额：</span>
                <span class="status-value">{{ activationStatus.remainingQuota }} / {{ activationStatus.maxQuota }}</span>
              </div>

              <div class="status-row">
                <span class="status-label">机器码：</span>
                <div class="machine-code-wrapper">
                  <code class="machine-code">{{ activationStatus.machineCode }}</code>
                  <el-button text type="primary" size="small" @click="copyMachineCode">
                    <el-icon><CopyDocument /></el-icon>
                    复制
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 联系信息和价格信息 -->
            <div class="activation-info" v-if="!activationStatus.isActivated">
              <el-divider content-position="left">激活说明</el-divider>
              <div class="info-section">
                <p class="info-text sales-info">
                  免费版每天可以生成10条视频，个人使用已经完全足够，若需解锁工作室版请联系作者
                </p>
                <div class="price-info">
                  <p class="price-title">价格信息：</p>
                  <ul class="price-list">
                    <li>一年 <span class="price">69元</span></li>
                    <li>三年 <span class="price">128元</span></li>
                    <li>终身 <span class="price original">1280元</span> <span class="discount">限时特惠仅需 <span class="special-price">398元</span></span></li>
                  </ul>
                </div>
                <div class="contact-info">
                  <p class="contact-title">联系方式：</p>
                  <p class="contact-detail">微信：<span class="highlight">me-orzing</span> (13145981227)</p>
                </div>
              </div>
            </div>

            <div class="activation-actions">
              <el-button
                v-if="!activationStatus.isActivated"
                type="primary"
                @click="showActivationDialog"
              >
                <el-icon><Key /></el-icon>
                输入激活码
              </el-button>
              <el-button
                v-else
                type="info"
                plain
                @click="refreshActivationStatus"
                :loading="activationLoading"
              >
                <el-icon><Refresh /></el-icon>
                刷新状态
              </el-button>
            </div>
          </div>
        </el-card>

        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Key /></el-icon>
              <span>API Key 配置</span>
            </div>
          </template>

          <div class="form-grid">
            <el-form-item label="DeepSeek API Key" class="full-width">
              <el-input 
                v-model="settingsStore.settings.deepseek_api_key" 
                type="password" 
                show-password
                placeholder="输入 DeepSeek API Key"
              />
            </el-form-item>

            <el-form-item label="阿里云 API Key" class="full-width">
              <el-input
                v-model="settingsStore.settings.aliyun_api_key"
                type="password"
                show-password
                placeholder="输入阿里云 API Key"
              />
            </el-form-item>
          </div>

          <div class="card-footer">
            <el-button type="primary" @click="saveApiKeys" :loading="saving">
              <el-icon><Check /></el-icon>
              保存 API Key
            </el-button>
          </div>
        </el-card>

        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>模版配置</span>
            </div>
          </template>

          <div class="form-grid">
            <el-form-item label="单人提示词模版" class="full-width">
              <el-input
                v-model="settingsStore.settings.single_person_prompt_template"
                type="textarea"
                :rows="4"
                placeholder="根据主题{theme}生成单人讲解文案，包含开场、情绪标签、场景标签、结束"
              />
              <div class="form-hint">
                可用变量：{theme} - 主题内容
              </div>
            </el-form-item>

            <el-form-item label="双人提示词模版" class="full-width">
              <el-input
                v-model="settingsStore.settings.dual_person_prompt_template"
                type="textarea"
                :rows="4"
                placeholder="根据主题{theme}生成双人对话文案，包含开场、左边说话人、右边说话人、情绪标签、场景标签、结束"
              />
              <div class="form-hint">
                可用变量：{theme} - 主题内容
              </div>
            </el-form-item>

            <el-form-item label="封面生成提示词模版" class="full-width">
              <el-input
                v-model="settingsStore.settings.cover_prompt_template"
                type="textarea"
                :rows="3"
                placeholder="根据文案{summary}生成视频封面，风格简洁，突出主题"
              />
              <div class="form-hint">
                可用变量：{summary} - 文案摘要
              </div>
            </el-form-item>
          </div>

          <div class="card-footer">
            <el-button type="primary" @click="savePromptTemplates" :loading="saving">
              <el-icon><Check /></el-icon>
              保存提示词模版
            </el-button>
          </div>
        </el-card>

        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Setting /></el-icon>
              <span>默认参数配置</span>
            </div>
          </template>

          <div class="form-grid">
            <el-form-item label="HeyGEM 原始参数">
              <el-switch v-model="settingsStore.settings.heygem_original" />
              <span class="form-hint">开启后使用原始分辨率/帧率参数</span>
            </el-form-item>

            <el-form-item label="双人模式">
              <el-switch v-model="settingsStore.settings.dual_mode" />
              <span class="form-hint">开启后启用双人对话模式</span>
            </el-form-item>

            <el-form-item label="HeyGEM 推理批次" class="full-width">
              <el-slider
                v-model="settingsStore.settings.heygem_inference_steps"
                :min="4"
                :max="32"
                :step="1"
                show-stops
                :marks="{ 4: '4', 16: '16', 32: '32' }"
              />
              <div class="form-hint">推理批次影响生成质量与速度，默认 16</div>
            </el-form-item>

            <el-form-item label="IndexTTS 默认语速" class="full-width">
              <el-slider
                v-model="settingsStore.settings.tts_speed"
                :min="0.8"
                :max="1.2"
                :step="0.05"
                show-input
              />
              <div class="form-hint">语速范围 0.8-1.2，默认 1.0</div>
            </el-form-item>

            <el-form-item label="IndexTTS 默认情感权重" class="full-width">
              <el-slider
                v-model="settingsStore.settings.tts_emo_weight"
                :min="0"
                :max="0.8"
                :step="0.05"
                show-input
              />
              <div class="form-hint">情感权重范围 0-0.8，默认 0.4</div>
            </el-form-item>
          </div>

          <div class="card-footer">
            <el-button type="primary" @click="saveDefaultParams" :loading="saving">
              <el-icon><Check /></el-icon>
              保存默认参数
            </el-button>
          </div>
        </el-card>

        <!-- 服务状态卡片 -->
        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Monitor /></el-icon>
              <span>服务状态</span>
            </div>
          </template>

          <!-- 低显存模式开关 -->
          <div class="low-memory-mode-section">
            <div class="low-memory-mode-header">
              <span class="low-memory-mode-label">低显存模式</span>
              <el-switch
                v-model="lowMemoryMode"
                :loading="lowMemoryModeLoading"
                @change="handleLowMemoryModeChange"
              />
            </div>
            <p class="low-memory-mode-hint">
              开启后系统启动时不加载模型，任务执行时按需加载，任务完成后释放显存
            </p>
          </div>
        </el-card>

        <TagGroupManager />

        <EmotionTagManager />

        <!-- 激活对话框 -->
        <ActivationDialog
          v-model="activationDialogVisible"
          @activated="handleActivated"
        />

        <el-card class="settings-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Delete /></el-icon>
              <span>系统维护</span>
            </div>
          </template>

          <div class="form-grid">
            <el-form-item label="清理缓存" class="full-width">
              <div class="cache-info">
                <p>清理系统运行过程中产生的临时文件，包括：</p>
                <ul>
                  <li>任务执行中间文件</li>
                  <li>音频/视频处理临时文件</li>
                  <li>日志文件</li>
                </ul>
              </div>
              <el-button 
                type="danger" 
                @click="showClearCacheConfirm"
                :loading="clearingCache"
              >
                <el-icon><Delete /></el-icon>
                清理缓存
              </el-button>
            </el-form-item>
          </div>
        </el-card>
      </el-form>
    </div>

    <a href="https://deerflow.tech" target="_blank" class="deerflow-badge">✦ Deerflow</a>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Key, Document, Setting, Delete, Monitor, Lock, CopyDocument, Refresh
} from '@element-plus/icons-vue'
import { settingsApi, systemApi, licenseApi } from '@/services/api'
import { useSettingsStore } from '@/stores/settingsStore.js'
import TagGroupManager from '@/components/TagGroupManager.vue'
import EmotionTagManager from '@/components/EmotionTagManager.vue'
import ActivationDialog from '@/components/ActivationDialog.vue'

// 注入主题状态
const isDarkTheme = inject('isDarkTheme', ref(false))
const settingsStore = useSettingsStore()

const saving = ref(false)
const clearingCache = ref(false)

// 低显存模式
const lowMemoryMode = ref(false)
const lowMemoryModeLoading = ref(false)

// 激活相关
const activationDialogVisible = ref(false)
const activationLoading = ref(false)
const activationStatus = ref({
  isActivated: false,
  machineCode: '',
  remainingQuota: 0,
  maxQuota: 0,
  licenseType: '',
  expiresAt: null
})

// 获取系统配置
const fetchSystemConfig = async () => {
  try {
    const response = await systemApi.getConfig()
    lowMemoryMode.value = response.low_memory_mode
  } catch (error) {
    console.error('获取系统配置失败:', error)
  }
}

// 更新低显存模式
const handleLowMemoryModeChange = async (value) => {
  lowMemoryModeLoading.value = true
  try {
    await systemApi.updateConfig({ low_memory_mode: value })
    ElMessage.success(`低显存模式已${value ? '开启' : '关闭'}`)
  } catch (error) {
    ElMessage.error(`更新失败: ${error.response?.data?.detail || error.message}`)
    // 恢复原值
    await fetchSystemConfig()
  } finally {
    lowMemoryModeLoading.value = false
  }
}

// 使用computed获取settings，确保响应式更新
const settings = computed({
  get: () => settingsStore.settings,
  set: (value) => settingsStore.updateSettings(value)
})

const saveApiKeys = async () => {
  saving.value = true
  try {
    await settingsApi.updateApiKeys({
      deepseek_api_key: settingsStore.settings.deepseek_api_key,
      aliyun_api_key: settingsStore.settings.aliyun_api_key
    })
    ElMessage.success('API Key 配置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const savePromptTemplates = async () => {
  saving.value = true
  try {
    await settingsApi.updatePromptTemplates({
      single_person_prompt_template: settingsStore.settings.single_person_prompt_template,
      dual_person_prompt_template: settingsStore.settings.dual_person_prompt_template,
      cover_prompt_template: settingsStore.settings.cover_prompt_template
    })
    ElMessage.success('提示词模版已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const saveDefaultParams = async () => {
  saving.value = true
  try {
    await settingsApi.updateDefaultParams({
      heygem_original: settingsStore.settings.heygem_original,
      heygem_inference_steps: settingsStore.settings.heygem_inference_steps,
      dual_mode: settingsStore.settings.dual_mode,
      tts_speed: settingsStore.settings.tts_speed,
      tts_emo_weight: settingsStore.settings.tts_emo_weight
    })
    ElMessage.success('默认参数已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const showClearCacheConfirm = () => {
  ElMessageBox.confirm(
    '确定要清理所有缓存文件吗？此操作不可撤销。',
    '清理缓存确认',
    {
      confirmButtonText: '确定清理',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    clearCache()
  }).catch(() => {
    // 用户取消
  })
}

const clearCache = async () => {
  clearingCache.value = true
  try {
    const result = await settingsApi.clearCache()
    if (result.code === 200) {
      const data = result.data
      ElMessage.success(
        `清理完成！删除 ${data.deleted_files} 个文件，释放 ${data.deleted_size_mb} MB 空间`
      )
    } else {
      ElMessage.error(result.message || '清理失败')
    }
  } catch (error) {
    ElMessage.error('清理缓存失败: ' + (error.message || '未知错误'))
  } finally {
    clearingCache.value = false
  }
}

// 激活相关方法
const fetchActivationStatus = async () => {
  activationLoading.value = true
  try {
    const response = await licenseApi.getStatus()
    activationStatus.value = {
      isActivated: response.is_activated,
      machineCode: response.machine_code,
      remainingQuota: response.remaining_quota,
      maxQuota: response.max_quota,
      licenseType: response.license_type || '',
      expiresAt: response.expires_at || null
    }
  } catch (error) {
    console.error('获取激活状态失败:', error)
    ElMessage.error('获取激活状态失败')
  } finally {
    activationLoading.value = false
  }
}

// 格式化激活类型显示
const formatLicenseType = (type) => {
  const typeMap = {
    'yearly': '一年期',
    'three_year': '三年期',
    'lifetime': '终身'
  }
  return typeMap[type] || type || '未知'
}

// 格式化过期时间显示
const formatExpiresAt = (expiresAt) => {
  if (!expiresAt) return '永久有效'
  try {
    const date = new Date(expiresAt)
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  } catch {
    return expiresAt
  }
}

const showActivationDialog = () => {
  activationDialogVisible.value = true
}

const handleActivated = () => {
  fetchActivationStatus()
  ElMessage.success('系统已激活')
}

const refreshActivationStatus = () => {
  fetchActivationStatus()
}

const copyMachineCode = async () => {
  try {
    await navigator.clipboard.writeText(activationStatus.value.machineCode)
    ElMessage.success('机器码已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

onMounted(() => {
  settingsStore.fetchSettings()
  fetchSystemConfig()
  fetchActivationStatus()
})
</script>

<style scoped>
.settings-container {
  min-height: calc(100vh - 64px - 40px);
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 50%, #eef2f6 100%);
  transition: background 0.3s ease;
}

.dark-theme .settings-container {
  background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #0f0f23 100%);
}

.settings-content {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 32px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin: 0;
  transition: color 0.3s ease;
}

.dark-theme .page-title {
  color: #fff;
}

.settings-card {
  margin-bottom: 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.dark-theme .settings-card {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.settings-card :deep(.el-card__header) {
  background: rgba(64, 158, 255, 0.05);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  padding: 16px 20px;
  transition: all 0.3s ease;
}

.dark-theme .settings-card :deep(.el-card__header) {
  background: rgba(0, 217, 255, 0.05);
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.settings-card :deep(.el-card__body) {
  padding: 24px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  transition: color 0.3s ease;
}

.dark-theme .card-header {
  color: #fff;
}

.card-header .el-icon {
  font-size: 20px;
  color: #409EFF;
  transition: color 0.3s ease;
}

.dark-theme .card-header .el-icon {
  color: #00d9ff;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.form-grid .full-width {
  grid-column: 1 / -1;
}

.form-grid :deep(.el-form-item__label) {
  color: #606266;
  font-weight: 500;
  transition: color 0.3s ease;
}

.dark-theme .form-grid :deep(.el-form-item__label) {
  color: #a0aec0;
}

.form-grid :deep(.el-input__wrapper),
.form-grid :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: none;
  transition: all 0.3s ease;
}

.dark-theme .form-grid :deep(.el-input__wrapper),
.dark-theme .form-grid :deep(.el-textarea__inner) {
  background: rgba(0, 0, 0, 0.3);
  border-color: rgba(255, 255, 255, 0.1);
}

.form-grid :deep(.el-input__wrapper:hover),
.form-grid :deep(.el-textarea__inner:hover) {
  border-color: rgba(64, 158, 255, 0.5);
}

.dark-theme .form-grid :deep(.el-input__wrapper:hover),
.dark-theme .form-grid :deep(.el-textarea__inner:hover) {
  border-color: rgba(0, 217, 255, 0.5);
}

.form-grid :deep(.el-input__wrapper.is-focus),
.form-grid :deep(.el-textarea__inner:focus) {
  border-color: #409EFF;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.dark-theme .form-grid :deep(.el-input__wrapper.is-focus),
.dark-theme .form-grid :deep(.el-textarea__inner:focus) {
  border-color: #00d9ff;
  box-shadow: 0 0 0 2px rgba(0, 217, 255, 0.1);
}

.form-hint {
  color: #909399;
  font-size: 12px;
  margin-top: 6px;
  line-height: 1.4;
  transition: color 0.3s ease;
}

.dark-theme .form-hint {
  color: #718096;
}

.form-grid :deep(.el-slider__runway) {
  background: rgba(0, 0, 0, 0.1);
}

.dark-theme .form-grid :deep(.el-slider__runway) {
  background: rgba(255, 255, 255, 0.1);
}

.form-grid :deep(.el-slider__bar) {
  background: linear-gradient(90deg, #409EFF, #67c23a);
}

.dark-theme .form-grid :deep(.el-slider__bar) {
  background: linear-gradient(90deg, #00d9ff, #00ff88);
}

.form-grid :deep(.el-slider__button) {
  border-color: #409EFF;
  background: #409EFF;
}

.dark-theme .form-grid :deep(.el-slider__button) {
  border-color: #00d9ff;
  background: #00d9ff;
}

.form-grid :deep(.el-switch) {
  --el-switch-off-color: rgba(0, 0, 0, 0.2);
  --el-switch-on-color: #409EFF;
}

.dark-theme .form-grid :deep(.el-switch) {
  --el-switch-off-color: rgba(255, 255, 255, 0.1);
  --el-switch-on-color: #00d9ff;
}

.form-grid :deep(.el-input-number) {
  width: 140px;
}

.form-grid :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}

.card-footer {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: flex-end;
  transition: border-color 0.3s ease;
}

.dark-theme .card-footer {
  border-top-color: rgba(255, 255, 255, 0.08);
}

.card-footer .el-button {
  background: linear-gradient(135deg, #409EFF, #67c23a);
  border: none;
  font-weight: 600;
}

.dark-theme .card-footer .el-button {
  background: linear-gradient(135deg, #00d9ff, #00ff88);
}

.card-footer .el-button:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.cache-info {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.dark-theme .cache-info {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.05);
}

.cache-info p {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 14px;
}

.dark-theme .cache-info p {
  color: #a0aec0;
}

.cache-info ul {
  margin: 0;
  padding-left: 20px;
  color: #909399;
  font-size: 13px;
}

.dark-theme .cache-info ul {
  color: #718096;
}

.cache-info li {
  margin: 4px 0;
}

/* 低显存模式开关样式 */
.low-memory-mode-section {
  margin-bottom: 8px;
}

.low-memory-mode-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.low-memory-mode-label {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.dark-theme .low-memory-mode-label {
  color: #fff;
}

.low-memory-mode-hint {
  margin: 0;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}

.dark-theme .low-memory-mode-hint {
  color: #718096;
}

/* 激活部分样式 */
.activation-section {
  padding: 8px 0;
}

.activation-status {
  margin-bottom: 20px;
}

.status-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.status-row:last-child {
  margin-bottom: 0;
}

.status-label {
  font-weight: 500;
  color: #606266;
  min-width: 80px;
}

.dark-theme .status-label {
  color: #a0aec0;
}

.status-value {
  color: #303133;
  font-weight: 600;
}

.dark-theme .status-value {
  color: #fff;
}

.machine-code-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.machine-code {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  letter-spacing: 1px;
  background: rgba(0, 0, 0, 0.05);
  padding: 6px 12px;
  border-radius: 4px;
  color: #303133;
}

.dark-theme .machine-code {
  background: rgba(255, 255, 255, 0.08);
  color: #00d9ff;
}

.activation-actions {
  margin-top: 16px;
}

/* 激活信息样式 */
.activation-info {
  margin-top: 16px;
}

.activation-info :deep(.el-divider__text) {
  color: #606266;
  font-size: 14px;
}

.dark-theme .activation-info :deep(.el-divider__text) {
  color: #a0aec0;
}

.info-section {
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.dark-theme .info-section {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.05);
}

.info-text {
  margin: 0 0 16px 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.dark-theme .info-text {
  color: #a0aec0;
}

.sales-info {
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(0, 0, 0, 0.1);
}

.dark-theme .sales-info {
  border-bottom-color: rgba(255, 255, 255, 0.1);
}

.price-info,
.contact-info {
  margin-bottom: 12px;
}

.contact-info {
  margin-bottom: 0;
}

.price-title,
.contact-title {
  margin: 0 0 8px 0;
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.dark-theme .price-title,
.dark-theme .contact-title {
  color: #fff;
}

.price-list {
  margin: 0;
  padding-left: 20px;
  list-style: none;
}

.price-list li {
  margin: 6px 0;
  color: #606266;
  font-size: 14px;
  position: relative;
}

.price-list li::before {
  content: '•';
  position: absolute;
  left: -12px;
  color: #409EFF;
}

.dark-theme .price-list li {
  color: #a0aec0;
}

.dark-theme .price-list li::before {
  color: #00d9ff;
}

.price {
  font-weight: 600;
  color: #409EFF;
}

.dark-theme .price {
  color: #00d9ff;
}

.price.original {
  color: #909399;
  text-decoration: line-through;
}

.dark-theme .price.original {
  color: #718096;
}

.discount {
  color: #e6a23c;
  font-size: 13px;
}

.dark-theme .discount {
  color: #f0c040;
}

.special-price {
  font-weight: 700;
  color: #f56c6c;
  font-size: 16px;
}

.dark-theme .special-price {
  color: #ff6b6b;
}

.contact-detail {
  margin: 0;
  color: #606266;
  font-size: 14px;
}

.dark-theme .contact-detail {
  color: #a0aec0;
}

.highlight {
  font-weight: 600;
  color: #409EFF;
}

.dark-theme .highlight {
  color: #00d9ff;
}

.deerflow-badge {
  position: fixed;
  bottom: 20px;
  right: 20px;
  color: rgba(0, 0, 0, 0.3);
  text-decoration: none;
  font-size: 12px;
  transition: all 0.3s;
}

.dark-theme .deerflow-badge {
  color: rgba(255, 255, 255, 0.3);
}

.deerflow-badge:hover {
  color: rgba(0, 0, 0, 0.6);
}

.dark-theme .deerflow-badge:hover {
  color: rgba(255, 255, 255, 0.6);
}

@media (max-width: 768px) {
  .settings-container {
    padding: 16px;
  }
  
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
