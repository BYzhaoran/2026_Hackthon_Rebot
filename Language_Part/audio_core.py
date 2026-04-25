"""
Audio Core Module - 音频录制与播放的统一接口
设计灵感来自 Fridge/Talk/ 模块，但集成了健壮的设备管理、采样率协商、音质检查
"""

import os
import sys
import wave
import json
import shutil
import subprocess
from typing import Optional, Tuple
import numpy as np
from pathlib import Path

try:
    import sounddevice as sd
    from scipy.io import wavfile
except ImportError as e:
    print(f"[ERROR] Missing audio dependencies. Install with:\n  conda install -c conda-forge portaudio python-sounddevice scipy")
    sys.exit(1)

try:
    from . import config
except ImportError:
    import config


DEVICE_CACHE_PATH = Path(config.BASE_DIR) / ".audio_device_cache.json"


# ==================== 设备管理 ====================
def get_all_input_device_indices(sd_module) -> list[int]:
    """获取所有可用的输入设备索引"""
    devices = sd_module.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            input_devices.append(i)
    return input_devices


def get_default_input_device_index(sd_module) -> Optional[int]:
    """获取系统默认输入设备索引。"""
    try:
        default_devices = sd_module.default.device
        if isinstance(default_devices, (list, tuple)) and len(default_devices) >= 1:
            default_in = default_devices[0]
            if default_in is not None and int(default_in) >= 0:
                return int(default_in)
    except Exception:
        pass
    return None


