<template>
  <div class="home">
    <div class="hero">
      <h1>AUTOavantar</h1>
      <p class="subtitle">数字人视频生成系统</p>
      <p class="description">
        基于先进的 AI 技术，快速生成高质量的数字人视频。
        支持文案自动生成、语音合成、视频合成等全流程自动化处理。
      </p>
    </div>

    <div class="features">
      <div class="feature-card">
        <div class="feature-icon">🎬</div>
        <h3>视频预处理</h3>
        <p>自动进行人脸检测、对齐、脱帽等预处理，确保视频质量</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">✍️</div>
        <h3>智能文案</h3>
        <p>基于 LLM 智能生成视频文案，或直接输入自定义文案</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">🎙️</div>
        <h3>语音合成</h3>
        <p>使用先进的 TTS 技术，将文案转换为自然流畅的语音</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">🤖</div>
        <h3>数字人生成</h3>
        <p>基于 HeyGen 技术，生成高质量的数字人视频</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">🎵</div>
        <h3>后期处理</h3>
        <p>智能降噪、字幕生成、BGM 合成，打造专业级视频</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">📊</div>
        <h3>任务管理</h3>
        <p>实时任务状态监控，任务队列管理，断点续传</p>
      </div>
    </div>

    <div class="quick-actions">
      <router-link to="/tasks" class="action-btn primary">
        开始使用
      </router-link>
      <router-link to="/materials" class="action-btn secondary">
        查看素材库
      </router-link>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
}

.hero {
  text-align: center;
  margin-bottom: 60px;
}

.hero h1 {
  font-size: 48px;
  color: #1976d2;
  margin-bottom: 10px;
}

.subtitle {
  font-size: 24px;
  color: #666;
  margin-bottom: 20px;
}

.description {
  font-size: 16px;
  color: #999;
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 60px;
}

.feature-card {
  background-color: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 20px;
}

.feature-card h3 {
  font-size: 20px;
  color: #333;
  margin-bottom: 10px;
}

.feature-card p {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.quick-actions {
  display: flex;
  justify-content: center;
  gap: 20px;
}

.action-btn {
  padding: 15px 40px;
  border-radius: 8px;
  font-size: 16px;
  text-decoration: none;
  transition: all 0.3s;
}

.action-btn.primary {
  background-color: #2196f3;
  color: white;
}

.action-btn.primary:hover {
  background-color: #1976d2;
}

.action-btn.secondary {
  background-color: white;
  color: #2196f3;
  border: 2px solid #2196f3;
}

.action-btn.secondary:hover {
  background-color: #e3f2fd;
}
</style>
