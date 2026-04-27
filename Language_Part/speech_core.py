"""
Speech Core Module - AI 文本到语音再到播放的统一流程

这个模块负责把模型返回的文本做轻量清洗，然后交给 TTS 后端生成音频，
最后按需播放。业务脚本只需要调用一个入口，不再自己拼接 TTS / 播放逻辑。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from . import config
    from .tts_core import text_to_speech
except ImportError:
    import config
    from tts_core import text_to_speech


_DIGIT_MAP = {
    "0": "零",
    "1": "一",
    "2": "二",
    "3": "三",
    "4": "四",
    "5": "五",
    "6": "六",
    "7": "七",
    "8": "八",
    "9": "九",
}

_PLAYFUL_TAILS = [
    "我已经记下了，后面就按这个命令走。",
    "指令收到，系统准备切换状态。",
    "命令确认，接下来交给控制脚本。",
    "别担心，我会把这条指令执行到位。",
    "流程已经接上了，你可以继续说下一条。",
    "收到，这次不再跑偏了。",
    "执行通道已经打开，准备动作。",
    "好，命令已经落地。",
    "收到指令，马上处理。",
    "状态同步完成，继续下一步吧。",
]


@dataclass
class SpeechResult:
    text: str
    audio_path: str
    played: bool


def _int_to_chinese(number: str) -> str:
    """把简单阿拉伯数字转成中文读法。"""
    try:
        value = int(number)
    except ValueError:
        return number

    if value < 0:
        return number
    if value < 10:
        return _DIGIT_MAP[number]
    if value < 20:
        return "十" if value == 10 else f"十{_DIGIT_MAP[str(value % 10)]}"
    if value < 100:
        tens, ones = divmod(value, 10)
        return f"{_DIGIT_MAP[str(tens)]}十" + (_DIGIT_MAP[str(ones)] if ones else "")
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        tens, ones = divmod(rest, 10)
        result = f"{_DIGIT_MAP[str(hundreds)]}百"
        if rest == 0:
            return result
        if rest < 10:
            return result + f"零{_DIGIT_MAP[str(ones)]}"
        if rest < 20:
            return result + f"一十{_DIGIT_MAP[str(ones)] if ones else ''}"
        return result + f"{_DIGIT_MAP[str(tens)]}十" + (_DIGIT_MAP[str(ones)] if ones else "")
    return number


def normalize_speech_text(text: str) -> str:
    """
    把 AI 返回文本清洗成更适合朗读的形式。

    目标不是“总结”，而是去掉明显会破坏朗读的 markdown / code / 多余空白。
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 去掉代码块标记，保留其中内容
    cleaned = re.sub(r"```(?:\w+)?\n?", "\n", cleaned)
    cleaned = cleaned.replace("```", "\n")

    # 去掉常见 markdown 装饰
    cleaned = cleaned.replace("*", " ").replace("_", " ").replace("`", " ")
    cleaned = cleaned.replace("#", " ")

    # 列表和换行转成停顿
    cleaned = re.sub(r"[\r\n]+", "，", cleaned)
    cleaned = re.sub(r"[•·]+", "，", cleaned)

    # 统一标点和空白
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*([，。！？；：,.;!?])\s*", r"\1", cleaned)
    cleaned = re.sub(r"，{2,}", "，", cleaned)
    cleaned = cleaned.strip(" ，。！？；：,.;!?")

    # 把数字读成中文，避免“1 2 号”这种拆读
    cleaned = re.sub(r"\b(\d+)\b", lambda m: _int_to_chinese(m.group(1)), cleaned)

    # 特别处理“12号”这类格式
    cleaned = re.sub(r"(\d+)号", lambda m: f"{_int_to_chinese(m.group(1))}号", cleaned)

    return cleaned


def add_playful_tone(text: str) -> str:
    """给确认文案追加一句轻微调侃，保持口吻自然。"""
    base = text.strip()
    if not base:
        return base
    return f"{base} {random.choice(_PLAYFUL_TAILS)}"


def _default_output_path(engine: Optional[str] = None) -> str:
    chosen = (engine or config.TTS_ENGINE or "edge-tts").strip().lower()
    suffix = ".wav" if chosen == "local" else ".mp3"
    return str(config.TTS_OUTPUT_PATH.with_suffix(suffix))


def synthesize_speech(
    text: str,
    *,
    output_path: Optional[str] = None,
    engine: Optional[str] = None,
) -> str:
    """只负责生成音频文件，不做播放。"""
    normalized = normalize_speech_text(text)
    if not normalized:
        return ""

    target_path = output_path or _default_output_path(engine)
    audio_path = text_to_speech(
        normalized,
        engine=engine or config.TTS_ENGINE,
        output_path=target_path,
    )
    if audio_path:
        expected = Path(audio_path)
        if not expected.exists() or expected.stat().st_size <= 0:
            raise RuntimeError(f"TTS generated invalid file: {audio_path}")
    return audio_path


def _play_audio_file_lazily(audio_path: str) -> None:
    """仅在真正需要播放时才导入音频播放依赖。"""
    try:
        from .audio_core import play_audio_file as _play_audio_file
    except ImportError:
        from audio_core import play_audio_file as _play_audio_file

    _play_audio_file(audio_path)


def speak_text(
    text: str,
    *,
    output_path: Optional[str] = None,
    engine: Optional[str] = None,
    auto_play: Optional[bool] = None,
) -> SpeechResult:
    """统一入口：清洗文本 -> 合成语音 -> 按需播放。"""
    audio_path = synthesize_speech(text, output_path=output_path, engine=engine)
    should_play = config.ENABLE_PLAYBACK if auto_play is None else auto_play
    played = False
    if audio_path and should_play:
        _play_audio_file_lazily(audio_path)
        played = True
    return SpeechResult(
        text=normalize_speech_text(text),
        audio_path=audio_path,
        played=played,
    )
