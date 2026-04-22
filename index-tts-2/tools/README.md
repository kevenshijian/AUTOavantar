# 语音增强 GTCRN 工具箱 - 代码功能文档

## 项目概述

这是一个基于 PyTorch 的语音增强（Speech Enhancement）工具箱，核心算法是 **GTCRN (ShuffleNetV2 + SFE + TRA + 2 DPGRNN)**。该项目的主要功能是通过深度学习模型对语音信号进行降噪处理，特别针对实时流式语音增强场景进行了优化。

---

## 核心文件功能说明

### 1. `gtcrn.py` (主模型实现)

**功能**: 定义了完整的 GTCRN 网络架构，这是一个用于语音增强的轻量级深度学习模型。

**主要组件**:

| 类名 | 功能描述 |
|------|----------|
| **ERB** | 模拟人耳听觉特性，将频谱转换为 ERB 频带（Equivalent Rectangular Bandwidth） |
| **SFE** | 子带特征提取模块，使用 unfold 操作提取相邻频带特征 |
| **TRA** | 时序循环注意力模块，使用 GRU 计算时域注意力权重 |
| **ConvBlock** | 基础卷积块，包含卷积、批归一化和激活函数 |
| **GTConvBlock** | 分组时序卷积块，结合深度可分离卷积和时序注意力 |
| **GRNN** | 分组 RNN，将输入分为两路独立处理 |
| **DPGRNN** | 分组双路径 RNN，包含 intra-RNN（频域）和 inter-RNN（时域） |
| **Encoder** | 5层编码器，逐级下采样特征 |
| **Decoder** | 5层解码器，逐级上采样并使用跳跃连接 |
| **Mask** | 复数比率掩码，对语音频谱进行增强 |

**模型特点**:
- 超轻量级：仅 33.0 MMACs，23.67 K 参数
- 因果性设计：可用于实时流式处理
- 支持多种硬件后端（CUDA/XPU/MPS）

---

### 2. `gpu_check.py` (硬件检测工具)

**功能**: 检测系统中可用的 PyTorch 硬件加速设备

**主要功能**:
- 检测 NVIDIA CUDA / AMD ROCm 设备
- 检测 Intel XPU 设备
- 检测 Apple MPS 设备
- 打印设备名称和数量
- 自动切换 CPU/GPU 模式提示

**使用示例**:
```python
python gpu_check.py
```

---

### 3. `stream/` 目录 (流式处理模块)

#### `stream/gtcrn.py` (流式模型实现)

**功能**: 将主模型改造为支持流式处理的版本

**主要组件**:

| 类名 | 功能描述 |
|------|----------|
| **StreamConv1d** | 支持缓存机制的一维卷积层 |
| **StreamConv2d** | 支持缓存机制的二维卷积层 |
| **StreamConvTranspose2d** | 支持缓存机制的二维转置卷积层 |
| **StreamTRA** | 带缓存的时序注意力模块 |
| **StreamGTConvBlock** | 支持缓存更新的卷积块 |
| **StreamEncoder** | 带缓存管理的编码器 |
| **StreamDecoder** | 带缓存管理的解码器 |
| **StreamGTCRN** | 完整的流式 GTCRN 模型 |

**关键特性**:
- 维护 `conv_cache`（卷积缓存）和 `tra_cache`（注意力缓存）
- 每次处理一帧（frame-by-frame），适合实时流式场景
- 可导出为 ONNX 模型用于部署
- 支持 `inter_cache` 用于 RNN 的时序状态传递

**输入输出格式**:
```python
# 输入
spec: (B, F, T, 2) = (1, 257, 1, 2)  # 当前帧频谱
conv_cache: (2, B, C, 8(kT-1), F)    # 卷积缓存
tra_cache: (2, 3, 1, B, C)           # 注意力缓存
inter_cache: (2, 1, BF, C)           # RNN 交互缓存

# 输出
spec_enh: 增强后的频谱
conv_cache_out: 更新后的卷积缓存
tra_cache_out: 更新后的注意力缓存
inter_cache_out: 更新后的 RNN 缓存
```

---

#### `stream/modules/convolution.py` (流式卷积层)

**功能**: 提供支持流式推理的卷积层实现

**主要类**:

