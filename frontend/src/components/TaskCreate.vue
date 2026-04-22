<template>
  <div class="task-create">
    <h2>创建新任务</h2>
    
    <form @submit.prevent="handleSubmit">
      <div class="form-group">
        <label>任务名称 *</label>
        <input 
          v-model="formData.name"
          type="text"
          required
          placeholder="输入任务名称"
        />
      </div>

      <div class="form-group">
        <label>源视频 *</label>
        <VideoUploader 
          @uploaded="handleVideoUploaded"
          @error="handleUploadError"
        />
        <input 
          v-model="formData.source_video_path"
          type="hidden"
          required
        />
      </div>

      <div class="form-group">
        <label>内容输入方式</label>
        <div class="radio-group">
          <label class="radio-label">
            <input 
              v-model="formData.use_llm_generate"
              type="radio"
              :value="true"
            />
            使用主题（AI 生成文案）
          </label>
          <label class="radio-label">
            <input 
              v-model="formData.use_llm_generate"
              type="radio"
              :value="false"
            />
            直接输入文案
          </label>
        </div>
      </div>

      <div v-if="formData.use_llm_generate" class="form-group">
        <label>主题</label>
        <input 
          v-model="formData.topic"
          type="text"
          placeholder="输入视频主题，AI 将自动生成文案"
        />
      </div>

      <div v-else class="form-group">
        <label>文案文本</label>
        <textarea 
          v-model="formData.script_text"
          rows="5"
          placeholder="输入要生成的文案内容"
        ></textarea>
      </div>

      <div class="form-group">
        <label>语音配置</label>
        <div class="config-row">
          <div class="config-item">
            <label>语速</label>
            <input 
              v-model.number="formData.tts_speed"
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
            />
            <span>{{ formData.tts_speed }}</span>
          </div>
          <div class="config-item">
            <label>情感权重</label>
            <input 
              v-model.number="formData.tts_emo_weight"
              type="range"
              min="0.1"
              max="1.2"
              step="0.1"
            />
            <span>{{ formData.tts_emo_weight }}</span>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>后期处理</label>
        <div class="checkbox-group">
          <label class="checkbox-label">
            <input 
              v-model="formData.enable_postprocess"
              type="checkbox"
            />
            启用后期处理
          </label>
          <label class="checkbox-label">
            <input 
              v-model="formData.enable_denoise"
              type="checkbox"
            />
            开启降噪
          </label>
          <label class="checkbox-label">
            <input 
              v-model="formData.enable_subtitle"
              type="checkbox"
            />
            添加字幕
          </label>
          <label class="checkbox-label">
            <input 
              v-model="formData.enable_bgm"
              type="checkbox"
            />
            添加 BGM
          </label>
          <label class="checkbox-label">
            <input 
              v-model="formData.enable_cover"
              type="checkbox"
            />
            生成封面
          </label>
        </div>
      </div>

      <div v-if="formData.enable_bgm" class="form-group">
        <label>BGM 音量</label>
        <input 
          v-model.number="formData.bgm_volume"
          type="range"
          min="0"
          max="1"
          step="0.1"
        />
        <span>{{ (formData.bgm_volume * 100).toFixed(0) }}%</span>
      </div>

      <div class="form-actions">
        <button type="submit" class="submit-btn" :disabled="isSubmitting">
          {{ isSubmitting ? '创建中...' : '创建任务' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import VideoUploader from './VideoUploader.vue'

const emit = defineEmits(['created', 'error'])

const formData = reactive({
  name: '',
  source_video_path: '',
  use_llm_generate: true,
  script_text: '',
  topic: '',
  tts_speed: 1.0,
  tts_emo_weight: 0.8,
  enable_postprocess: true,
  enable_denoise: true,
  enable_subtitle: true,
  enable_bgm: true,
  bgm_volume: 0.3,
  enable_cover: false
})

const isSubmitting = ref(false)

const handleVideoUploaded = (data) => {
  formData.source_video_path = data.file_path
}

const handleUploadError = (error) => {
  emit('error', error)
}

const handleSubmit = async () => {
  if (!formData.source_video_path) {
    emit('error', '请上传源视频')
    return
  }

  if (formData.use_llm_generate && !formData.topic) {
    emit('error', '请输入视频主题')
    return
  }

  if (!formData.use_llm_generate && !formData.script_text) {
    emit('error', '请输入文案文本')
    return
  }

  isSubmitting.value = true

  try {
    const submitData = { ...formData }
    
    if (submitData.use_llm_generate) {
      delete submitData.script_text
    } else {
      delete submitData.topic
    }

    emit('created', submitData)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.task-create {
  background-color: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

h2 {
  margin: 0 0 20px 0;
  font-size: 24px;
  color: #333;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  color: #333;
}

.form-group input[type="text"],
.form-group textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group textarea {
  resize: vertical;
  font-family: inherit;
}

.radio-group,
.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radio-label,
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: normal;
  cursor: pointer;
}

.config-row {
  display: flex;
  gap: 20px;
}

.config-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.config-item label {
  min-width: 80px;
  font-weight: normal;
}

.config-item input[type="range"] {
  flex: 1;
}

.form-actions {
  margin-top: 30px;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background-color: #2196f3;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.submit-btn:hover:not(:disabled) {
  background-color: #1976d2;
}

.submit-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.dark-theme .task-create {
  background: #141414;
  color: #ffffff;
}

.dark-theme h2 {
  color: #ffffff;
}

.dark-theme h3 {
  color: #e0e0e0;
}

.dark-theme .config-group {
  background: #1f1f1f;
  border-color: #303030;
}

.dark-theme input[type="text"],
.dark-theme textarea,
.dark-theme select {
  background: #262626;
  border-color: #424242;
  color: #ffffff;
}

.dark-theme input[type="text"]::placeholder,
.dark-theme textarea::placeholder {
  color: #616161;
}

.dark-theme input[type="text"]:focus,
.dark-theme textarea:focus,
.dark-theme select:focus {
  border-color: #3b82f6;
}

.dark-theme .config-item label {
  color: #bdbdbd;
}
</style>
