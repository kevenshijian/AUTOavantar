# IndexTTS API Server

基于 [IndexTTS-2](https://github.com/index-tts/index-tts) 模型的 REST API 语音合成服务，完全替代原有的 Gradio/cy_app 接口。

## 快速启动

### 前置条件

- Python 3.10+
- NVIDIA GPU（建议 8GB+ 显存）
- 模型文件已放置在 `checkpoints/` 目录
- 预设音色 `.pt` 文件已放置在 `voices/` 目录

### 启动服务

```bash
cd index-tts-2

# 方式一：使用启动脚本
启动API服务.bat

# 方式二：命令行启动
python -m uvicorn api_server.main:app --host 0.0.0.0 --port 7860
```

服务启动后：
- API 文档：http://localhost:7860/docs
- 健康检查：http://localhost:7860/api/v1/health

## API 接口

### 1. 健康检查

```
GET /api/v1/health
```

返回模型状态、GPU 信息、队列统计等。

### 2. 配置查询

```
GET /api/v1/config
```

返回推理配置、默认参数等。

### 3. TTS 合成

```
POST /api/v1/tts/synthesize
Content-Type: application/json

{
  "text": "要合成的文本",
  "voice_name": "苏瑶",
  "emotion_vec": {"vec1": 0.8, "vec7": 0.5},
  "inference_mode": "fast",
  "temperature": 1.0,
  "top_p": 0.8,
  "top_k": 30,
  "num_beams": 3
}
```

响应 (202)：
```json
{
  "task_id": "a1b2c3d4e5f6a7b8",
  "status": "pending",
  "queue_position": 1
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | 是 | - | 合成文本（1-1000 字符） |
| `voice_name` | 二选一 | - | 预设音色名称 |
| `reference_audio` | 二选一 | - | 自定义音频文件路径 |
| `emotion` | 否 | - | 情绪标签（如"高兴"），通过映射表翻译 |
| `emotion_vec` | 否 | - | 情感向量（`{"vec1": 0.8, ...}`），优先级高于 emotion |
| `inference_mode` | 否 | `fast` | 推理模式：`fast` 或 `standard` |
| `temperature` | 否 | `1.0` | 生成温度（0.1-2.0） |
| `top_p` | 否 | `0.8` | Top-p 采样（0-1.0） |
| `top_k` | 否 | `30` | Top-k 采样（1-100） |
| `num_beams` | 否 | `3` | Beam search 数量（1-10） |

### 4. 任务查询

```
GET /api/v1/tasks/{task_id}
```

```json
{
  "task_id": "a1b2c3d4e5f6a7b8",
  "status": "completed",
  "audio_url": "/api/v1/audio/a1b2c3d4e5f6a7b8.wav",
  "duration_sec": 5.2,
  "inference_time_sec": 3.1,
  "created_at": "2026-04-06T10:00:00Z",
  "completed_at": "2026-04-06T10:00:03Z"
}
```

### 5. 队列状态

```
GET /api/v1/tasks/{task_id}/status
```

### 6. 音色管理

```
GET  /api/v1/voices                    # 列出预设音色
POST /api/v1/voices                    # 上传新音色（audio_file + name）
POST /api/v1/voices/upload             # 上传临时音色（仅提取特征）
```

### 7. 音频文件

```
GET /api/v1/audio/{filename}           # 直接访问合成音频
```

## 配置

配置文件：`api_server/config.yaml`

```yaml
server:
  host: "0.0.0.0"
  port: 7860
  reload: false

model:
  cfg_path: "checkpoints/config.yaml"
  model_dir: "checkpoints"
  is_fp16: true
  device: null          # null 自动检测

queue:
  max_size: 10
  task_timeout_sec: 600

audio:
  output_dir: "outputs"
  retention_hours: 24

emotion:
  mapping_file: "emotion_mapping.yaml"
```

环境变量覆盖（前缀 `INDEXTTS_API_`）：

```bash
INDEXTTS_API_SERVER_PORT=8080
INDEXTTS_API_MODEL_IS_FP16=false
```

## 情感控制

### 方式一：情绪标签

通过 `emotion_mapping.yaml` 配置文件定义情绪标签到 vec1-vec8 的映射：

```yaml
高兴:
  vec1: 0.8
  vec7: 0.5
悲伤:
  vec3: 0.8
```

使用：
```json
{"text": "今天真开心", "voice_name": "苏瑶", "emotion": "高兴"}
```

### 方式二：情感向量直传

直接传入 vec1-vec8 权重值（优先级高于 emotion 标签）：

```json
{"text": "今天真开心", "voice_name": "苏瑶", "emotion_vec": {"vec1": 0.8, "vec7": 0.5}}
```

## 快速请求示例

### cURL

```bash
# 健康检查
curl -X GET "http://localhost:7860/api/v1/health"

# 基础合成
curl -X POST "http://localhost:7860/api/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，欢迎使用 IndexTTS。", "voice_name": "苏瑶"}'