##### `StreamConv1d`
- 一维流式卷积，维护输入序列的缓存
- 输入: `x: [bs, C, T_size]`, `cache: [bs, C, T_size-1]`
- 用于处理时间维度的连续数据

##### `StreamConv2d`
- 二维流式卷积，用于时频域处理
- 输入: `x: [bs, C, 1, F]`, `cache: [bs, C, T_size-1, F]`
- 仅支持因果 Padding（T 方向无 padding）

##### `StreamConvTranspose2d`
- 二维流式转置卷积（反卷积），用于解码器
- 使用 Weight Time Reversal 技术实现因果转置卷积
- 支持 F 方向的上采样（stride > 1）

**设计原则**:
- 所有卷积层都采用因果 Padding（只向前补零）
- 每次前向传播返回输出和更新后的缓存
- 缓存机制确保时序连续性

---

#### `stream/modules/convert.py` (模型转换工具)

**功能**: 将 offline 模型转换为 stream 模型

**主要函数**:
```python
def convert_to_stream(stream_model, model):
    """
    将预训练的 offline 模型权重复制到流式模型
    """
```

**转换逻辑**:
1. 直接复制同名键的权重
2. 处理 `Conv1d.` 和 `Conv2d.` 前缀的键
3. 特别处理转置卷积的权重翻转（实现 ConvTranspose2d 的因果版本）
   - 权重需要进行维度置换和翻转操作

---

#### `stream/modules/__init__.py`

**功能**: 模块初始化文件（空文件）

---

### 4. `i18n/` 目录 (国际化支持)

#### `i18n/i18n.py`

**功能**: 提供国际化（i18n）支持类

**主要类**:
```python
class I18nAuto:
    def __init__(self, language=None):  # 初始化，自动检测语言
    def __call__(self, key):            # 键值查询
    def __repr__(self):                 # 返回当前语言
```

**功能说明**:
- 支持语言自动检测（基于系统 locale）
- 支持中英文切换（zh_CN / en_US）
- 使用 `__call__` 方法实现键值查询
- 语言文件不存在时自动回退到英文

**使用示例**:
```python
from i18n import I18nAuto
i18n = I18nAuto(language='zh_CN')
print(i18n("生成语音"))  # 输出: 生成语音
```

---

#### `i18n/scan_i18n.py`

**功能**: 扫描代码中的 i18n 字符串并更新翻译文件

**主要函数**:

| 函数 | 描述 |
|------|------|
| `extract_i18n_strings(node)` | 递归提取 AST 节点中的 i18n 字符串 |
| `scan_i18n_strings()` | 扫描所有 Python 文件，提取 i18n 字符串 |
| `update_i18n_json(json_file, standard_keys)` | 更新翻译文件：补充缺失键、删除冗余键、检查重复值 |

**功能特点**:
- 使用 AST 解析 Python 文件，提取 `i18n()` 函数调用
- 自动填充缺少的翻译键（默认语言键值相同，其他语言标记为 `#!键名`）
- 检测并报告未翻译内容
- 检测重复的翻译值（可能导致翻译错误）
- 按优先级排序翻译键

---

#### `i18n/locale/` (翻译文件)

**文件列表**:

| 文件 | 说明 |
|------|------|
| `en_US.json` | 英文翻译（作为基准语言） |
| `zh_CN.json` | 中文翻译 |

**主要翻译内容**:
- UI 界面文本（按钮、标签）
- 参数设置说明
- 错误提示信息
- 功能描述文本

---

### 5. ONNX 模型文件 (`stream/onnx_models/`)

| 文件名 | 说明 |
|--------|------|
| `gtcrn.onnx` | 导出的流式 GTCRN ONNX 模型 |
| `gtcrn_simple.onnx` | 简化后的 ONNX 模型（通过 onnx-simplifier 优化） |
| `model_trained_on_dns3.tar` | 在 DNS3 数据集上训练的模型权重 |
| `model_trained_on_vctk.tar` | 在 VCTK 数据集上训练的模型权重 |

---

### 6. 音频测试文件 (`stream/test_wavs/`)

| 文件名 | 说明 |
|--------|------|
| `mix.wav` | 混合语音（含噪声）- 测试输入 |
| `enh.wav` | 离线处理后的增强语音 |
| `enh_stream.wav` | 流式处理后的增强语音 |
| `enh_onnx.wav` | ONNX 推理后的增强语音 |

