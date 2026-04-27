# Setup Guide

This guide turns the repository documentation into a concrete setup sequence.

## 1. Prepare a Python Environment

Use one of the following approaches:

- `uv` for `Control_Part/reBotArm_control_py`
- `conda` or a plain virtual environment for the vision and language stacks

Recommended base version:

- Python 3.10

## 2. Install the Robot Control Stack First

Path: [`Control_Part/reBotArm_control_py/`](./Control_Part/reBotArm_control_py)

Install:

```bash
cd Control_Part/reBotArm_control_py
uv sync
```

Sanity checks:

```bash
uv run python example/5_fk_test.py
uv run python example/6_ik_test.py
```

If you plan to run the vision grasp pipeline, keep this repository available locally because the grasp code imports it directly.

## 3. Install the Vision Grasping Stack

Path: [`Vision_Part/rebot_grasp/`](./Vision_Part/rebot_grasp)

Install the Python dependencies:

```bash
cd Vision_Part/rebot_grasp
pip install -r requirements.txt
```

Optional but usually required for Orbbec Gemini 2:

- clone and install `pyorbbecsdk`
- install the Orbbec udev rules

Recommended local SDK location:

```text
Control_Part/reBotArm_control_py/
Vision_Part/rebot_grasp/
```

If the control library is not found automatically, set `robot.repo_root` in `Vision_Part/rebot_grasp/config/default.yaml`.

Run a dry run before moving hardware:

```bash
python scripts/main.py --dry-run
```

## 4. Install the TabletopSeg3D Stack If Needed

Path: [`Vision_Part/TabletopSeg3D/3DDetection/`](./Vision_Part/TabletopSeg3D/3DDetection)

Install:

```bash
cd Vision_Part/TabletopSeg3D/3DDetection
pip install -r requirements.txt
```

Orbbec backend extras:

```bash
pip install -r requirements-orbbec.txt
```

Sanity check:

```bash
python scripts/realtime_open3d_scene.py --list-devices --camera-backend auto
```

## 5. Install the Language Stack If Needed

Path: [`Language_Part/`](./Language_Part)

Install:

```bash
cd Language_Part
pip install -r requirements.txt
```

Copy the template secrets file and fill in your own values:

- `secrets.local.example.json`
- `secrets.local.json`

Recommended first test:

```bash
python voice_pipeline.py --text "我想吃点清爽的"
```

If microphone mode fails, use `--text` first and add `--list-devices` to inspect your audio devices.

## 6. Prepare Evaluation Assets

The root evaluation scripts expect these checkpoints:

- `Datasets/NOODLE1/140000/pretrained_model`
- `Datasets/NOODLE2/080000/pretrained_model`
- `Datasets/NOODLE3/040000/pretrained_model`

Make sure the `lerobot` environment is available before running:

```bash
./run_eval_TASK1.sh
./run_eval_TASK2.sh
./run_eval_TASK3.sh
```

## 7. Set Device Permissions

Typical hardware permission commands:

```bash
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyUSB0
sudo chmod a+rw /dev/bus/usb/*/*
```

Adjust the device names to match your system.

## 8. Suggested Verification Order

1. Verify Python package installation for the control stack.
2. Verify the camera backend with a list-devices command.
3. Run the vision pipeline in dry-run mode.
4. Run the language pipeline with `--text`.
5. Only then enable actual robot motion.

## 9. Common Failure Points

- Missing `reBotArm_control_py` path
  - Fix by checking the local clone or setting `robot.repo_root`
- Missing `pyorbbecsdk`
  - Fix by installing the Orbbec Python wrapper
- Missing audio input
  - Fix by using `--list-devices` and testing `--text`
- Missing evaluation checkpoints
  - Fix by restoring the `Datasets/` contents

## 10. Where to Go Next

- [`README.md`](./README.md)
- [`PROJECT_GUIDE.md`](./PROJECT_GUIDE.md)
- [`DEPENDENCIES.md`](./DEPENDENCIES.md)
