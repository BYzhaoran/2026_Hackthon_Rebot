# Language Part: Voice -> Ingredient IDs

This folder provides a minimal pipeline:
1. Record voice from microphone.
2. Transcribe speech to text locally (faster-whisper).
3. Build a numbered ingredient prompt from a JSON database.
4. Select matching ingredient IDs according to user request.
5. Generate AI TTS confirmation audio for selected results.
6. Write selection results + confirmation metadata to JSON file.

## Files
- `voice_select_ingredients.py`: main script
- `ingredients_db.json`: ingredient database (replace with your own data)
- `selected_ingredients.json`: output result file
- `secrets.local.example.json`: local secret file template
- `requirements.txt`: python dependencies

## Install
```bash
cd Language_Part
pip install -r requirements.txt
```

If you see "PortAudio library not found", install system dependency first:

Conda (recommended in your conda env):
```bash
conda install -n Hackthon_Rebot -c conda-forge portaudio python-sounddevice
```

Ubuntu apt + pip:
```bash
sudo apt update
sudo apt install -y portaudio19-dev
pip install sounddevice
```

## Environment Variables
- `DEEPSEEK_API_KEY` (required)
- `DEEPSEEK_BASE_URL` (optional, default: `https://api.deepseek.com`)
- `DEEPSEEK_CHAT_MODEL` (optional, default: `deepseek-chat`)
- `DEEPSEEK_DISABLE_PROXY` (optional, `true/1/yes/on` to ignore all proxy env)
- `TTS_ENABLED` (optional, default: `true`)
- `TTS_MODEL` (optional, default: `gpt-4o-mini-tts`)
- `TTS_VOICE` (optional, default: `alloy`)
- `TTS_API_KEY` (optional, for dedicated TTS provider)
- `TTS_BASE_URL` (optional, e.g. `https://api.openai.com/v1`)

If you see `Unknown scheme for proxy URL('socks://...')`:
- Use `socks5://127.0.0.1:7890` instead of `socks://127.0.0.1:7890`
- Or set `DEEPSEEK_DISABLE_PROXY=true` to bypass proxy for this script

Local STT setup:
```bash
pip install faster-whisper
```

Optional local STT config in `secrets.local.json`:
- `LOCAL_STT_MODEL`: `small` (or `tiny/base/medium/...`)
- `LOCAL_STT_LANGUAGE`: `zh` (set empty for auto detect)
- env `LOCAL_STT_COMPUTE_TYPE`: `int8` (default), `float16`, `float32`
- env `LOCAL_STT_HINT`: domain hint words to bias recognition (default includes ingredient names)
- env `LOCAL_STT_MIN_RMS`: minimum audio RMS threshold (default `0.001`), lower if mic is very quiet

If local STT returns empty text:
- Keep speaking duration >= 2 seconds and stay close to mic
- Set `LOCAL_STT_LANGUAGE` to empty string for auto language detect
- Use `--input-device` to choose the correct microphone
- The script already retries with `vad_filter` on/off automatically
- If `rms` is too low, script now auto-tries other input devices when `--input-device` is not set

## Local Secret File (Recommended)
Use local file `secrets.local.json` in this folder. It is ignored by git via root `.gitignore`.

Create it from template:
```bash
cp secrets.local.example.json secrets.local.json
```

Then fill `DEEPSEEK_API_KEY` in `secrets.local.json`.

Example:
```bash
export DEEPSEEK_API_KEY="your_api_key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

## Run
### A) Full voice flow
```bash
python voice_select_ingredients.py \
  --db ingredients_db.json \
  --output selected_ingredients.json \
  --duration 5 \
  --tts-output confirmation_reply.mp3
```

If recording fails with `Invalid sample rate [PaErrorCode -9997]`, the script now auto-retries common rates (16000/44100/48000/device default).
You can also inspect/select device manually:

```bash
python voice_select_ingredients.py --list-devices
python voice_select_ingredients.py --input-device 1 --sample-rate 44100
```

Default behavior includes playback after recording.
- Disable playback: add `--no-playback`
- Force playback: add `--playback`
- Disable TTS confirmation audio: add `--disable-tts`

### B) Text-only test (skip recording/transcription)
```bash
python voice_select_ingredients.py \
  --db ingredients_db.json \
  --output selected_ingredients.json \
  --text "I want to cook tomato egg noodle"
```

## Input database format
The script supports either:
- top-level list
- object with `ingredients` list

Each item must contain:
- `id` (integer)
- `name` (string)

Optional fields:
- `aliases` (string list)
- `category` (string)

## Output format
`selected_ingredients.json` example:
```json
{
  "timestamp_utc": "2026-04-25T12:00:00+00:00",
  "request_text": "I want to cook tomato egg noodle",
  "selected_ids": [1, 6, 9],
  "numbered_selection": [
    {"seq": 1, "id": 1, "name": "tomato", "category": "vegetable"},
    {"seq": 2, "id": 6, "name": "egg", "category": "protein"},
    {"seq": 3, "id": 9, "name": "noodle", "category": "staple"}
  ],
  "selected_items": [
    {"id": 1, "name": "tomato"},
    {"id": 6, "name": "egg"},
    {"id": 9, "name": "noodle"}
  ],
  "confirmation_text": "已为你确认食材：1号tomato，6号egg，9号noodle。请确认是否正确。",
  "confirmation_audio_path": "confirmation_reply.mp3"
}
```