---

## 模型工作流程

### 离线处理流程

```
原始语音 (时域)
    ↓
STFT (短时傅里叶变换)
    ↓
复数频谱 (B, F, T, 2)
    ↓
    ├─ ERB 变换: (B, 3, T, 129)
    ├─ SFE 特征提取: (B, 9, T, 129)
    ├─ Encoder (5层): (B, 16, T, 33)
    ├─ DPGRNN1 (双路径 RNN)
    ├─ DPGRNN2 (双路径 RNN)
    ├─ Decoder (5层) + 跳跃连接
    └─ ERB 逆变换
    ↓
复数掩码 (Complex Ratio Mask)
    ↓
ISTFT (逆短时傅里叶变换)
    ↓
增强语音 (时域)
```

### 流式处理流程

```
实时音频流
    ↓
分帧处理（每次一帧）
    ↓
读取缓存 + 当前帧输入
    ↓
    ├─ 卷积层: 输出 + 更新 conv_cache
    ├─ 注意力: 输出 + 更新 tra_cache
    └─ RNN: 输出 + 更新 inter_cache
    ↓
输出当前帧增强结果
    ↓
累积输出到完整音频
```

---

## 性能特点

| 指标 | 数值 |
|------|------|
| **计算复杂度** | 33.0 MMACs（百万次乘加运算） |
| **参数量** | 23.67 K（千参数） |
| **实时因子 (RTF)** | < 0.01（可在 CPU 上实时运行） |
| **单帧延迟** | 约 0.5-1ms（CPU） |
| **输入帧长** | 256 samples（16ms at 16kHz） |
| **输入频点** | 257 (nfft=512) |

---

## 应用场景

1. **语音增强**: 降噪、回声消除、痉挛声抑制
2. **实时通话**: 视频会议、在线语音、电话会议
3. **语音识别预处理**: 提高 ASR 准确率
4. **嵌入式设备**: 低功耗语音处理（树莓派等）
5. **音频处理工具**: 音乐、播客后期处理

---

## 使用示例

### 离线推理
```python
from gtcrn import GTCRN
import soundfile as sf
import torch

# 加载模型
model = GTCRN().eval()
model.load_state_dict(torch.load('onnx_models/model_trained_on_dns3.tar')['model'])

# 读取音频
audio, sr = sf.read('mix.wav')
audio_tensor = torch.from_numpy(audio)

# STFT
spec = torch.stft(audio_tensor, 512, 256, 512,
                  torch.hann_window(512).pow(0.5),
                  return_complex=False)
spec = spec[None]  # 添加 batch 维度

# 推理
with torch.no_grad():
    enhanced_spec = model(spec)

# ISTFT
enhanced_audio = torch.istft(enhanced_spec[0], 512, 256, 512,
                             torch.hann_window(512).pow(0.5))
sf.write('enh.wav', enhanced_audio.numpy(), 16000)
```

### 流式推理
```python
from stream.gtcrn import StreamGTCRN
import numpy as np

# 初始化流式模型
stream_model = StreamGTCRN().eval()
stream_model.load_state_dict(torch.load('model_trained_on_dns3.tar')['model'])

# 初始化缓存
conv_cache = torch.zeros(2, 1, 16, 16, 33)
tra_cache = torch.zeros(2, 3, 1, 1, 16)
inter_cache = torch.zeros(2, 1, 33, 16)

# 逐帧处理
for i in range(num_frames):
    frame = spec[:, :, i:i+1]  # 当前帧
    enhanced_frame, conv_cache, tra_cache, inter_cache = \
        stream_model(frame, conv_cache, tra_cache, inter_cache)
    # 累积增强帧
```

---

## 技术参考

- **TRT-SE**: https://github.com/Xiaobin-Rong/TRT-SE
- **GTCRN 原始论文**: https://github.com/Xiaobin-Rong/gtcrn
- **Issue-3**: https://github.com/Xiaobin-Rong/gtcrn/issues/3（ONNX 简化优化）

---

## 作者

Xiaobin Rong

---

## 许可

本项目包含自定义开源协议，使用前请务必阅读根目录下的 LICENSE 文件。
