# Fruit Recommendation

This folder now contains a fruit recommendation pipeline.

It turns a spoken request or direct text input into one recommended fruit, then:

- speaks the recommendation with a teasing line
- writes the chosen sequence number into a JSON file

## Fruit Menu

The fixed fruit mapping is:

- `1` - 草莓
- `2` - 蓝莓
- `3` - 香蕉
- `4` - 杨桃
- `5` - 圣女果
- `6` - 猕猴桃

## Files

- `config.py` - audio, STT, TTS, chat, and JSON output settings
- `audio_core.py` - microphone capture and playback helpers
- `speech_core.py` - optional text-to-speech feedback
- `fruit_recommendation_core.py` - fruit selection and JSON formatting
- `tts_core.py` - TTS backends
- `voice_pipeline.py` - speech-to-fruit entrypoint

## Usage

Direct text test:

```bash
python voice_pipeline.py --text "我想吃点清爽的"
python voice_pipeline.py --text "我要补充维C"
```

Microphone mode:

```bash
python voice_pipeline.py
```

List input devices:

```bash
python voice_pipeline.py --list-devices
```

## Output

The JSON file defaults to `fruit_recommendation.json` and contains at least:

- `recommended_seq`
- `recommended_name`
- `voice_text`
- `request_text`

## AI Behavior

- `FRUIT_USE_LLM=true` enables the DeepSeek/OpenAI-compatible recommendation path.
- By default, the pipeline now stays on the LLM path and does not silently fall back to local rules.
- Set `FRUIT_ALLOW_LOCAL_FALLBACK=true` only if you explicitly want keyword-based fallback.
- You can point the fruit recommender at a different OpenAI-compatible endpoint with `FRUIT_API_KEY`, `FRUIT_BASE_URL`, and `FRUIT_CHAT_MODEL`.
- `FRUIT_LLM_TIMEOUT_SEC` limits how long the AI call can block before falling back.

## Notes

- `--no-tts` disables spoken feedback.
- `--no-playback` keeps TTS generation silent.
- If `faster-whisper` is not installed, use `--text` instead of microphone mode.
