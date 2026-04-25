"""
Voice-to-Ingredient Pipeline (重构版本)
设计灵感：Fridge/Talk_main.py 模块化架构 + 健壮的多策略设备管理

Pipeline:
  🎙️  录音 → 🔤 STT转文字 → 🤖 DeepSeek选择食材 → 💬 生成确认文本 → 🔊 TTS合成 → 💾 保存JSON
"""

import json
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List

# 支持相对导入和直接运行
try:
    from . import config
    from .speech_core import add_playful_tone, speak_text
    from .ingredient_selection_core import SelectionOutcome, best_effort_select_ids, extract_selected_ids
    from .wake_core import contains_wake_word, strip_wake_word
except ImportError:
    # 直接运行（非模块模式）
    import config
    from speech_core import add_playful_tone, speak_text
    from ingredient_selection_core import SelectionOutcome, best_effort_select_ids, extract_selected_ids
    from wake_core import contains_wake_word, strip_wake_word

try:
    from faster_whisper import WhisperModel
    from openai import OpenAI
except ImportError as e:
    print(f"[ERROR] Missing dependencies: {e}")
    print("Install with: pip install faster-whisper openai")
    sys.exit(1)


# ==================== STT 模块 ====================
def transcribe_audio_local(
    audio_path: str,
    language: str = None,
    model_size: str = None,
) -> str:
    """
    使用 faster-whisper 进行本地语音转文本
    
    Args:
        audio_path: 音频文件路径
        language: 语言代码（zh, en, None自动识别），默认使用 config.LOCAL_STT_LANGUAGE
        model_size: 模型大小（tiny/base/small/medium），默认使用 config.LOCAL_STT_MODEL
        
    Returns:
        转录文本
    """
    language = language or config.LOCAL_STT_LANGUAGE
    model_size = model_size or config.LOCAL_STT_MODEL

    print(f"[INFO] Transcribing with faster-whisper ({model_size} model, lang={language or 'auto'})...")

    try:
        model = WhisperModel(model_size, device="cpu", compute_type=config.LOCAL_STT_COMPUTE_TYPE)
        
        # 多策略重试（处理边界情况）
        strategies = []
        if config.LOCAL_STT_STRATEGY_RETRY:
            strategies = [
                {"lang": language, "vad": True},
                {"lang": language, "vad": False},
                {"lang": None, "vad": True},  # 自动识别语言
                {"lang": None, "vad": False},
            ]
        else:
            strategies = [{"lang": language, "vad": True}]

        results = []
        for i, strategy in enumerate(strategies):
            print(f"  Strategy {i+1}/{len(strategies)}: lang={strategy['lang'] or 'auto'}, vad={strategy['vad']}")
            
            try:
                segments, info = model.transcribe(
                    audio_path,
                    language=strategy["lang"],
                    vad_filter=strategy["vad"],
                )
                text = "".join([s.text for s in segments]).strip()
                
                if text:
                    confidence = info.language_probability if hasattr(info, 'language_probability') else 1.0
                    results.append((text, confidence, i))
                    print(f"    ✅ Got text (conf={confidence:.2f}): {text[:50]}...")
                else:
                    print(f"    ⚠️  Empty text")
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
        
        if not results:
            raise RuntimeError("All transcription strategies failed")
        
        # 选择置信度最高的结果
        best_text, best_conf, best_idx = max(results, key=lambda x: x[1])
        print(f"[INFO] Selected: strategy {best_idx+1}, text: {best_text}")
        return best_text
        
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        raise


# ==================== 食材选择模块 ====================
def load_ingredients_db(db_path: str) -> Dict:
    """
    加载食材数据库
    
    Returns:
        {ingredients: [{id, name, aliases, category}, ...]}
    """
    with open(db_path) as f:
        data = json.load(f)
    print(f"[INFO] Loaded {len(data['ingredients'])} ingredients from {db_path}")
    return data


def make_chat_client() -> OpenAI:
    api_key = str(getattr(config, "DEEPSEEK_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    base_url = str(getattr(config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")).strip()
    return OpenAI(api_key=api_key, base_url=base_url)


