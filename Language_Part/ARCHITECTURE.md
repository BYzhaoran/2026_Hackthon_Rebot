# Voice-to-Ingredient Pipeline - 架构文档

## 🏗️ 项目结构（基于 Fridge 设计思想）

```
Language_Part/
├── config.py                  # ⚙️  统一配置（所有参数在这里）
├── audio_core.py              # 🎙️  音频录制/播放模块
├── tts_core.py                # 🔊 TTS 合成模块（Edge-TTS/DeepSeek）
├── voice_pipeline.py          # 🎯 主流程脚本
├── ingredients_db.json        # 📋 食材数据库
├── selected_ingredients.json  # 📤 输出 JSON
├── secrets.local.json         # 🔐 API Key 配置（Git 忽略）
├── requirements.txt           # 📦 依赖项
└── README.md                  # 📖 使用指南
```

## 🔄 处理流程

```
┌─────────────────┐
│  🎙️  录音       │ record_audio_robustly()
│  (电脑麦克风)   │  └─ 多设备检测
└────────┬────────┘  └─ 采样率自动协商
         │            └─ RMS 音量检查
         ↓
┌─────────────────┐
│  🔤 STT         │ transcribe_audio_local()
│  (Faster-Whisper)│  └─ 多策略重试
└────────┬────────┘  └─ 置信度评分
         │
         ↓
┌─────────────────┐
│  🤖 LLM选择     │ select_ingredients()
│  (DeepSeek)      │  └─ 食材 ID 提取
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  💬 确认文本    │ generate_confirmation_text()
│  生成           │  └─ 序号化食材列表
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  🔊 TTS 合成    │ generate_confirmation_audio()
│  (Edge-TTS)      │  └─ MP3 音频输出
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  💾 保存 JSON   │ save_output_json()
│  (结构化输出)   │  └─ 完整结果记录
└─────────────────┘
```

## 📦 核心模块

### `config.py` - 统一配置

**设计理念**：类似 Fridge 的 `config.py`，集中管理所有参数

```python
# 环境变量覆盖（优先级最高）
export DEEPSEEK_API_KEY=sk-xxx
export LOCAL_STT_LANGUAGE=zh
export TTS_ENGINE=edge-tts

# 或从 secrets.local.json 加载（次优先）
# 或使用代码中的默认值（最低优先）
```

**关键配置**：
- 音频参数：采样率、时长、最小 RMS
- STT：模型大小（tiny/base/small/medium）、语言
- TTS：引擎选择（edge-tts/deepseek）、声音
- API：DeepSeek API Key、代理设置

---

### `audio_core.py` - 音频处理模块

**特性**（相比 Fridge）：

| 功能 | Fridge | audio_core.py |
|-----|--------|---------------|
| 设备选择 | ❌ 无 | ✅ 自动 + 手动选择 |
| 采样率协商 | ❌ 固定 16kHz | ✅ 16k/44.1k/48k 自动协商 |
| 音质检查 | ❌ 无 | ✅ RMS 阈值 + 重试 |
| 错误恢复 | ❌ 最小 | ✅ 多策略回退 |

**主要函数**：

```python
# 鲁棒录音（带多策略回退）
audio, sr = record_audio_robustly(
    duration_sec=10,
    target_sample_rate=16000,
    input_device=None,  # None = 默认设备
    min_rms_threshold=0.001,
)

# 保存/加载 WAV
save_audio_to_wav(audio, sr, "output.wav")
audio, sr = load_audio_from_wav("input.wav")

# 播放音频
play_audio(audio, sr)

# 列出设备
init_audio_system()  # 打印所有可用设备
```

---

### `tts_core.py` - TTS 合成模块

**支持两种引擎**：

1. **Edge-TTS**（推荐）✅
   - 优点：免费、无 API 额度限制、支持异步
   - 输出格式：MP3
   - 声音：`zh-CN-XiaoxiaoNeural`（微软小晓）等

2. **DeepSeek TTS**
   - 优点：与现有 API 集成、多语言
   - 缺点：需要充足 API 额度
   - 输出格式：MP3

**主要函数**：

```python
# 高级接口
confirmation_audio_path = generate_confirmation_audio(
    "已为你确认食材：12号蓝莓，16号芒果。"
)

# 低级接口（指定引擎）
path = text_to_speech(
    text="测试文本",
    engine="edge-tts",  # 或 "deepseek"
    output_path="output.mp3"
)
```

---

### `voice_pipeline.py` - 主脚本

**模块化设计**：

1. `transcribe_audio_local()` - STT 转录
   - 多策略重试（语言 × VAD 组合）
   - 置信度评分

2. `select_ingredients()` - DeepSeek 食材选择
   - JSON 响应解析
   - ID 提取

3. `generate_confirmation_text()` - 确认消息生成
   - 序号化列表格式

4. `main_voice_pipeline()` - 主流程编排
   - 完整的 6 步管道

**支持两种运行模式**：

```bash
# 🎙️  语音模式（使用麦克风）
python voice_pipeline.py

# 📝 文本模式（用于测试）
python voice_pipeline.py --text "我想要蓝莓和芒果"

# 高级选项
python voice_pipeline.py \
  --input-device 1 \
  --sample-rate 44100 \
  --duration 5 \
  --disable-tts
```

