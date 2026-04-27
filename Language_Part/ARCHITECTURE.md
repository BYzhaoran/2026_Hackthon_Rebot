# Fruit Recommendation Architecture

This folder implements a single pipeline:

1. Capture speech from the microphone or accept direct text input.
2. Transcribe it locally with `faster-whisper` when needed.
3. Ask the assistant to choose one fruit from the fixed six-item menu.
4. Speak the recommendation with a teasing line.
5. Write the chosen sequence number into a JSON file.

## Fruit Mapping

- `1` -> 草莓
- `2` -> 蓝莓
- `3` -> 香蕉
- `4` -> 杨桃
- `5` -> 圣女果
- `6` -> 猕猴桃

## Configuration

Environment variables in `config.py` control:

- Microphone capture settings
- Whisper model and language
- Fruit chat model
- `FRUIT_USE_LLM` toggles the AI recommendation path
- Feedback TTS engine
- JSON output path

## Entry point

Run:

```bash
python voice_pipeline.py
```

or for direct testing:

```bash
python voice_pipeline.py --text "我想吃点清爽的"
```

## Fallback behavior

- If `FRUIT_ALLOW_LOCAL_FALLBACK=true`, the pipeline falls back to a local keyword-based fruit selector.
- Otherwise it stops on the LLM error so you can fix the API key, base URL, model, or quota.
- If `faster-whisper` is unavailable, use `--text` instead of microphone mode.
