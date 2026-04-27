"""
Configuration for the fruit recommendation pipeline.

The language stack now does one thing:
turn a user's request into one recommended fruit, a teasing response, and a
JSON record containing the chosen sequence number.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def normalize_proxy_env(disable_proxy: bool = False) -> None:
    """Normalize or clear common proxy environment variables."""
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
            os.environ.pop(key, None)
        return

    for key in proxy_keys:
        value = os.environ.get(key)
        if value and value.startswith("socks://"):
            os.environ[key] = "socks5://" + value[len("socks://") :]


def normalize_deepseek_base_url(url: str) -> str:
    """
    Normalize DeepSeek base URLs to the OpenAI-compatible /v1 endpoint.

    Some local secrets files store the host root (for example, https://api.deepseek.com).
    The OpenAI client expects the versioned base URL, so we upgrade that form here.
    """
    normalized = str(url or "").strip()
    if not normalized:
        return "https://api.deepseek.com/v1"
    if normalized.rstrip("/") == "https://api.deepseek.com":
        return "https://api.deepseek.com/v1"
    return normalized


BASE_DIR = Path(__file__).parent.resolve()
SECRETS_PATH = BASE_DIR / "secrets.local.json"

# Audio
AUDIO_DURATION_SEC = float(os.getenv("AUDIO_DURATION_SEC", "3"))
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
AUDIO_MIN_RMS = float(os.getenv("AUDIO_MIN_RMS", "0.001"))
AUDIO_INPUT_DEVICE = os.getenv("AUDIO_INPUT_DEVICE", None)
TEMP_AUDIO_PATH = BASE_DIR / "voice_command.wav"

# STT
LOCAL_STT_MODEL = os.getenv("LOCAL_STT_MODEL", "small")
LOCAL_STT_LANGUAGE = os.getenv("LOCAL_STT_LANGUAGE", "zh")
LOCAL_STT_COMPUTE_TYPE = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8")

# Fruit recommendation
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
FRUIT_USE_LLM = os.getenv("FRUIT_USE_LLM", "true").lower() == "true"
FRUIT_LLM_TIMEOUT_SEC = float(os.getenv("FRUIT_LLM_TIMEOUT_SEC", "4"))
FRUIT_ALLOW_LOCAL_FALLBACK = os.getenv("FRUIT_ALLOW_LOCAL_FALLBACK", "false").lower() == "true"
FRUIT_OUTPUT_JSON_PATH = BASE_DIR / "fruit_recommendation.json"
FRUIT_API_KEY = os.getenv("FRUIT_API_KEY", "")
FRUIT_BASE_URL = normalize_deepseek_base_url(os.getenv("FRUIT_BASE_URL", ""))
FRUIT_CHAT_MODEL = os.getenv("FRUIT_CHAT_MODEL", DEEPSEEK_CHAT_MODEL)

# Feedback TTS
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge-tts")
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
EDGE_TTS_TIMEOUT_SEC = float(os.getenv("EDGE_TTS_TIMEOUT_SEC", "20"))
TTS_OUTPUT_PATH = BASE_DIR / "command_reply.mp3"
ENABLE_TTS = os.getenv("ENABLE_TTS", "true").lower() == "true"
ENABLE_PLAYBACK = os.getenv("ENABLE_PLAYBACK", "true").lower() == "true"
ENABLE_DEBUG_LOG = os.getenv("ENABLE_DEBUG_LOG", "false").lower() == "true"

TTS_API_KEY = os.getenv("TTS_API_KEY", "")
TTS_BASE_URL = os.getenv("TTS_BASE_URL", "")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = normalize_deepseek_base_url(
    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
)
DEEPSEEK_TTS_MODEL = os.getenv("DEEPSEEK_TTS_MODEL", "tts-1")
DEEPSEEK_TTS_VOICE = os.getenv("DEEPSEEK_TTS_VOICE", "alloy")
DEEPSEEK_DISABLE_PROXY = os.getenv("DEEPSEEK_DISABLE_PROXY", "false").lower() == "true"

def load_secrets() -> None:
    """Load optional local overrides from `secrets.local.json`."""
    if not SECRETS_PATH.exists():
        return

    try:
        with SECRETS_PATH.open("r", encoding="utf-8") as f:
            secrets = json.load(f)
    except Exception as exc:
        print(f"[WARN] Failed to load secrets from {SECRETS_PATH}: {exc}")
        return

    if not isinstance(secrets, dict):
        print(f"[WARN] secrets file must be a JSON object: {SECRETS_PATH}")
        return

    for key, value in secrets.items():
        env_key = str(key).upper()
        if env_key in globals():
            globals()[env_key] = value


load_secrets()
normalize_proxy_env(disable_proxy=DEEPSEEK_DISABLE_PROXY)
DEEPSEEK_BASE_URL = normalize_deepseek_base_url(DEEPSEEK_BASE_URL)
FRUIT_API_KEY = globals().get("FRUIT_API_KEY", FRUIT_API_KEY) or DEEPSEEK_API_KEY
FRUIT_BASE_URL = normalize_deepseek_base_url(
    globals().get("FRUIT_BASE_URL", FRUIT_BASE_URL) or DEEPSEEK_BASE_URL
)

if "FRUIT_CHAT_MODEL" not in os.environ:
    FRUIT_CHAT_MODEL = globals().get("DEEPSEEK_CHAT_MODEL", FRUIT_CHAT_MODEL)

if ENABLE_DEBUG_LOG:
    print("[CONFIG] Loaded configuration:")
    print(f"  Audio: {AUDIO_SAMPLE_RATE}Hz, {AUDIO_DURATION_SEC}s, device={AUDIO_INPUT_DEVICE}")
    print(f"  STT: {LOCAL_STT_MODEL} (lang={LOCAL_STT_LANGUAGE})")
    print(f"  Fruit chat model: {FRUIT_CHAT_MODEL}")
    print(f"  Fruit LLM enabled: {FRUIT_USE_LLM} (timeout={FRUIT_LLM_TIMEOUT_SEC}s)")
    print(f"  TTS: {TTS_ENGINE}")
    print(f"  JSON output: {FRUIT_OUTPUT_JSON_PATH}")
