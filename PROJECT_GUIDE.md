# Project Guide

This file is the engineering-facing guide for the repository. It tells you which part does what, what to install first, and how the pieces connect.

## Modules

- `Control_Part/reBotArm_control_py/`
  - Robot arm control library
  - Kinematics, trajectory planning, gripper control, simulation examples
- `Vision_Part/rebot_grasp/`
  - Main grasping pipeline
  - Camera backend, YOLO detection, hand-eye calibration, grasp execution
- `Vision_Part/TabletopSeg3D/3DDetection/`
  - Independent tabletop 3D detection demo
  - Open3D visualization and RealSense / Orbbec camera backends
- `Language_Part/`
  - Voice or text input
  - Fruit recommendation, STT, TTS, JSON output
- `Datasets/`
  - Local policy checkpoints and evaluation assets for LeRobot scripts

## Recommended Setup Order

1. Install the robot arm control library first.
2. Install the vision stack next.
3. Install the language stack if you need voice interaction.
4. Prepare datasets and policy checkpoints for evaluation scripts.
5. Verify devices and permissions before any real hardware run.

The concrete step-by-step installer lives in [`SETUP.md`](./SETUP.md).

## System Requirements

- Ubuntu 22.04 or newer
- Python 3.10 for the robot arm stack and the main grasping stack
- Access to the robot arm serial or CAN interface
- Access to the Orbbec Gemini 2 camera
- Microphone and speaker/headset for the language stack
- `lerobot` environment for evaluation scripts

## Control Part

Path: [`Control_Part/reBotArm_control_py/`](./Control_Part/reBotArm_control_py)

Install:

```bash
cd Control_Part/reBotArm_control_py
uv sync
```

Important files:

- `pyproject.toml`
- `config/arm.yaml`
- `config/gripper.yaml`
- `example/`

Useful examples:

```bash
uv run python example/1_damiao_text.py
uv run python example/2_zero_and_read.py
uv run python example/5_fk_test.py
uv run python example/6_ik_test.py
uv run python example/7_arm_ik_control.py
uv run python example/8_arm_traj_control.py
```

## Vision Grasping Part

Path: [`Vision_Part/rebot_grasp/`](./Vision_Part/rebot_grasp)

Install:

```bash
cd Vision_Part/rebot_grasp
pip install -r requirements.txt
```

Main entry:

```bash
python scripts/main.py
python scripts/main.py --dry-run
```

Key configuration:

- `config/default.yaml`
- `config/calibration/orbbec_gemini2/hand_eye.npz`
- `config/calibration/realsense_d435i/`
- `config/calibration/realsense_d405/`

Dependency note:

- This module expects `reBotArm_control_py` to be available locally.
- If the SDK is not in the default lookup path, set `robot.repo_root` in `config/default.yaml`.
- Orbbec camera support requires `pyorbbecsdk`.

## TabletopSeg3D

Path: [`Vision_Part/TabletopSeg3D/3DDetection/`](./Vision_Part/TabletopSeg3D/3DDetection)

Install:

```bash
cd Vision_Part/TabletopSeg3D/3DDetection
pip install -r requirements.txt
```

Orbbec-specific extras:

```bash
pip install -r requirements-orbbec.txt
```

Main entry:

```bash
python scripts/realtime_open3d_scene.py --camera-backend auto
```

## Language Part

Path: [`Language_Part/`](./Language_Part)

Install:

```bash
cd Language_Part
pip install -r requirements.txt
```

Main entry:

```bash
python voice_pipeline.py --text "我想吃点清爽的"
python voice_pipeline.py --list-devices
python voice_pipeline.py
```

Important files:

- `config.py`
- `secrets.local.example.json`
- `voice_pipeline.py`
- `fruit_recommendation_core.py`

## Evaluation Scripts

The root scripts are:

- `run_eval_TASK1.sh`
- `run_eval_TASK2.sh`
- `run_eval_TASK3.sh`

They assume:

- `lerobot` is installed and activated
- The robot arm is reachable at `/dev/ttyACM0` or the correct serial port
- The camera is available to `lerobot-record`
- The corresponding policy checkpoints exist under `Datasets/`

## Device Permissions

Before running hardware, verify permissions:

```bash
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyUSB0
sudo chmod a+rw /dev/bus/usb/*/*
```

Adjust the device names for your actual hardware.

## Suggested Sanity Check Order

1. Import the robot control library.
2. Verify the camera backend.
3. Run a non-hardware vision dry-run.
4. Run `voice_pipeline.py --text`.
5. Only then enable robot motion.

## Notes

- Several subdirectories already contain their own README files. Use them for deeper module-specific details.
- This repository contains duplicated or archived copies under `Vision_Part/TableFrult/`; treat them as reference material unless you know you need that variant.
- Large model weights and dataset archives are stored in the repository. Check disk space before cloning or copying the project.
