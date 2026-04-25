"""
TTS Core Module - 文字转语音统一接口
支持 Edge-TTS（推荐）和 DeepSeek TTS
"""

import asyncio
import os
import sys
import shutil
import subprocess
import time
from typing import Optional
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("[WARN] edge_tts not installed. Install with: pip install edge-tts")
    edge_tts = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

from openai import OpenAI
try:
    from . import config
except ImportError:
    import config


def _wait_for_file_ready(file_path: str, timeout_sec: float = 5.0) -> bool:
    """等待文件落盘并可读取，避免 TTS 生成后立刻播放的竞态。"""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


# ==================== TTS 工厂函数 ====================
async def text_to_speech_edge(
    text: str,
    voice: str = None,
    output_path: str = None,
) -> str:
    """
    使用 Edge-TTS 合成语音（推荐方案）
    
    Args:
        text: 待合成文本
        voice: 声音代码，默认 zh-CN-XiaoxiaoNeural
        output_path: 输出 MP3 路径，默认 config.TTS_OUTPUT_PATH
        
    Returns:
        输出文件路径
    """
    if edge_tts is None:
        raise RuntimeError("edge_tts not installed")
    
    voice = voice or config.EDGE_TTS_VOICE
    output_path = output_path or str(config.TTS_OUTPUT_PATH)
    
    print(f"[INFO] Synthesizing TTS with Edge-TTS: {voice}")
    print(f"  Text: {text[:50]}...")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"[INFO] TTS saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Edge-TTS failed: {e}")
        raise


def text_to_speech_deepseek(
    text: str,
    voice: str = None,
    output_path: str = None,
) -> str:
    """
    使用 DeepSeek API 合成语音（需要充足的API额度）
    
    Args:
        text: 待合成文本
        voice: 声音代码，默认 alloy
        output_path: 输出 MP3 路径
        
    Returns:
        输出文件路径
    """
    voice = voice or config.DEEPSEEK_TTS_VOICE
    output_path = output_path or str(config.TTS_OUTPUT_PATH)
    
    if not config.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set")
    
    print(f"[INFO] Synthesizing TTS with DeepSeek: {voice}")
    print(f"  Text: {text[:50]}...")
    
    try:
        client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        
        with client.audio.speech.with_raw_response.create(
            model=config.DEEPSEEK_TTS_MODEL,
            voice=voice,
            input=text,
        ) as response:
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        
        print(f"[INFO] TTS saved to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"[ERROR] DeepSeek TTS failed: {e}")
        raise


def text_to_speech_local(
    text: str,
    output_path: str = None,
) -> str:
    """本地离线 TTS（优先 pyttsx3，回退 espeak）。"""
    if output_path is None:
        output_path = str(Path(config.BASE_DIR) / "confirmation_audio.wav")
    if not output_path.lower().endswith(".wav"):
        output_path = str(Path(output_path).with_suffix(".wav"))

    print("[INFO] Synthesizing TTS with local engine")
    print(f"  Text: {text[:50]}...")

    # 1) pyttsx3 (offline)
    if pyttsx3 is not None:
        try:
            engine = pyttsx3.init()
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            if _wait_for_file_ready(output_path, timeout_sec=6.0):
                print(f"[INFO] Local TTS saved to {output_path}")
                return output_path
            print("[WARN] pyttsx3 output file not ready in time")
        except Exception as e:
            print(f"[WARN] pyttsx3 failed: {e}")

    # 2) espeak (offline command fallback)
    espeak_bin = shutil.which("espeak")
    if espeak_bin:
        try:
            subprocess.run([espeak_bin, "-w", output_path, text], check=True)
            if _wait_for_file_ready(output_path, timeout_sec=2.0):
                print(f"[INFO] Local TTS saved to {output_path}")
                return output_path
            print("[WARN] espeak output file not ready in time")
        except Exception as e:
            print(f"[WARN] espeak failed: {e}")

    raise RuntimeError("No local TTS backend available (pyttsx3/espeak)")


def text_to_speech(
    text: str,
    engine: str = None,
    output_path: str = None,
) -> str:
    """
    统一的 TTS 接口（支持多引擎）
    
    Args:
        text: 待合成文本
        engine: TTS 引擎（edge-tts/deepseek），默认使用 config.TTS_ENGINE
        output_path: 输出文件路径
        
    Returns:
        输出文件路径
    """
    engine = engine or config.TTS_ENGINE
    
    if not config.ENABLE_TTS:
        print("[INFO] TTS disabled (ENABLE_TTS=false)")
        return ""
    
    if not text or not text.strip():
        print("[WARN] Empty text for TTS, skipping")
        return ""
    
    try:
        if engine == "edge-tts":
            try:
                return asyncio.run(text_to_speech_edge(text, output_path=output_path))
            except Exception as edge_err:
                print(f"[WARN] Edge-TTS unavailable, fallback to local TTS: {edge_err}")
                return text_to_speech_local(text, output_path=output_path)
        elif engine == "deepseek":
            return text_to_speech_deepseek(text, output_path=output_path)
        elif engine == "local":
            return text_to_speech_local(text, output_path=output_path)
        else:
            raise ValueError(f"Unknown TTS engine: {engine}")
    except Exception as e:
        print(f"[ERROR] TTS failed: {e}")
        if config.ENABLE_DEBUG_LOG:
            import traceback
            traceback.print_exc()
        return ""


# ==================== 快速接口 ====================
def generate_confirmation_audio(
    confirmation_text: str,
    output_path: str = None,
) -> str:
    """
    生成确认消息的语音版本
    
    Args:
        confirmation_text: 确认文本（如 "已为你确认食材：12号蓝莓，16号芒果。请确认是否正确。"）
        output_path: 输出文件路径
        
    Returns:
        音频文件路径（如果成功）或空字符串（如果禁用/失败）
    """
    return text_to_speech(confirmation_text, output_path=output_path)


# ==================== 测试 ====================
if __name__ == "__main__":
    # 测试 Edge-TTS
    test_text = "这是一个测试。食材已确认：番茄和土豆。"
    print(f"Testing TTS with text: {test_text}\n")
    
    try:
        result = text_to_speech(test_text, engine="edge-tts")
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
