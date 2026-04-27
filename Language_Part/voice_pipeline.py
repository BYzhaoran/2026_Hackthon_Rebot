"""
Fruit recommendation pipeline.

Flow:
1. Capture speech or accept direct text input.
2. Transcribe locally if needed.
3. Ask the assistant to choose one fruit from the fixed six-item menu.
4. Speak the recommendation with a teasing tone.
5. Write the chosen sequence number into a JSON file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Optional
from pathlib import Path

try:
    from . import config
    from .fruit_recommendation_core import recommend_fruit, write_result_json
except ImportError:
    import config
    from fruit_recommendation_core import recommend_fruit, write_result_json


def _audio_core():
    try:
        from .audio_core import init_audio_system, list_input_devices, record_audio_robustly, save_audio_to_wav
    except ImportError:
        from audio_core import init_audio_system, list_input_devices, record_audio_robustly, save_audio_to_wav
    return init_audio_system, list_input_devices, record_audio_robustly, save_audio_to_wav


def _speak_text():
    try:
        from .speech_core import speak_text
    except ImportError:
        from speech_core import speak_text
    return speak_text


def transcribe_audio(audio_path: str) -> str:
    """Transcribe a recorded WAV file using faster-whisper, loaded lazily."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise RuntimeError(
            "faster-whisper is required for microphone mode. "
            "Install it or use --text to skip transcription."
        ) from exc

    print(
        f"[INFO] Loading Whisper model: {config.LOCAL_STT_MODEL} "
        f"(lang={config.LOCAL_STT_LANGUAGE or 'auto'})"
    )
    model = WhisperModel(
        config.LOCAL_STT_MODEL,
        device="cpu",
        compute_type=config.LOCAL_STT_COMPUTE_TYPE,
    )

    language = config.LOCAL_STT_LANGUAGE or None
    strategies = [
        {"language": language, "vad_filter": True},
        {"language": language, "vad_filter": False},
        {"language": None, "vad_filter": True},
        {"language": None, "vad_filter": False},
    ]

    last_error: Optional[Exception] = None
    for idx, strategy in enumerate(strategies, start=1):
        try:
            print(
                f"[INFO] STT attempt {idx}/{len(strategies)} "
                f"(lang={strategy['language'] or 'auto'}, vad={strategy['vad_filter']})"
            )
            segments, info = model.transcribe(
                audio_path,
                language=strategy["language"],
                vad_filter=strategy["vad_filter"],
            )
            text = "".join(segment.text for segment in segments).strip()
            if text:
                confidence = getattr(info, "language_probability", 1.0)
                print(f"[INFO] Transcript (conf={confidence:.2f}): {text}")
                return text
            print("[WARN] Empty transcript")
        except Exception as exc:
            last_error = exc
            print(f"[WARN] STT failed: {exc}")

    raise RuntimeError("Transcription failed") from last_error


def _say_feedback(message: str) -> None:
    if not config.ENABLE_TTS:
        return
    try:
        speak_text = _speak_text()
        speak_text(message, auto_play=config.ENABLE_PLAYBACK)
    except Exception as exc:
        print(f"[WARN] Feedback TTS failed: {exc}")