def select_ingredients(
    request_text: str,
    ingredients_db: Dict,
    api_key: str = None,
    base_url: str = None,
    model: str = None,
) -> SelectionOutcome:
    """
    使用 DeepSeek API 根据用户请求选择食材
    
    Args:
        request_text: 用户请求文本（如 "我想要蓝莓和芒果"）
        ingredients_db: 食材数据库
        api_key: DeepSeek API Key，默认使用 config.DEEPSEEK_API_KEY
        base_url: API Base URL，默认使用 config.DEEPSEEK_BASE_URL
        model: 模型名称，默认使用 config.DEEPSEEK_CHAT_MODEL
        
    Returns:
        选中的食材 ID 列表，以及必要时的兜底说明
    """
    api_key = api_key or config.DEEPSEEK_API_KEY
    base_url = base_url or config.DEEPSEEK_BASE_URL
    model = model or config.DEEPSEEK_CHAT_MODEL

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not configured")

    print(f"[INFO] Calling DeepSeek API for ingredient selection...")
    
    # 构建食材列表提示
    ingredients_list = "\n".join([
        f"- ID {ing['id']}: {ing['name']} (别名: {', '.join(ing['aliases'])}, 类别: {ing['category']})"
        for ing in ingredients_db["ingredients"]
    ])

    system_prompt = """你是一个智能食材选择助手。用户会告诉你他们想要哪些食材。
根据用户的请求，从下面的食材列表中选择相应的食材，返回它们的 ID 号。
如果没有完全匹配，也要返回最接近的 1-3 个候选，而不要返回空列表。
返回格式：只返回 JSON 对象 {"selected_ids": [id1, id2, ...]}，不要其他文本。

可用食材：
""" + ingredients_list

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request_text},
            ],
            temperature=0.3,
        )
        
        response_text = response.choices[0].message.content.strip()
        print(f"  API Response: {response_text}")
        
        # 解析 JSON 响应
        try:
            result = json.loads(response_text)
            selected_ids = result.get("selected_ids", [])
            selected_ids = sorted({int(x) for x in selected_ids})
            if selected_ids:
                print(f"  ✅ Selected IDs: {selected_ids}")
                return SelectionOutcome(ids=selected_ids)
            fallback = best_effort_select_ids(request_text, ingredients_db["ingredients"])
            print(f"  ⚠️  Empty result from API, fallback IDs: {fallback.ids}")
            return fallback
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to parse API response as JSON: {e}")
            fallback = best_effort_select_ids(request_text, ingredients_db["ingredients"])
            print(f"  ⚠️  Fallback IDs: {fallback.ids}")
            return fallback
            
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        fallback = best_effort_select_ids(request_text, ingredients_db["ingredients"])
        print(f"  ⚠️  Fallback IDs: {fallback.ids}")
        return fallback


# ==================== 确认消息生成 ====================
def generate_confirmation_text(
    selected_ids: List[int],
    ingredients_db: Dict,
    selection_note: str = "",
) -> str:
    """
    生成确认消息文本
    
    Args:
        selected_ids: 选中的食材 ID 列表
        ingredients_db: 食材数据库
        
    Returns:
        确认文本（如 "已为你确认食材：蓝莓，芒果。请确认是否正确。"）
    """
    if not selected_ids:
        return "未找到匹配的食材。"
    
    # 构建食材映射
    id_to_ingredient = {ing["id"]: ing for ing in ingredients_db["ingredients"]}
    
    # 生成语音显示列表（只读名称，不读序号）
    items = []
    for id_ in selected_ids:
        if id_ in id_to_ingredient:
            ing = id_to_ingredient[id_]
            items.append(ing["name"])
    
    if not items:
        return "未找到匹配的食材。"
    
    confirmation = f"已为你确认食材：{', '.join(items)}。请确认是否正确。"
    if selection_note:
        confirmation += f" {selection_note}"
    return add_playful_tone(confirmation)


def _import_audio_core():
    try:
        from .audio_core import record_audio_robustly, save_audio_to_wav, init_audio_system, play_prompt_sound
    except ImportError:
        from audio_core import record_audio_robustly, save_audio_to_wav, init_audio_system, play_prompt_sound
    return record_audio_robustly, save_audio_to_wav, init_audio_system, play_prompt_sound


