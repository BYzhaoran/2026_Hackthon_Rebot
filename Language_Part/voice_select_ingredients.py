import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI
from scipy.io.wavfile import read, write


def require_sounddevice_for_audio() -> Any:
    try:
        import sounddevice as sd  # type: ignore

        return sd
    except Exception as exc:
        raise RuntimeError(
            "Audio recording/playback requires PortAudio. "
            "Install with 'conda install -c conda-forge portaudio python-sounddevice' "
            "or on Ubuntu 'sudo apt install portaudio19-dev' then 'pip install sounddevice'."
        ) from exc


def list_input_devices() -> None:
    sd = require_sounddevice_for_audio()
    devices = sd.query_devices()
    print("[INFO] Available input devices:")
    for idx, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0)) > 0:
            default_sr = int(dev.get("default_samplerate", 0) or 0)
            print(f"  - index={idx}, name={dev.get('name', 'unknown')}, default_samplerate={default_sr}")


def get_all_input_device_indices(sd: Any) -> List[int]:
    devices = sd.query_devices()
    indices: List[int] = []
    for idx, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0)) > 0:
            indices.append(idx)
    return indices


def get_default_input_device_index(sd: Any) -> Optional[int]:
    default_device = getattr(sd.default, "device", None)
    if isinstance(default_device, (list, tuple)) and default_device:
        try:
            return int(default_device[0])
        except Exception:
            return None
    if isinstance(default_device, int):
        return default_device
    return None


def resolve_device_index(sd: Any, input_device: Optional[int]) -> Optional[int]:
    if input_device is not None:
        return int(input_device)
    return get_default_input_device_index(sd)


def get_device_default_sample_rate(sd: Any, device_index: Optional[int]) -> Optional[int]:
    try:
        if device_index is None:
            dev = sd.query_devices(kind="input")
        else:
            dev = sd.query_devices(device_index)
        default_sr = int(float(dev.get("default_samplerate", 0) or 0))
        return default_sr if default_sr > 0 else None
    except Exception:
        return None


def build_sample_rate_candidates(requested_sr: int, device_default_sr: Optional[int]) -> List[int]:
    candidates: List[int] = []
    for sr in [requested_sr, 16000, 44100, 48000, device_default_sr or 0]:
        if isinstance(sr, int) and sr > 0 and sr not in candidates:
            candidates.append(sr)
    return candidates


def load_ingredients(db_path: Path) -> List[Dict[str, Any]]:
    with db_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("ingredients"), list):
        items = payload["ingredients"]
    else:
        raise ValueError("Database JSON must be a list or a dict with 'ingredients' list")

    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if "id" not in item or "name" not in item:
            continue
        try:
            item_id = int(item["id"])
        except (TypeError, ValueError):
            continue
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        normalized.append(item)

    if not normalized:
        raise ValueError("No valid ingredient items with unique integer 'id' and 'name' found")

    normalized.sort(key=lambda x: int(x["id"]))
    return normalized