def _read_recommended_seq(json_path: str) -> int:
    path = Path(json_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    seq = int(data["recommended_seq"])
    if not 1 <= seq <= 6:
        raise ValueError(f"recommended_seq must be in [1, 6], got {seq}")
    return seq


def _run_pos_traj(recommended_json: str) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    pos_traj_path = repo_root / "Control_Part" / "reBotArm_control_py" / "example" / "Pos_Traj.py"
    if not pos_traj_path.exists():
        print(f"[ERROR] Pos_Traj.py not found: {pos_traj_path}")
        return 1

    seq = _read_recommended_seq(recommended_json)
    print(f"[INFO] Launching Pos_Traj for recommended_seq={seq}")
    completed = subprocess.run(
        [sys.executable, str(pos_traj_path), "--auto-start"],
        check=False,
    )
    if completed.returncode != 0:
        print(f"[ERROR] Pos_Traj exited with code {completed.returncode}")
    return int(completed.returncode)


def _listen_once(
    *,
    duration_sec: float,
    sample_rate: Optional[int],
    input_device: Optional[str],
    temp_audio_path: Optional[str],
    output_json: str,
    auto_speak: bool,
) -> int:
    _, _, record_audio_robustly, save_audio_to_wav = _audio_core()
    audio, sr = record_audio_robustly(
        duration_sec=duration_sec,
        target_sample_rate=sample_rate,
        input_device=input_device,
    )
    audio_path = save_audio_to_wav(audio, sr, output_path=temp_audio_path)
    request_text = transcribe_audio(audio_path)
    return _handle_request(request_text, output_json=output_json, auto_speak=auto_speak)


def _handle_request(request_text: str, *, output_json: str, auto_speak: bool) -> int:
    try:
        result = recommend_fruit(request_text)
    except Exception as exc:
        print(f"[ERROR] Fruit recommendation failed: {exc}")
        return 1

    written_path = write_result_json(result, output_json)

    print(f"[INFO] Request: {request_text}")
    print(f"[INFO] Recommended: {result.seq} - {result.name}")
    print(f"[INFO] Source: {result.source}")
    print(f"[INFO] JSON written to: {written_path}")
    print(f"[INFO] Voice text: {result.voice_text}")

    if auto_speak:
        _say_feedback(result.voice_text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fruit recommendation assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python voice_pipeline.py --text "我想吃点清爽的"
  python voice_pipeline.py --text "我要补充维C"
  python voice_pipeline.py
        """,
    )
    parser.add_argument("--text", help="Direct request text for testing")
    parser.add_argument("--duration", type=float, default=None, help="Recording duration in seconds")
    parser.add_argument("--input-device", default=None, help="Input device index or name")
    parser.add_argument("--sample-rate", type=int, default=None, help="Target sample rate")
    parser.add_argument(
        "--audio-temp",
        default=str(config.TEMP_AUDIO_PATH),
        help="Temporary wav path used for transcription",
    )
    parser.add_argument(
        "--output-json",
        default=str(config.FRUIT_OUTPUT_JSON_PATH),
        help="JSON file used to store the selected sequence number",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Print available input audio devices and exit",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable spoken feedback even if TTS is configured",
    )
    parser.add_argument(
        "--no-playback",
        action="store_true",
        help="Generate TTS text but do not play the audio",
    )
    args = parser.parse_args()

    if args.list_devices:
        try:
            import sounddevice as sd
        except Exception as exc:
            print(f"[ERROR] sounddevice not available: {exc}")
            return 1
        print("\n[INFO] Available input devices:")
        devices = sd.query_devices()
        found = False
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                found = True
                print(
                    f"  [{idx}] {dev.get('name', 'unknown')} "
                    f"(sr={dev.get('default_samplerate', '?')}, channels={dev.get('max_input_channels', 0)})"
                )
        if not found:
            print("  [WARN] No input devices found")
        print()
        return 0

    if args.no_playback:
        config.ENABLE_PLAYBACK = False

    auto_speak = not args.no_tts
    duration_sec = args.duration or config.AUDIO_DURATION_SEC

    if args.text:
        rc = _handle_request(args.text, output_json=args.output_json, auto_speak=auto_speak)
        if rc != 0:
            return rc
        return _run_pos_traj(args.output_json)

    init_audio_system, _, _, _ = _audio_core()
    init_audio_system()
    rc = _listen_once(
        duration_sec=duration_sec,
        sample_rate=args.sample_rate,
        input_device=args.input_device,
        temp_audio_path=args.audio_temp,
        output_json=args.output_json,
        auto_speak=auto_speak,
    )
    if rc != 0:
        return rc
    return _run_pos_traj(args.output_json)


if __name__ == "__main__":
    raise SystemExit(main())