def process_request_cycle(
    request_text: str,
    ingredients_db: Dict,
    chat_client: OpenAI,
    chat_model: str,
    disable_tts: bool,
    tts_engine: str,
    tts_output_path: Path,
) -> Dict[str, object]:
    """执行一次“识别 -> 选择 -> 确认 -> TTS -> 保存”的完整周期。"""
    print(f"  → Request: {request_text}\n")

    print("🤖 Step 3: Selecting ingredients (DeepSeek)...")
    selection = select_ingredients(request_text, ingredients_db, model=chat_model)
    selected_ids = selection.ids
    print()

    print("💬 Step 4: Generating confirmation text...")
    confirmation_text = generate_confirmation_text(selected_ids, ingredients_db, selection_note=selection.note)
    print(f"  → {confirmation_text}\n")

    confirmation_audio_path = ""
    if not disable_tts:
        print("🔊 Step 5: Synthesizing confirmation audio...")
        try:
            speech_result = speak_text(
                confirmation_text,
                engine=tts_engine,
                output_path=str(tts_output_path),
                auto_play=config.ENABLE_PLAYBACK,
            )
            confirmation_audio_path = speech_result.audio_path
            if confirmation_audio_path:
                print(f"  → {confirmation_audio_path}\n")
        except Exception as e:
            print(f"  ⚠️  TTS failed: {e}, continuing without audio\n")
    else:
        print("⏭️  Step 5: TTS disabled (--disable-tts)\n")

    return {
        "selected_ids": selected_ids,
        "selection_note": selection.note,
        "confirmation_text": confirmation_text,
        "confirmation_audio_path": confirmation_audio_path,
    }


def run_wake_loop(
    ingredients_db: Dict,
    chat_client: OpenAI,
    chat_model: str,
    command_window_sec: float,
    input_device: Optional[str],
    sample_rate: Optional[int],
    disable_tts: bool,
    tts_engine: str,
    tts_output_path: Path,
    wake_window_sec: Optional[float] = None,
) -> None:
    """持续监听唤醒词，检测到后处理一次命令。"""
    record_audio_robustly, save_audio_to_wav, init_audio_system, play_prompt_sound = _import_audio_core()
    init_audio_system()

    wake_window = float(wake_window_sec or getattr(config, "WAKE_LISTEN_WINDOW_SEC", 2.5))
    command_window = float(command_window_sec or getattr(config, "WAKE_COMMAND_WINDOW_SEC", 5.0))
    cooldown_sec = float(getattr(config, "WAKE_COOLDOWN_SEC", 1.5))

    print(f"[INFO] Wake loop enabled. Wake word: {config.WAKE_WORD}")
    print(f"[INFO] Listening window={wake_window}s, command window={command_window}s")

    while True:
        print("\n🎧 Waiting for wake word...")
        wake_audio, wake_sr = record_audio_robustly(
            duration_sec=wake_window,
            target_sample_rate=sample_rate,
            input_device=input_device,
        )
        wake_audio_path = save_audio_to_wav(wake_audio, wake_sr)
        wake_text = transcribe_audio_local(wake_audio_path)
        print(f"[INFO] Wake transcript: {wake_text}")

        matched, alias = contains_wake_word(wake_text)
        if not matched:
            continue
        print(f"[INFO] Wake word matched: {alias or config.WAKE_WORD}")
        play_prompt_sound("wake")

        request_text = strip_wake_word(wake_text)
        if request_text:
            print(f"[INFO] Wake command extracted: {request_text}")
        else:
            play_prompt_sound("record")
            print("[INFO] Wake word detected, waiting for command...")
            cmd_audio, cmd_sr = record_audio_robustly(
                duration_sec=command_window,
                target_sample_rate=sample_rate,
                input_device=input_device,
            )
            cmd_audio_path = save_audio_to_wav(cmd_audio, cmd_sr)
            request_text = transcribe_audio_local(cmd_audio_path)
            request_text = strip_wake_word(request_text)
            print(f"[INFO] Command transcript: {request_text}")

        if not request_text:
            print("[WARN] Empty command after wake word, continuing to listen")
            time.sleep(cooldown_sec)
            continue

        result = process_request_cycle(
            request_text=request_text,
            ingredients_db=ingredients_db,
            chat_client=chat_client,
            chat_model=chat_model,
            disable_tts=disable_tts,
            tts_engine=tts_engine,
            tts_output_path=tts_output_path,
        )

        save_output_json(
            output_path=str(config.OUTPUT_JSON_PATH),
            request_text=request_text,
            selected_ids=result["selected_ids"],
            ingredients_db=ingredients_db,
            confirmation_text=result["confirmation_text"],
            confirmation_audio_path=result["confirmation_audio_path"],
            selection_note=result["selection_note"],
        )
        print(f"[INFO] Selected IDs: {result['selected_ids']}")
        print(f"[INFO] Output written to: {config.OUTPUT_JSON_PATH}")
        time.sleep(cooldown_sec)