def record_audio_to_wav(
    output_path: Path,
    duration_sec: float,
    sample_rate: int,
    input_device: Optional[int] = None,
) -> int:
    sd = require_sounddevice_for_audio()
    if duration_sec <= 0:
        raise ValueError("duration_sec must be > 0")

    device_index = resolve_device_index(sd, input_device)
    min_rms = float(os.getenv("LOCAL_STT_MIN_RMS", "0.001").strip() or "0.001")

    if input_device is not None:
        device_candidates = [device_index]
    else:
        device_candidates = []
        if device_index is not None:
            device_candidates.append(device_index)
        for idx in get_all_input_device_indices(sd):
            if idx not in device_candidates:
                device_candidates.append(idx)

    if not device_candidates:
        raise RuntimeError("No input audio device found")

    last_error: Optional[Exception] = None
    for dev_idx in device_candidates:
        device_default_sr = get_device_default_sample_rate(sd, dev_idx)
        sample_rates = build_sample_rate_candidates(sample_rate, device_default_sr)

        for sr in sample_rates:
            frames = int(duration_sec * sr)
            if frames <= 0:
                continue

            try:
                dev_note = f", device={dev_idx}" if dev_idx is not None else ""
                print(f"[INFO] Recording {duration_sec:.1f}s audio at {sr}Hz{dev_note}...")
                audio = sd.rec(
                    frames,
                    samplerate=sr,
                    channels=1,
                    dtype="float32",
                    device=dev_idx,
                )
                sd.wait()

                audio_float = audio.reshape(-1).astype(np.float32)
                rms = float(np.sqrt(np.mean(np.square(audio_float)))) if audio_float.size else 0.0
                print(f"[INFO] Recorded audio RMS={rms:.6f}")
                if rms < min_rms:
                    print(
                        f"[WARN] Audio too quiet on device={dev_idx} sr={sr} (rms={rms:.6f} < {min_rms:.6f}), trying next candidate"
                    )
                    continue

                audio_int16 = np.int16(np.clip(audio, -1.0, 1.0) * 32767)
                write(str(output_path), sr, audio_int16)
                print(f"[INFO] Audio saved: {output_path}")
                return sr
            except Exception as exc:
                last_error = exc
                print(f"[WARN] Failed to record on device={dev_idx} at {sr}Hz: {exc}")

    raise RuntimeError(
        "Unable to capture usable audio from available devices/sample rates. "
        "Try --list-devices and set --input-device, speak louder/closer, or reduce LOCAL_STT_MIN_RMS."
    ) from last_error


def play_wav(audio_path: Path) -> None:
    sd = require_sounddevice_for_audio()
    sample_rate, audio_data = read(str(audio_path))
    print(f"[INFO] Playing audio: {audio_path}")
    sd.play(audio_data, samplerate=sample_rate)
    sd.wait()


def load_secret_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("Secret config must be a JSON object")
    return payload


def str_to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_proxy_env(secret_cfg: Dict[str, Any]) -> None:
    disable_proxy = str_to_bool(str(secret_cfg.get("DEEPSEEK_DISABLE_PROXY", ""))) or str_to_bool(
        os.getenv("DEEPSEEK_DISABLE_PROXY", "")
    )

    proxy_keys = ["ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]

    if disable_proxy:
        for key in proxy_keys:
            os.environ.pop(key, None)
        print("[INFO] Proxy disabled by DEEPSEEK_DISABLE_PROXY")
        return

    for key in proxy_keys:
        value = os.getenv(key, "")
        if value.startswith("socks://"):
            fixed = "socks5://" + value[len("socks://") :]
            os.environ[key] = fixed
            print(f"[INFO] Normalized proxy {key}: socks:// -> socks5://")


def transcribe_audio_local(audio_path: Path, model_size: str, language: str) -> str:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Local STT fallback requires faster-whisper. Install with 'pip install faster-whisper'."
        ) from exc

    compute_type = os.getenv("LOCAL_STT_COMPUTE_TYPE", "int8").strip() or "int8"
    domain_hint = os.getenv(
        "LOCAL_STT_HINT",
        "食材名称：仙女果 蓝莓 草莓 奇异果 香蕉 芒果 杨桃 番茄 土豆 洋葱 鸡肉 牛肉 鸡蛋 豆腐 米饭 面条 牛奶",
    ).strip()
    print(f"[INFO] Local STT enabled: model={model_size}, language={language}, compute={compute_type}")
    model = WhisperModel(model_size, compute_type=compute_type)

    configured_lang = language.strip() if language.strip() else None
    strategies = [
        {"language": configured_lang, "vad_filter": True},
        {"language": configured_lang, "vad_filter": False},
        {"language": None, "vad_filter": True},
        {"language": None, "vad_filter": False},
    ]

    best_text = ""
    best_score = float("-inf")

    for i, st in enumerate(strategies, start=1):
        lang = st["language"]
        vad = bool(st["vad_filter"])
        lang_note = lang if lang else "auto"
        print(f"[INFO] Local STT try {i}: language={lang_note}, vad_filter={vad}")

        segments, _info = model.transcribe(
            str(audio_path),
            language=lang,
            vad_filter=vad,
            beam_size=5,
            condition_on_previous_text=False,
            initial_prompt=domain_hint,
        )
        seg_list = list(segments)
        text = "".join(seg.text for seg in seg_list).strip()
        if not text:
            continue

        avg_logprob = float(np.mean([float(getattr(seg, "avg_logprob", -5.0)) for seg in seg_list]))
        no_speech_prob = float(np.mean([float(getattr(seg, "no_speech_prob", 1.0)) for seg in seg_list]))
        zh_char_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        score = avg_logprob - no_speech_prob + (0.02 * zh_char_count)

        if score > best_score:
            best_score = score
            best_text = text

    if best_text:
        print(f"[INFO] Local STT selected best candidate, score={best_score:.3f}")
        return best_text

    sample_rate, audio_data = read(str(audio_path))
    # Normalize to float for consistent diagnostics across int16/float32 WAV.
    audio_float = audio_data.astype(np.float32)
    if audio_float.ndim > 1:
        audio_float = audio_float[:, 0]
    if np.max(np.abs(audio_float)) > 1.5:
        audio_float = audio_float / 32767.0
    rms = float(np.sqrt(np.mean(np.square(audio_float)))) if audio_float.size else 0.0
    duration = float(audio_float.size / sample_rate) if sample_rate > 0 else 0.0
    raise RuntimeError(
        "Local STT produced empty text after retries. "
        f"audio_duration={duration:.2f}s, rms={rms:.6f}. "
        "Try speaking louder/closer, set --input-device explicitly, or set LOCAL_STT_LANGUAGE to empty for auto detect."
    )


