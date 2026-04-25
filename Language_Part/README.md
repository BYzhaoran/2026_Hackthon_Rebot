# 🎙️ Voice-to-Ingredient Selection Pipeline

**Fridge 架构版本** - 模块化、健壮、生产就绪

这个文件夹提供了一个完整的声音→食材ID→JSON输出的管道系统，基于 [Fridge](https://github.com/BYzhaoran/Fridge) 项目的模块化设计思想，但集成了企业级的错误处理和设备管理。

## 🎯 核心功能

```
🎙️ 电脑麦克风录音 (sounddevice + 多设备支持)
    ↓
🔤 本地语音识别 (Faster-Whisper，多策略重试)
    ↓
🤖 DeepSeek API 智能选择食材
    ↓
💬 AI 生成确认消息
    ↓
🔊 Edge-TTS 文字转语音 (或 DeepSeek TTS)
    ↓
💾 结构化 JSON 输出
```

## 📂 项目结构 (Fridge 模块化设计)

```
Language_Part/
├── config.py                    # ⚙️  统一配置（所有参数）
├── audio_core.py                # 🎙️  音频录制/播放模块
├── tts_core.py                  # 🔊 TTS 合成模块
├── voice_pipeline.py            # 🎯 主流程脚本（新版本）
├── ingredients_db.json          # 📋 食材数据库
├── selected_ingredients.json    # 📤 输出 JSON
├── secrets.local.json           # 🔐 API Key（Git 忽略）
├── ARCHITECTURE.md              # 📖 详细架构文档
├── requirements.txt             # 📦 依赖项（含 edge-tts）
└── README.md                    # 📘 本文件
```

## 🚀 快速开始

### 1️⃣ 安装依赖

```bash
# 安装 PortAudio（必需）
conda install -c conda-forge portaudio

# 安装 Python 包（包括新的 edge-tts）
pip install -r requirements.txt
```

### 2️⃣ 配置 API Key

创建 `secrets.local.json`：

```json
{
  "DEEPSEEK_API_KEY": "sk-your-api-key-here",
  "DEEPSEEK_DISABLE_PROXY": true
}
```

或使用环境变量：

```bash
export DEEPSEEK_API_KEY=sk-xxx
export DEEPSEEK_DISABLE_PROXY=true
```

### 3️⃣ 首次测试（文本模式，推荐）

```bash
# 文本模式 - 快速验证（无需麦克风）
python voice_pipeline.py --text "我想要蓝莓和芒果" --disable-tts

# 输出：
# ✅ Pipeline completed successfully!
# 查看结果: cat selected_ingredients.json
```

### 4️⃣ 实际使用（语音模式）

```bash
# 使用麦克风录音（默认 10 秒）
python voice_pipeline.py

# 或指定录音时长和设备
python voice_pipeline.py --duration 5 --input-device 0

# 查看所有选项
python voice_pipeline.py --help
```

## 📋 使用示例

### 示例 1：文本输入 + TTS

```bash
python voice_pipeline.py \
  --text "我想要番茄、土豆和鸡蛋" \
  --output my_result.json
```

**输出** 样式 (numbered_selection 新增):
```json
{
  "timestamp_utc": "2026-04-25T04:49:11.936235+00:00",
  "request_text": "我想要番茄、土豆和鸡蛋",
  "selected_ids": [1, 2, 5],
  "numbered_selection": [
    {"seq": 1, "id": 1, "name": "番茄", "category": "vegetable"},
    {"seq": 2, "id": 2, "name": "土豆", "category": "vegetable"},
    {"seq": 3, "id": 5, "name": "鸡蛋", "category": "protein"}
  ],
  "selected_items": [...],
  "confirmation_text": "已为你确认食材：1号番茄, 2号土豆, 5号鸡蛋。请确认是否正确。",
  "confirmation_audio_path": "/path/to/confirmation_audio.mp3"
}
```

### 示例 2：实时麦克风输入

```bash
# 使用指定的麦克风设备
python voice_pipeline.py --input-device 1 --duration 10

# 流程：
# 1. 开始录音 10 秒...（请说出你想要的食材）
# 2. 转录语音文本
# 3. 通过 DeepSeek 选择食材
# 4. 生成 TTS 确认语音
# 5. 保存 JSON 结果
```

### 示例 3：禁用 TTS（节省时间）

```bash
python voice_pipeline.py --text "我想要蓝莓" --disable-tts
# 跳过 TTS 步骤，confirmation_audio_path 为空
```

## ⚙️ 高级配置

### 切换 TTS 引擎

```bash
# 使用 Edge-TTS（默认，推荐，免费无限制）
export TTS_ENGINE=edge-tts
export EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural

# 使用 DeepSeek TTS（需要API额度）
export TTS_ENGINE=deepseek
export DEEPSEEK_TTS_VOICE=alloy
```

### 自定义 STT 模型

```bash
# 更快的识别（但质量较低）
export LOCAL_STT_MODEL=tiny
export LOCAL_STT_LANGUAGE=zh

# 更准确的识别（但速度较慢）
export LOCAL_STT_MODEL=medium
```

### 设备选择

```bash
# 列出可用设备（调试模式）
ENABLE_DEBUG_LOG=true python voice_pipeline.py --text "test" 2>&1 | grep "Available"

# 指定特定设备
python voice_pipeline.py --input-device 2

# 按名称选择
python voice_pipeline.py --input-device "USB Audio Device"
```

### 音量阈值调整

```bash
# 降低阈值（更敏感的麦克风）
export AUDIO_MIN_RMS=0.0001

# 提高阈值（更难以激活）
export AUDIO_MIN_RMS=0.01
```

## 📖 详细文档

完整的架构文档、模块说明和故障排查见 [ARCHITECTURE.md](ARCHITECTURE.md)

## 🔍 故障排查

### 问题：PortAudio 库找不到

```bash
# 解决：使用 conda 安装
conda install -c conda-forge portaudio python-sounddevice

# 或 Ubuntu apt
sudo apt install -y portaudio19-dev libportaudio2
```

### 问题：DeepSeek API 代理错误

```bash
# 问题：Unknown scheme for proxy URL('socks://...')
# 解决 1：使用正确的格式
export http_proxy=socks5://127.0.0.1:7890
export https_proxy=socks5://127.0.0.1:7890

# 解决 2：禁用代理
export DEEPSEEK_DISABLE_PROXY=true
```

### 问题：STT 产生空文本

```bash
# 原因：可能是 VAD（语音活动检测）太敏感
# 解决：启用多策略重试
export LOCAL_STT_STRATEGY_RETRY=true

# 或尝试不同的语言
export LOCAL_STT_LANGUAGE=en

# 检查音量
export ENABLE_DEBUG_LOG=true
# 查看 RMS 值（应该 > 0.001）
```

### 问题：没有 Edge-TTS 警告

```bash
# 解决
pip install edge-tts
```

## 📊 与 Fridge 原项目的对比

| 特性 | Fridge | 本项目 |
|-----|--------|--------|
| 架构 | 简洁模块化 | 企业级模块化 |
| 麦克风设备 | ❌ 无选择 | ✅ 自动+手动选择 |
| 采样率 | 固定 16kHz | ✅ 自动协商 |
| 音质检查 | ❌ 无 | ✅ RMS 阈值+多设备重试 |
| 错误恢复 | 最小化 | ✅ 多策略完整回退 |
| 配置管理 | 硬编码 | ✅ config.py+env vars |
| TTS | Edge-TTS | ✅ Edge-TTS（推荐）+ DeepSeek |
| 生产就绪 | 🟡 学习/演示 | 🟢 生产级 |

## ✨ 新特性

### v2.0 (当前 - Fridge 架构重构版)

- ✅ **模块化设计**：`config.py` + `audio_core.py` + `tts_core.py` + `voice_pipeline.py`
- ✅ **多设备支持**：自动检测+手动选择，设备故障自动回退
- ✅ **采样率协商**：支持 16kHz/44.1kHz/48kHz 自动选择
- ✅ **RMS 音量检查**：低音量时自动尝试其他设备
- ✅ **多策略 STT 重试**：4 种语言×VAD 组合，置信度评分
- ✅ **Edge-TTS 支持**：免费、无额度限制、完全异步
- ✅ **序号化输出**：`numbered_selection` 字段，便于 UI 显示
- ✅ **环境变量配置**：完整支持参数化控制

### v1.0 (前版本)

- 基础语音→文字→食材选择→JSON 输出管道

## 🛠️ 开发

### 项目模块

1. **config.py** - 统一参数配置（Fridge 风格）
2. **audio_core.py** - 音频录制/播放（改进的多设备支持）
3. **tts_core.py** - TTS 合成（Edge-TTS + DeepSeek）
4. **voice_pipeline.py** - 主流程编排（完整的 6 步管道）

### 直接导入使用

```python
from audio_core import record_audio_robustly, play_audio_file
from tts_core import generate_confirmation_audio
from voice_pipeline import select_ingredients, generate_confirmation_text

# 或作为 Python 模块使用
# 支持相对导入和直接脚本运行
```

## 📝 环境变量完整列表

见 `config.py` 或 [ARCHITECTURE.md](ARCHITECTURE.md) 的"环境变量参考"部分

快速查看：

```bash
ENABLE_DEBUG_LOG=true python voice_pipeline.py --text "test"
```

## 🔐 安全

- `secrets.local.json` 已添加到 `.gitignore`
- API Key 可通过环境变量或本地 secrets 文件配置
- 代理设置支持 socks5 协议规范化
- 支持 `DEEPSEEK_DISABLE_PROXY` 标志

## 📞 支持

遇到问题？

1. 查看 [ARCHITECTURE.md](ARCHITECTURE.md) 的故障排查部分
2. 启用调试：`ENABLE_DEBUG_LOG=true`
3. 参考 Fridge 原项目：https://github.com/BYzhaoran/Fridge

## 📄 许可

基于 Fridge 项目的架构思想，采用模块化设计。

---

**最后更新**: 2026-04-25  
**版本**: 2.0 (Fridge 架构版，模块化重构)  
**参考项目**: https://github.com/BYzhaoran/Fridge