# ==================== 输出格式化 ====================
def save_output_json(
    output_path: str,
    request_text: str,
    selected_ids: List[int],
    ingredients_db: Dict,
    confirmation_text: str,
    confirmation_audio_path: str = "",
    selection_note: str = "",
) -> None:
    """
    保存结构化输出 JSON 文件
    
    Args:
        output_path: 输出文件路径
        request_text: 原始请求文本
        selected_ids: 选中的食材 ID
        ingredients_db: 食材数据库
        confirmation_text: 确认消息
        confirmation_audio_path: 确认消息语音文件路径（可选）
    """
    # 构建食材映射
    id_to_ingredient = {ing["id"]: ing for ing in ingredients_db["ingredients"]}
    
    # 序号列表（带序列号）
    numbered_selection = [
        {
            "seq": i+1,
            "id": id_,
            "name": id_to_ingredient[id_]["name"],
            "category": id_to_ingredient[id_]["category"],
        }
        for i, id_ in enumerate(selected_ids)
        if id_ in id_to_ingredient
    ]
    
    # 完整选中项
    selected_items = [
        id_to_ingredient[id_] 
        for id_ in selected_ids 
        if id_ in id_to_ingredient
    ]
    
    output_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_text": request_text,
        "selected_ids": selected_ids,
        "numbered_selection": numbered_selection,
        "selected_items": selected_items,
        "confirmation_text": confirmation_text,
        "confirmation_audio_path": confirmation_audio_path,
        "selection_note": selection_note,
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"[INFO] Output saved to {output_path}")


# ==================== 主流程 ====================
def main_voice_pipeline(
    duration_sec: Optional[float] = None,
    input_device: Optional[str] = None,
    sample_rate: Optional[int] = None,
    disable_tts: bool = False,
    text_input: Optional[str] = None,  # 文本模式（用于测试）
    continuous: bool = False,
    wake_window_sec: Optional[float] = None,
    wake_command_window_sec: Optional[float] = None,
) -> None:
    """
    完整的语音到食材选择管道
    
    Args:
        duration_sec: 录音时长（秒）
        input_device: 输入设备（名称/索引）
        sample_rate: 采样率（Hz）
        disable_tts: 禁用 TTS 确认音频
        text_input: 直接提供文本（跳过录音和 STT）
        continuous: 持续运行并等待唤醒词
        wake_window_sec: 唤醒词监听窗口
        wake_command_window_sec: 唤醒后命令监听窗口
    """
    print("\n" + "="*70)
    print("🎙️  Voice-to-Ingredient Selection Pipeline (Fridge 架构版)")
    print("="*70 + "\n")

    # 统一处理代理变量，避免 socks:// 导致 STT/API 初始化失败
    config.normalize_proxy_env(disable_proxy=config.DEEPSEEK_DISABLE_PROXY)
    ingredients_db = load_ingredients_db(str(config.INGREDIENTS_DB_PATH))

    chat_client = make_chat_client()
    chat_model = config.DEEPSEEK_CHAT_MODEL
    tts_engine = config.TTS_ENGINE
    tts_output_path = Path(config.TTS_OUTPUT_PATH)

    if text_input:
        print(f"[INFO] Using provided text: {text_input}\n")
        result = process_request_cycle(
            request_text=text_input,
            ingredients_db=ingredients_db,
            chat_client=chat_client,
            chat_model=chat_model,
            disable_tts=disable_tts,
            tts_engine=tts_engine,
            tts_output_path=tts_output_path,
        )
        save_output_json(
            output_path=str(config.OUTPUT_JSON_PATH),
            request_text=text_input,
            selected_ids=result["selected_ids"],
            ingredients_db=ingredients_db,
            confirmation_text=result["confirmation_text"],
            confirmation_audio_path=result["confirmation_audio_path"],
            selection_note=result["selection_note"],
        )
        return

    if continuous:
        run_wake_loop(
            ingredients_db=ingredients_db,
            chat_client=chat_client,
            chat_model=chat_model,
            command_window_sec=wake_command_window_sec or config.WAKE_COMMAND_WINDOW_SEC,
            input_device=input_device,
            sample_rate=sample_rate,
            disable_tts=disable_tts,
            tts_engine=tts_engine,
            tts_output_path=tts_output_path,
            wake_window_sec=wake_window_sec,
        )
        return

    record_audio_robustly, save_audio_to_wav, init_audio_system = _import_audio_core()
    init_audio_system()
    print("🎙️  Step 1: Recording audio...")
    audio, sr = record_audio_robustly(
        duration_sec=duration_sec,
        target_sample_rate=sample_rate,
        input_device=input_device,
    )
    audio_path = save_audio_to_wav(audio, sr)
    print("\n🔤 Step 2: Transcribing audio...")
    request_text = transcribe_audio_local(audio_path)

    result = process_request_cycle(
        request_text=request_text,
        ingredients_db=ingredients_db,
        chat_client=chat_client,
        chat_model=chat_model,
        disable_tts=disable_tts,
        tts_engine=tts_engine,
        tts_output_path=tts_output_path,
    )
    save_output_json(
        output_path=str(config.OUTPUT_JSON_PATH),
        request_text=request_text,
        selected_ids=result["selected_ids"],
        ingredients_db=ingredients_db,
        confirmation_text=result["confirmation_text"],
        confirmation_audio_path=result["confirmation_audio_path"],
        selection_note=result["selection_note"],
    )

    print("\n" + "="*70)
    print("✅ Pipeline completed successfully!")
    print("="*70 + "\n")