def build_ingredient_prompt(ingredients: List[Dict[str, Any]]) -> str:
    lines = []
    for item in ingredients:
        aliases = item.get("aliases", [])
        aliases_text = ", ".join(str(a) for a in aliases) if isinstance(aliases, list) and aliases else ""
        category = str(item.get("category", ""))
        extras = []
        if aliases_text:
            extras.append(f"aliases: {aliases_text}")
        if category:
            extras.append(f"category: {category}")
        suffix = f" ({'; '.join(extras)})" if extras else ""
        lines.append(f"{int(item['id'])}. {item['name']}{suffix}")
    return "\n".join(lines)


def extract_selected_ids(raw: str) -> List[int]:
    raw = raw.strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            ids = data.get("selected_ids", [])
            if isinstance(ids, list):
                return sorted({int(x) for x in ids})
    except Exception:
        pass

    matches = re.findall(r"\d+", raw)
    return sorted({int(x) for x in matches})


def select_ingredients(
    client: OpenAI,
    chat_model: str,
    request_text: str,
    ingredients: List[Dict[str, Any]],
) -> List[int]:
    ingredient_text = build_ingredient_prompt(ingredients)

    system_prompt = (
        "You are a strict ingredient selector. "
        "Given a user cooking request and a numbered ingredient database, "
        "return only a JSON object with key 'selected_ids' whose value is a list of integers. "
        "Do not include any explanation."
    )

    user_prompt = (
        "User request:\n"
        f"{request_text}\n\n"
        "Numbered ingredient database:\n"
        f"{ingredient_text}\n\n"
        "Rules:\n"
        "1) Choose only IDs that are relevant to the user request.\n"
        "2) Use IDs from the database only.\n"
        "3) If nothing matches, return {'selected_ids': []} as JSON.\n"
        "Output format example: {\"selected_ids\": [1, 3, 8]}"
    )

    resp = client.chat.completions.create(
        model=chat_model,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = (resp.choices[0].message.content or "").strip()
    return extract_selected_ids(content)


def build_confirmation_text(selected_items: List[Dict[str, Any]]) -> str:
    if not selected_items:
        return "没有匹配到明确食材，请再说一遍你需要的食材名称。"

    parts = [f"{int(item['id'])}号{item['name']}" for item in selected_items]
    joined = "，".join(parts)
    return f"已为你确认食材：{joined}。请确认是否正确。"


def make_tts_client(secret_cfg: Dict[str, Any], fallback_client: OpenAI) -> OpenAI:
    tts_api_key = str(secret_cfg.get("TTS_API_KEY", "")).strip() or os.getenv("TTS_API_KEY", "").strip()
    tts_base_url = str(secret_cfg.get("TTS_BASE_URL", "")).strip() or os.getenv("TTS_BASE_URL", "").strip()

    if not tts_api_key and not tts_base_url:
        return fallback_client

    if not tts_api_key:
        raise EnvironmentError("TTS_API_KEY is required when TTS_BASE_URL is set")

    if not tts_base_url:
        tts_base_url = "https://api.openai.com/v1"

    return OpenAI(api_key=tts_api_key, base_url=tts_base_url)


def synthesize_confirmation_audio(
    client: OpenAI,
    text: str,
    tts_model: str,
    tts_voice: str,
    tts_output_path: Path,
) -> Path:
    try:
        speech = client.audio.speech.create(
            model=tts_model,
            voice=tts_voice,
            input=text,
        )
    except Exception as exc:
        raise RuntimeError(
            "TTS generation failed. Check TTS model/base URL/API key compatibility."
        ) from exc

    if hasattr(speech, "stream_to_file"):
        speech.stream_to_file(str(tts_output_path))
    else:
        audio_bytes = getattr(speech, "content", None)
        if not isinstance(audio_bytes, (bytes, bytearray)):
            raise RuntimeError("TTS API returned no audio content")
        with tts_output_path.open("wb") as f:
            f.write(audio_bytes)

    return tts_output_path


def save_output(
    output_path: Path,
    request_text: str,
    selected_ids: List[int],
    ingredients: List[Dict[str, Any]],
    confirmation_text: str,
    confirmation_audio_path: Optional[Path],
) -> None:
    item_map = {int(x["id"]): x for x in ingredients}
    selected_items = [item_map[i] for i in selected_ids if i in item_map]
    numbered_selection = [
        {
            "seq": idx,
            "id": int(item["id"]),
            "name": item.get("name", ""),
            "category": item.get("category", ""),
        }
        for idx, item in enumerate(selected_items, start=1)
    ]

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_text": request_text,
        "selected_ids": selected_ids,
        "numbered_selection": numbered_selection,
        "selected_items": selected_items,
        "confirmation_text": confirmation_text,
        "confirmation_audio_path": str(confirmation_audio_path) if confirmation_audio_path else "",
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def make_chat_client(secret_cfg: Dict[str, Any]) -> OpenAI:
    normalize_proxy_env(secret_cfg)

    api_key = str(secret_cfg.get("DEEPSEEK_API_KEY", "")).strip() or os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("DEEPSEEK_API_KEY is required")

    base_url = str(secret_cfg.get("DEEPSEEK_BASE_URL", "")).strip() or os.getenv(
        "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
    ).strip()
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local speech-to-text + ingredient ID selection"
    )
    parser.add_argument("--db", default="ingredients_db.json", help="Ingredient database JSON path")
    parser.add_argument("--output", default="selected_ingredients.json", help="Output JSON path")
    parser.add_argument(
        "--audio-temp",
        default="speech_input.wav",
        help="Temporary WAV path for recorded audio",
    )
    parser.add_argument(
        "--config",
        default="secrets.local.json",
        help="Local secret JSON path",
    )
    parser.add_argument("--duration", type=float, default=5.0, help="Recording duration in seconds")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Recording sample rate")
    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="Input device index for recording (use --list-devices to inspect)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available input devices and exit",
    )
    parser.add_argument(
        "--playback",
        dest="playback",
        action="store_true",
        help="Play recorded audio before transcription",
    )
    parser.add_argument(
        "--no-playback",
        dest="playback",
        action="store_false",
        help="Do not play recorded audio",
    )
    parser.set_defaults(playback=True)
    parser.add_argument(
        "--text",
        default="",
        help="Optional direct request text. If set, skip recording and transcription.",
    )
    parser.add_argument(
        "--stt-model",
        default="",
        help="Reserved for compatibility. Local STT is used by default.",
    )
    parser.add_argument(
        "--chat-model",
        default="",
        help="Chat model name",
    )
    parser.add_argument(
        "--tts-output",
        default="confirmation_reply.mp3",
        help="Output audio file path for TTS confirmation",
    )
    parser.add_argument(
        "--disable-tts",
        action="store_true",
        help="Disable TTS confirmation generation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_devices:
        list_input_devices()
        return 0

    db_path = Path(args.db)
    out_path = Path(args.output)
    audio_path = Path(args.audio_temp)
    tts_output_path = Path(args.tts_output)
    config_path = Path(args.config)

    try:
        ingredients = load_ingredients(db_path)
        secret_cfg = load_secret_config(config_path)
        chat_client = make_chat_client(secret_cfg)
        tts_client = make_tts_client(secret_cfg, fallback_client=chat_client)

        local_stt_model = str(secret_cfg.get("LOCAL_STT_MODEL", "small")).strip() or os.getenv(
            "LOCAL_STT_MODEL", "small"
        ).strip()
        local_stt_language = str(secret_cfg.get("LOCAL_STT_LANGUAGE", "zh")).strip() or os.getenv(
            "LOCAL_STT_LANGUAGE", "zh"
        ).strip()
        chat_model = (
            args.chat_model.strip()
            or str(secret_cfg.get("DEEPSEEK_CHAT_MODEL", "")).strip()
            or os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat").strip()
        )
        tts_model = str(secret_cfg.get("TTS_MODEL", "")).strip() or os.getenv("TTS_MODEL", "gpt-4o-mini-tts").strip()
        tts_voice = str(secret_cfg.get("TTS_VOICE", "")).strip() or os.getenv("TTS_VOICE", "alloy").strip()
        tts_enabled = (not args.disable_tts) and str_to_bool(
            str(secret_cfg.get("TTS_ENABLED", "true")).strip() or os.getenv("TTS_ENABLED", "true").strip()
        )

        request_text = args.text.strip()
        if not request_text:
            used_sr = record_audio_to_wav(
                audio_path,
                duration_sec=args.duration,
                sample_rate=args.sample_rate,
                input_device=args.input_device,
            )
            if args.playback:
                play_wav(audio_path)
            request_text = transcribe_audio_local(
                audio_path=audio_path,
                model_size=local_stt_model,
                language=local_stt_language,
            )
            print(f"[INFO] Recording sample rate used: {used_sr}Hz")

        print(f"[INFO] Transcribed request: {request_text}")

        selected_ids = select_ingredients(
            client=chat_client,
            chat_model=chat_model,
            request_text=request_text,
            ingredients=ingredients,
        )

        item_map = {int(x["id"]): x for x in ingredients}
        selected_items = [item_map[i] for i in selected_ids if i in item_map]
        confirmation_text = build_confirmation_text(selected_items)
        confirmation_audio_path: Optional[Path] = None

        if tts_enabled:
            confirmation_audio_path = synthesize_confirmation_audio(
                client=tts_client,
                text=confirmation_text,
                tts_model=tts_model,
                tts_voice=tts_voice,
                tts_output_path=tts_output_path,
            )
            print(f"[INFO] TTS confirmation audio saved: {confirmation_audio_path}")

        save_output(
            output_path=out_path,
            request_text=request_text,
            selected_ids=selected_ids,
            ingredients=ingredients,
            confirmation_text=confirmation_text,
            confirmation_audio_path=confirmation_audio_path,
        )

        print(f"[INFO] Selected IDs: {selected_ids}")
        print(f"[INFO] Output written to: {out_path}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