# 带情感合成
curl -X POST "http://localhost:7860/api/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text": "太开心了！", "voice_name": "苏瑶", "emotion": "高兴"}'

# 情感向量直传（更精确控制）
curl -X POST "http://localhost:7860/api/v1/tts/synthesize" \
  -H "Content-Type: application/json" \
  -d '{"text": "我很难过...", "voice_name": "苏瑶", "emotion_vec": {"vec1": 0.2, "vec3": 0.8}}'

# 查询任务状态
curl -X GET "http://localhost:7860/api/v1/tasks/{task_id}"

# 列出可用音色
curl -X GET "http://localhost:7860/api/v1/voices"
```

### Python

```python
import requests

API = "http://localhost:7860/api/v1"

# 1. 健康检查
health = requests.get(f"{API}/health").json()
print(f"模型已加载: {health['model_loaded']}")

# 2. 获取音色列表
voices = requests.get(f"{API}/voices").json()["voices"]
voice_name = voices[0]["name"]

# 3. 提交合成任务
result = requests.post(
    f"{API}/tts/synthesize",
    json={"text": "你好，这是一段测试语音。", "voice_name": voice_name},
).json()

task_id = result["task_id"]
print(f"任务已提交: {task_id}")

# 4. 轮询等待完成
import time
while True:
    task = requests.get(f"{API}/tasks/{task_id}").json()
    if task["status"] == "completed":
        print(f"音频: {task['audio_url']}")
        break
    time.sleep(1)
```

### Python (异步 aiohttp)

```python
import asyncio
import aiohttp

API = "http://localhost:7860/api/v1"

async def synthesize_text(text: str, voice_name: str):
    async with aiohttp.ClientSession() as session:
        # 提交任务
        async with session.post(
            f"{API}/tts/synthesize",
            json={"text": text, "voice_name": voice_name},
        ) as resp:
            task_id = (await resp.json())["task_id"]

        # 轮询等待完成
        while True:
            await asyncio.sleep(1)
            async with session.get(f"{API}/tasks/{task_id}") as resp:
                result = await resp.json()
                if result["status"] == "completed":
                    return result["audio_url"]

# 并发合成多段文本
texts = ["第一段。", "第二段。", "第三段。"]
results = await asyncio.gather(*[synthesize_text(t, "苏瑶") for t in texts])
```

## 测试

```bash
cd index-tts-2

# 运行集成测试（需先启动服务）
python api_server/test_api_server.py --host http://localhost:7860

# 运行 API 示例脚本
python api_server/api_examples.py --list-curl        # 列出所有 cURL 示例
python api_server/api_examples.py --example basic    # 运行基础示例
python api_server/api_examples.py --run-all          # 运行完整测试套件
```

## 项目结构

```
api_server/
├── __init__.py
├── main.py              # FastAPI 入口 + lifespan
├── config.py            # 配置管理（YAML + 环境变量）
├── config.yaml          # 默认配置
├── models/
│   ├── tts.py           # TTS 请求/响应模型
│   ├── voice.py         # 音色数据模型
│   ├── task.py          # 任务状态模型
│   └── system.py        # 系统监控模型
├── routers/
│   ├── tts.py           # TTS 合成路由
│   ├── tasks.py         # 任务查询路由
│   ├── voices.py        # 音色管理路由
│   └── system.py        # 系统监控路由
├── services/
│   ├── tts_engine.py    # TTS 推理引擎（model_v2 + BigVGAN）
│   ├── task_queue.py    # 异步任务队列
│   ├── audio_service.py # 音频文件服务
│   ├── voice_manager.py # 音色管理服务
│   └── emotion_mapping.py  # 情绪映射服务
└── test_api_server.py   # 集成测试
```

## 版本历史

- **v0.2.0** — 功能完善：情感向量控制、增强系统监控、优雅关闭、定期清理
- **v0.1.0** — MVP：核心 TTS 合成、任务队列、音色管理、基础监控
