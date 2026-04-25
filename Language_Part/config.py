"""
Fridge 风格统一配置文件
支持环境变量覆盖，保留本地 JSON 配置的高级选项
"""

import os
import json
from pathlib import Path
from typing import Optional


def normalize_proxy_env(disable_proxy: bool = False) -> None:
    """Normalize proxy env vars for libraries that reject socks://.

    - If disable_proxy is True, clears all common proxy env vars.
    - Otherwise rewrites socks:// to socks5:// for compatibility.
    """
    proxy_keys = [
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    ]

    if disable_proxy:
        for key in proxy_keys:
            if key in os.environ:
                os.environ.pop(key, None)
        return

    for key in proxy_keys:
        value = os.environ.get(key)
        if not value:
            continue
        # httpx/urllib3 generally accept socks5:// but may reject socks://
        if value.startswith("socks://"):
            os.environ[key] = "socks5://" + value[len("socks://") :]

# ==================== 路径配置 ====================
BASE_DIR = Path(__file__).parent.resolve()
INGREDIENTS_DB_PATH = BASE_DIR / "ingredients_db.json"
OUTPUT_JSON_PATH = BASE_DIR / "selected_ingredients.json"
TEMP_AUDIO_PATH = BASE_DIR / "speech_input.wav"
SECRETS_PATH = BASE_DIR / "secrets.local.json"

# ==================== 音频参数 ====================
AUDIO_DURATION_SEC = float(os.getenv("AUDIO_DURATION_SEC", "10"))
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
AUDIO_MIN_RMS = float(os.getenv("AUDIO_MIN_RMS", "0.001"))
AUDIO_INPUT_DEVICE = os.getenv("AUDIO_INPUT_DEVICE", None)  # None = default device

# ==================== STT 配置（本地）====================
LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")  # tiny, base, small, medium
LOCAL_STT_LANGUAGE = os.getenv("LOCAL_STT_LANGUAGE", "zh")  # zh, en, auto
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")  # int8, float16, float32
LOCAL_STT_STRATEGY_RETRY = os.getenv("LOCAL_STT_STRATEGY_RETRY", "true").lower() == "true"

# ==================== API 配置（DeepSeek） ====================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
DEEPSEEK_PROXY = os.getenv("DEEPSEEK_PROXY", "")
DEEPSEEK_DISABLE_PROXY = os.getenv("DEEPSEEK_DISABLE_PROXY", "false").lower() == "true"

# ==================== TTS 配置 ====================
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge-tts")  # edge-tts, deepseek, local
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # 微软女性声
TTS_OUTPUT_PATH = BASE_DIR / "confirmation_audio.mp3"

DEEPSEEK_TTS_MODEL = os.getenv("DEEPSEEK_TTS_MODEL", "tts-1")
DEEPSEEK_TTS_VOICE = os.getenv("DEEPSEEK_TTS_VOICE", "alloy")

# ==================== 功能开关 ====================
ENABLE_TTS = os.getenv("ENABLE_TTS", "true").lower() == "true"
ENABLE_PLAYBACK = os.getenv("ENABLE_PLAYBACK", "true").lower() == "true"
ENABLE_DEBUG_LOG = os.getenv("ENABLE_DEBUG_LOG", "false").lower() == "true"

# ==================== 唤醒词配置（Fridge 风格） ====================
WAKE_WORDS = {
    "小冰": "recipe",
    "小兵": "recipe",
    "小炳": "recipe",
}

# ==================== 从 secrets.local.json 加载覆盖值 ====================
def load_secrets():
    """从本地 secrets 文件加载敏感配置"""
    if SECRETS_PATH.exists():
        try:
            with open(SECRETS_PATH) as f:
                secrets = json.load(f)
                # 只覆盖显式配置的值
                globals().update({
                    k.upper(): v 
                    for k, v in secrets.items()
                    if k.upper() in globals()
                })
        except Exception as e:
            print(f"[WARN] Failed to load secrets from {SECRETS_PATH}: {e}")

# 在模块导入时自动加载
load_secrets()

# 在配置加载后，统一处理代理环境变量
normalize_proxy_env(disable_proxy=DEEPSEEK_DISABLE_PROXY)

# ==================== 调试输出 ====================
if ENABLE_DEBUG_LOG:
    print("[CONFIG] Loaded configuration:")
    print(f"  Audio: {AUDIO_SAMPLE_RATE}Hz, {AUDIO_DURATION_SEC}s, device={AUDIO_INPUT_DEVICE}")
    print(f"  STT: {LOCAL_STT_MODEL} (lang={LOCAL_STT_LANGUAGE})")
    print(f"  TTS: {TTS_ENGINE} ({EDGE_TTS_VOICE if TTS_ENGINE == 'edge-tts' else DEEPSEEK_TTS_VOICE})")
    print(f"  Paths: db={INGREDIENTS_DB_PATH}, output={OUTPUT_JSON_PATH}")
