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
    # 自信/傲娇风格
    "这点小菜单我还是能搞定的，别把我当成只会背菜名的机器人。",
    "放心，这波我已经替你理顺了，别再让我当食材复读机。",
    "我已经帮你安排明白了，下次可以直接考我难一点的。",
    "菜单我先记下了，别拿这种小场面来试探我。",
    "就这？我连满汉全席的食材都能背，你这点单子洒洒水啦~",
    "记好了啊，我这小本本可不是白长的，下次直接报菜名就行。",
    "搞定！不是我吹，你点啥我都能接住。",
    "再复杂的单子我都见过，你这算开胃菜。",
    
    # 调侃/幽默风格
    "收到！虽然你说话像挤牙膏，但我还是听懂了。",
    "总算说清楚了，我还以为你要报菜名报一个小时呢。",
    "你确定就这些？不多加点？我记性很好的，别浪费。",
    "食材已锁定，别说我没提醒你，冰箱里可能没有哦~",
    "收到指令！不过你要是临时改主意，我可不负责。",
    "行吧，虽然你说得有点乱，但我还是帮你捋顺了。",
    "记下了！下次可以试着说快点，我反应比你想的快。",
    "没问题，不过我建议你说话的时候离麦克风近一点，我怕听岔了。",
    
    # 贴心/卖萌风格
    "记好啦~ 需要我帮你想个菜谱吗？",
    "收到！如果需要推荐做法，随时喊我~",
    "食材清单已生成，期待你的厨艺大作！",
    "好啦好啦，都记住了，快去准备吧~",
    "收到！如果缺什么食材，我也可以帮你找替代方案哦。",
    "清单已备好，祝你做出美味大餐！",
    "搞定！需要我帮你检查一下搭配是否合理吗？",
    
    # 吐槽/毒舌风格
    "记是记住了，但你确定这些能做出好吃的？",
    "菜单记下了，不过你这个搭配...有点迷啊。",
    "行，你说了算。反正不是我吃，你开心就好。",
    "收到！虽然我觉得这个组合有点黑暗料理的潜质...",
    "记好了，不过我建议你再想想，这个搭配真的没问题吗？",
    "食材已确认，但我保留吐槽你口味不好的权利。",
    
    # 角色扮演/中二风格
    "指令确认！食材数据库已更新，任务完成！",
    "收到！菜单录入成功，随时准备接受下一个任务。",
    "确认完毕！系统稳定，食材清单已锁定。",
    "目标已标记！厨房小助手随时待命。",
    "Over and out！食材数据已同步，请求下次任务。",
    
    # 互动/引导风格
    "记好啦！要不要我帮你排个烹饪顺序？",
    "搞定~ 需要我提醒你先处理哪个食材吗？",
    "收到！要是不确定怎么搭配，我可以给点建议哦。",
    "菜单确认！需要我推荐几个经典菜谱吗？",
    "OK！如果想调整数量或换食材，随时说~",
    
    # 俏皮/调戏风格
    "记下了！不过你要是说错了我可不背锅~",
    "收到！话说你确定就点这些？不多宠幸几个？",
    "食材已收藏~ 下次可以直接说'老样子'哦。",
    "搞定！如果你是想考验我记性，那恭喜你，我过了~",
    "确认完毕！以后这种简单的就别让我重复了，显得我像复读机。",
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