---

## 🚀 快速开始

### 1️⃣ 安装依赖

```bash
# 安装 PortAudio（必需）
conda install -c conda-forge portaudio

# 安装 Python 包
pip install -r requirements.txt

# 或更新环境
conda env update -f environment.yml
```

### 2️⃣ 配置 API Key

创建 `secrets.local.json`：

```json
{
  "DEEPSEEK_API_KEY": "sk-your-api-key-here",
  "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
  "EDGE_TTS_VOICE": "zh-CN-XiaoxiaoNeural"
}
```

或使用环境变量：

```bash
export DEEPSEEK_API_KEY=sk-xxx
export DEEPSEEK_DISABLE_PROXY=true  # 如果在中国大陆
```

### 3️⃣ 测试运行

**文本模式（推荐先试）**：

```bash
python voice_pipeline.py --text "我想要番茄和土豆" --disable-tts
```

预期输出：

```json
{
  "timestamp_utc": "2026-04-25T04:10:43.653061+00:00",
  "request_text": "我想要番茄和土豆",
  "selected_ids": [1, 2],
  "numbered_selection": [
    {"seq": 1, "id": 1, "name": "番茄", "category": "vegetable"},
    {"seq": 2, "id": 2, "name": "土豆", "category": "vegetable"}
  ],
  "confirmation_text": "已为你确认食材：1号番茄，2号土豆。请确认是否正确。",
  "confirmation_audio_path": ""
}
```

**语音模式（实际使用）**：

```bash
python voice_pipeline.py --duration 5 --input-device 0
```

流程：
1. ⏺️ 开始录音 5 秒
2. 🔤 自动转录语音
3. 🤖 调用 DeepSeek 选择食材
4. 💬 生成确认消息
5. 🔊 生成语音回复（可选）
6. 💾 保存到 `selected_ingredients.json`

---

## 🎛️ 环境变量参考

```bash
# 音频
AUDIO_DURATION_SEC=10              # 录音时长
AUDIO_SAMPLE_RATE=16000            # 采样率
AUDIO_INPUT_DEVICE=0               # 输入设备索引
AUDIO_MIN_RMS=0.001                # 最小音量

# STT
LOCAL_STT_MODEL=small              # whisper 模型
LOCAL_STT_LANGUAGE=zh              # 语言
LOCAL_STT_COMPUTE_TYPE=int8        # 计算类型

# API
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_DISABLE_PROXY=true        # 禁用代理

# TTS
TTS_ENGINE=edge-tts                # 或 deepseek
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
ENABLE_TTS=true
ENABLE_PLAYBACK=true

# 调试
ENABLE_DEBUG_LOG=false
```

---

## 📊 与 Fridge 对比

| 特性 | Fridge | 本项目 |
|-----|--------|--------|
| 架构风格 | 模块化（Talk/） | 模块化（config + core modules） |
| 配置管理 | `config.py` | `config.py`（更完善） |
| 音频设备 | 固定默认 | 自动 + 手动选择 |
| 采样率 | 固定 16kHz | 自动协商 |
| 音质检查 | 无 | RMS 阈值 + 重试 |
| STT | Whisper base | faster-whisper (可选 tiny/small/medium) |
| TTS | Edge-TTS | Edge-TTS（推荐）+ DeepSeek（备选） |
| 错误处理 | 最小化 | 完整多策略 |
| 生产就绪 | 🟡 学习/演示 | 🟢 企业级 |

---

## ⚙️ 故障排查

### 问题：录音失败（"Invalid sample rate"）

**解决**：
1. 列出设备：`python voice_pipeline.py --text "test" 2>&1 | grep "Available"`
2. 尝试指定设备：`python voice_pipeline.py --input-device 1`
3. 检查采样率：`python voice_pipeline.py --sample-rate 44100`

### 问题：STT 产生空文本

**解决**：
1. 检查音量：`ENABLE_DEBUG_LOG=true python voice_pipeline.py`
   - 查看 RMS 值是否超过阈值
2. 尝试禁用 VAD：`LOCAL_STT_STRATEGY_RETRY=true python voice_pipeline.py`
3. 更换语言：`LOCAL_STT_LANGUAGE=en python voice_pipeline.py`

### 问题：DeepSeek API 超时

**解决**：
1. 检查 API Key：`echo $DEEPSEEK_API_KEY`
2. 禁用代理：`DEEPSEEK_DISABLE_PROXY=true`
3. 检查网络：`ping api.deepseek.com`

### 问题：Edge-TTS 无输出

**解决**：
1. 测试连接：`python -c "import edge_tts; print('OK')"`
2. 指定声音：`EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural`
3. 启用调试：`ENABLE_DEBUG_LOG=true`

---

## 📝 下一步

- [ ] 添加唤醒词检测（Fridge 风格）
- [ ] 支持本地 TTS（pyttsx3）
- [ ] WebUI 控制面板
- [ ] 数据库持久化
- [ ] 性能监控和日志系统

---

**参考**：
- Fridge 项目：https://github.com/BYzhaoran/Fridge
- Faster-Whisper 文档：https://github.com/SYSTRAN/faster-whisper
- Edge-TTS 文档：https://github.com/rany2/edge-tts
- DeepSeek API：https://platform.deepseek.com/