# ==================== CLI 入口 ====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Voice-to-Ingredient Selection with Fridge Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 语音模式（使用麦克风）
  python -m voice_select_ingredients
  
  # 指定设备和采样率
  python -m voice_select_ingredients --input-device 1 --sample-rate 44100
  
  # 文本模式（用于测试）
  python -m voice_select_ingredients --text "我想要蓝莓和芒果"
  
  # 禁用 TTS 确认
  python -m voice_select_ingredients --disable-tts
        """,
    )
    
    parser.add_argument(
        "--text",
        help="直接提供请求文本（跳过录音和STT，用于测试）",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="录音时长（秒），默认从 config 读取",
    )
    parser.add_argument(
        "--input-device",
        help="输入设备索引或名称，默认使用系统默认设备",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        help="采样率（Hz），默认自动协商",
    )
    parser.add_argument(
        "--disable-tts",
        action="store_true",
        help="禁用 TTS 确认语音",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="持续监听唤醒词并循环处理",
    )
    parser.add_argument(
        "--wake-window",
        type=float,
        default=None,
        help="唤醒词监听窗口（秒），默认使用 config.WAKE_LISTEN_WINDOW_SEC",
    )
    parser.add_argument(
        "--wake-command-window",
        type=float,
        default=None,
        help="唤醒后命令录音窗口（秒），默认使用 config.WAKE_COMMAND_WINDOW_SEC",
    )
    parser.add_argument(
        "--db",
        default="ingredients_db.json",
        help="食材数据库 JSON 文件路径",
    )
    parser.add_argument(
        "--output",
        default="selected_ingredients.json",
        help="输出 JSON 文件路径",
    )
    
    args = parser.parse_args()
    
    # 覆盖 config 中的默认值
    if args.db:
        config.INGREDIENTS_DB_PATH = Path(args.db)
    if args.output:
        config.OUTPUT_JSON_PATH = Path(args.output)
    
    try:
        main_voice_pipeline(
            duration_sec=args.duration,
            input_device=args.input_device,
            sample_rate=args.sample_rate,
            disable_tts=args.disable_tts,
            text_input=args.text,
            continuous=args.continuous,
            wake_window_sec=args.wake_window,
            wake_command_window_sec=args.wake_command_window,
        )
    except KeyboardInterrupt:
        print("\n[INFO] Pipeline cancelled by user")
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        if config.ENABLE_DEBUG_LOG:
            import traceback
            traceback.print_exc()
        sys.exit(1)