def load_cached_input_device() -> tuple[Optional[int], Optional[int]]:
    """加载上次成功的输入设备和采样率。"""
    try:
        if not DEVICE_CACHE_PATH.exists():
            return None, None
        with open(DEVICE_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("device_idx"), data.get("sample_rate")
    except Exception:
        return None, None


def save_cached_input_device(device_idx: int, sample_rate: int) -> None:
    """保存本次成功的输入设备和采样率。"""
    try:
        payload = {"device_idx": int(device_idx), "sample_rate": int(sample_rate)}
        with open(DEVICE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # 缓存失败不影响主流程
        pass


def list_input_devices(sd_module) -> None:
    """打印所有可用的输入设备"""
    devices = sd_module.query_devices()
    print("\n[INFO] Available input devices:")
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            default_sr = dev.get("default_samplerate", "?")
            print(f"  [{i}] {dev['name']} (sr={default_sr}, channels={dev['max_input_channels']})")
    print()


def resolve_device_index(sd_module, device_spec: Optional[str | int]) -> Optional[int]:
    """解析设备指定符（设备索引或名称）为实际索引"""
    if device_spec is None:
        return None  # 使用 sounddevice 默认设备
    if isinstance(device_spec, int):
        return device_spec
    if isinstance(device_spec, str) and device_spec.isdigit():
        return int(device_spec)
    # 按名称搜索
    devices = sd_module.query_devices()
    for i, dev in enumerate(devices):
        if device_spec in dev["name"]:
            return i
    raise ValueError(f"Device '{device_spec}' not found")


def get_device_default_sample_rate(sd_module, device_idx: int) -> float:
    """获取设备的默认采样率"""
    dev_info = sd_module.query_devices(device_idx)
    return dev_info.get("default_samplerate", 16000.0)


# ==================== 录音函数 ====================
def record_audio_robustly(
    duration_sec: float = None,
    target_sample_rate: int = None,
    input_device: Optional[str | int] = None,
    min_rms_threshold: float = None,
    max_retries: int = 5,
) -> Tuple[np.ndarray, int]:
    """
    鲁棒的音频录制函数（带多策略回退）
    
    Args:
        duration_sec: 录制时长（秒），默认使用 config.AUDIO_DURATION_SEC
        target_sample_rate: 目标采样率（Hz），默认使用 config.AUDIO_SAMPLE_RATE
        input_device: 输入设备（索引/名称/None），默认使用 config.AUDIO_INPUT_DEVICE
        min_rms_threshold: 最小音量阈值，默认使用 config.AUDIO_MIN_RMS
        max_retries: 最大重试次数（不同设备/采样率）
    
    Returns:
        (audio_array, sample_rate) - 归一化音频数据及其采样率
        
    Raises:
        RuntimeError: 所有重试策略均失败
    """
    duration_sec = duration_sec or config.AUDIO_DURATION_SEC
    target_sample_rate = target_sample_rate or config.AUDIO_SAMPLE_RATE
    min_rms_threshold = min_rms_threshold or config.AUDIO_MIN_RMS

    print(f"[INFO] Recording {duration_sec}s of audio (target {target_sample_rate}Hz)...")

    # 1. 解析目标设备
    try:
        target_device_idx = resolve_device_index(sd, input_device)
    except ValueError as e:
        print(f"[WARN] {e}, using default device")
        target_device_idx = None

    # 2. 构建设备候选列表（优先级：指定设备 > 缓存设备 > 系统默认 > 其他输入设备）
    device_candidates = []
    all_input_devices = get_all_input_device_indices(sd)
    cached_device_idx, cached_sr = load_cached_input_device()
    default_device_idx = get_default_input_device_index(sd)

    if target_device_idx is not None:
        device_candidates.append(target_device_idx)
    elif cached_device_idx is not None and cached_device_idx in all_input_devices:
        device_candidates.append(cached_device_idx)

    if default_device_idx is not None and default_device_idx in all_input_devices and default_device_idx not in device_candidates:
        device_candidates.append(default_device_idx)

    for dev_idx in all_input_devices:
        if dev_idx not in device_candidates:
            device_candidates.append(dev_idx)

    # 3. 为每个设备构建采样率候选列表
    def build_sample_rate_candidates(requested_sr: int, device_default_sr: float) -> list[int]:
        candidates = []
        if requested_sr == int(device_default_sr):
            candidates.append(requested_sr)  # 最优：请求与默认相同
        else:
            candidates.append(int(device_default_sr))  # 优先：设备默认采样率
            candidates.append(requested_sr)  # 次优：请求采样率
        # 如果有缓存且是当前设备，优先尝试缓存采样率
        if cached_sr and int(cached_sr) not in candidates:
            candidates.insert(0, int(cached_sr))
        return candidates[:2]  # 限制为最多2个，减少无效尝试

    # 4. 多策略重试
    last_error = None
    attempt = 0

    for dev_idx in device_candidates:
        device_default_sr = get_device_default_sample_rate(sd, dev_idx)
        sample_rates = build_sample_rate_candidates(target_sample_rate, device_default_sr)

        for sr in sample_rates:
            attempt += 1
            if attempt > max_retries:
                break

            try:
                dev_info = sd.query_devices(dev_idx)
                dev_name = dev_info["name"]

                # 先做参数预检，避免触发底层 PortAudio 冗长错误日志
                try:
                    sd.check_input_settings(
                        device=dev_idx,
                        channels=config.AUDIO_CHANNELS,
                        samplerate=int(sr),
                    )
                except Exception:
                    print(f"  [Attempt {attempt}] Device={dev_name} (idx={dev_idx}), SR={sr}Hz")
                    print("    ⚠️  Unsupported input settings, skipping")
                    continue

                print(f"  [Attempt {attempt}] Device={dev_name} (idx={dev_idx}), SR={sr}Hz")

                # 执行录音
                frames = int(sr * duration_sec)
                audio = sd.rec(frames, samplerate=int(sr), channels=config.AUDIO_CHANNELS, device=dev_idx)
                sd.wait()

                # 转为浮点型
                if audio.dtype == np.int16:
                    audio_float = audio.astype(np.float32) / 32768.0
                else:
                    audio_float = audio.astype(np.float32)

                # 计算 RMS（音量）
                rms = np.sqrt(np.mean(np.square(audio_float)))
                print(f"    RMS={rms:.6f}")

                if rms < min_rms_threshold:
                    print(f"    ❌ Audio too quiet (min={min_rms_threshold:.6f}), trying next device...")
                    # 低音量通常是设备问题，直接切换设备，不再在本设备试其他采样率
                    break

                # 成功：保存并返回
                print(f"  ✅ Recording successful!")
                save_cached_input_device(dev_idx, sr)
                return audio_float, sr

            except Exception as exc:
                print(f"    ❌ Error: {exc}")
                last_error = exc
                continue

        if attempt > max_retries:
            break

    # 所有重试都失败
    error_msg = f"Audio recording failed after {attempt} attempts. Last error: {last_error}"
    print(f"[ERROR] {error_msg}")
    raise RuntimeError(error_msg)


def save_audio_to_wav(audio: np.ndarray, sample_rate: int, output_path: str = None) -> str:
    """
    保存音频为 WAV 文件
    
    Args:
        audio: 音频数据 (float32 -1.0~1.0)
        sample_rate: 采样率 (Hz)
        output_path: 输出文件路径，默认使用 config.TEMP_AUDIO_PATH
        
    Returns:
        保存路径
    """
    output_path = output_path or str(config.TEMP_AUDIO_PATH)
    
    # 转换为 int16
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(output_path, sample_rate, audio_int16)
    print(f"[INFO] Audio saved to {output_path}")
    return output_path


def load_audio_from_wav(audio_path: str) -> Tuple[np.ndarray, int]:
    """
    从 WAV 文件加载音频
    
    Args:
        audio_path: 文件路径
        
    Returns:
        (audio_float32, sample_rate)
    """
    sample_rate, audio_int16 = wavfile.read(audio_path)
    audio_float32 = audio_int16.astype(np.float32) / 32768.0
    print(f"[INFO] Loaded audio from {audio_path} ({sample_rate}Hz)")
    return audio_float32, sample_rate


# ==================== 播放函数 ====================
def play_audio(audio: np.ndarray, sample_rate: int) -> None:
    """
    播放音频（类似 Fridge 的 speak 函数）
    
    Args:
        audio: 音频数据 (float32 -1.0~1.0)
        sample_rate: 采样率 (Hz)
    """
    if not config.ENABLE_PLAYBACK:
        print("[INFO] Playback disabled (ENABLE_PLAYBACK=false)")
        return

    try:
        print(f"[INFO] Playing audio ({len(audio)/sample_rate:.2f}s)...")
        sd.play(audio, sample_rate)
        sd.wait()
        print("[INFO] Playback finished")
    except Exception as e:
        print(f"[WARN] Playback failed: {e}")


def play_tone(
    frequency: float = 880.0,
    duration_sec: float = 0.12,
    volume: float = 0.18,
    sample_rate: int = 22050,
) -> None:
    """播放单个短提示音。"""
    if not config.ENABLE_PLAYBACK:
        print("[INFO] Playback disabled (ENABLE_PLAYBACK=false)")
        return

    duration_sec = max(0.02, float(duration_sec))
    frequency = max(50.0, float(frequency))
    volume = max(0.0, min(float(volume), 1.0))
    sample_rate = max(8000, int(sample_rate))

    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    envelope = np.linspace(0.0, 1.0, t.size)
    envelope = np.minimum(envelope, envelope[::-1])
    audio = (np.sin(2 * np.pi * frequency * t) * envelope * volume).astype(np.float32)
    play_audio(audio, sample_rate)


def play_prompt_sound(kind: str) -> None:
    """播放预定义提示音。"""
    kind = (kind or "").strip().lower()
    if kind == "wake":
        play_tone(frequency=880.0, duration_sec=0.10, volume=0.18)
        play_tone(frequency=1175.0, duration_sec=0.10, volume=0.16)
    elif kind == "record":
        play_tone(frequency=660.0, duration_sec=0.14, volume=0.18)
    else:
        play_tone(frequency=880.0, duration_sec=0.10, volume=0.18)


def play_audio_file(audio_path: str) -> None:
    """
    使用系统命令播放音频文件
    """
    if not config.ENABLE_PLAYBACK:
        print("[INFO] Playback disabled (ENABLE_PLAYBACK=false)")
        return

    audio_path = str(audio_path)
    suffix = Path(audio_path).suffix.lower()
    
    # 根据文件类型优先选择匹配的播放器，避免把 MP3 交给只适合 WAV 的播放器
    if suffix == ".mp3":
        players = [
            ("mpg123", ["mpg123", "-q"]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
            ("paplay", ["paplay"]),
        ]
    else:
        players = [
            ("aplay", ["aplay"]),
            ("paplay", ["paplay"]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
            ("mpg123", ["mpg123", "-q"]),
        ]
    
    for player_name, player_cmd in players:
        player = shutil.which(player_name)
        if player:
            try:
                print(f"[INFO] Playing with {player_name}: {audio_path}")
                subprocess.run(player_cmd + [audio_path], check=True, timeout=30)
                print("[INFO] Playback finished")
                return
            except subprocess.TimeoutExpired:
                print(f"[WARN] {player_name} timeout")
            except Exception as e:
                print(f"[WARN] {player_name} failed: {e}")
    
    print("[ERROR] No working audio player found")


# ==================== 初始化 ====================
def init_audio_system() -> None:
    """初始化音频系统，列出可用设备"""
    print("\n" + "="*60)
    print("🎙️  Audio System Initialization")
    print("="*60)
    
    if config.ENABLE_DEBUG_LOG:
        list_input_devices(sd)
    
    print(f"Configuration:")
    print(f"  Default device: {config.AUDIO_INPUT_DEVICE or 'system default'}")
    print(f"  Sample rate: {config.AUDIO_SAMPLE_RATE} Hz")
    print(f"  Duration: {config.AUDIO_DURATION_SEC} s")
    print(f"  Min RMS: {config.AUDIO_MIN_RMS}")
    print("="*60 + "\n")
