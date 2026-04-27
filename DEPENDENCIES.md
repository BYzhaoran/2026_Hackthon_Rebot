# Dependencies

This file groups the repository dependencies by module and gives the intended installation source for each one.

## Control_Part / reBotArm_control_py

Path: [`Control_Part/reBotArm_control_py/`](./Control_Part/reBotArm_control_py)

Declared in:

- `pyproject.toml`

Core dependencies:

- `meshcat>=0.3.2`
- `pin>=3.9.0`
- `numpy>=1.24.0`
- `pyyaml>=6.0`
- `matplotlib>=3.10.8`
- `motorbridge>=0.1.7`

Install command:

```bash
cd Control_Part/reBotArm_control_py
uv sync
```

## Vision_Part / rebot_grasp

Path: [`Vision_Part/rebot_grasp/`](./Vision_Part/rebot_grasp)

Declared in:

- `requirements.txt`

Core dependencies:

- `numpy<2.0.0`
- `scipy>=1.10`
- `opencv-python<4.10.0`
- `opencv-contrib-python<4.10.0`
- `ultralytics`
- `PyYAML>=6.0`
- `pyrealsense2>=2.54`
- `pin>=3.9.0`
- `meshcat>=0.3.2`
- `matplotlib>=3.10.0`
- `motorbridge>=0.1.7`

Install command:

```bash
cd Vision_Part/rebot_grasp
pip install -r requirements.txt
```

Extra requirement:

- `pyorbbecsdk` is not bundled and must be installed separately for Orbbec Gemini 2 support.

## Vision_Part / TabletopSeg3D

Path: [`Vision_Part/TabletopSeg3D/3DDetection`](./Vision_Part/TabletopSeg3D/3DDetection)

Declared in:

- `requirements.txt`
- `requirements-orbbec.txt`

Typical dependencies:

- `numpy`
- `opencv-python`
- `open3d`
- `ultralytics`
- `pyrealsense2`
- Orbbec SDK Python wrapper for the Orbbec backend

Install commands:

```bash
cd Vision_Part/TabletopSeg3D/3DDetection
pip install -r requirements.txt
pip install -r requirements-orbbec.txt
```

## Language_Part

Path: [`Language_Part/`](./Language_Part)

Declared in:

- `requirements.txt`

Core dependencies:

- `openai>=1.40.0`
- `sounddevice>=0.4.7`
- `scipy>=1.13.1`
- `numpy>=1.26.0`
- `faster-whisper>=1.0.3`
- `edge-tts>=6.1.0`
- `pyttsx3>=2.90`

Install command:

```bash
cd Language_Part
pip install -r requirements.txt
```

## Local secrets

Language module secrets template:

- `Language_Part/secrets.local.example.json`

Optional local override file:

- `Language_Part/secrets.local.json`

Recommended keys:

- `FRUIT_API_KEY`
- `FRUIT_BASE_URL`
- `FRUIT_CHAT_MODEL`
- `FRUIT_USE_LLM`
- `FRUIT_ALLOW_LOCAL_FALLBACK`
- `TTS_ENGINE`
- `EDGE_TTS_VOICE`
- `ENABLE_TTS`
- `ENABLE_PLAYBACK`

## Evaluation Assets

The evaluation shell scripts assume these local checkpoints exist:

- `Datasets/NOODLE1/140000/pretrained_model`
- `Datasets/NOODLE2/080000/pretrained_model`
- `Datasets/NOODLE3/040000/pretrained_model`

They are not Python requirements, but they are required for the evaluation workflow.

## Practical Install Order

1. Create or activate the Python environment.
2. Install `Control_Part/reBotArm_control_py`.
3. Install `Vision_Part/rebot_grasp`.
4. Install `Vision_Part/TabletopSeg3D/3DDetection` if needed.
5. Install `Language_Part` if you need voice features.
6. Install camera SDKs and udev rules.
7. Verify datasets and local model paths.
