# reBot Hackathon Rebot

这是一个围绕 `reBot Arm B601-DM` 机械臂搭建的多模块工程，按功能分成四块：

- `Control_Part/`：机械臂控制库与运动学/轨迹/夹爪控制
- `Vision_Part/`：视觉抓取、三维检测、标定与相关实验代码
- `Language_Part/`：语音输入、意图识别、果蔬推荐与 TTS 输出
- `Datasets/`：本地评测与策略权重数据

仓库里已经有各子模块的英文/中文说明，这份根 README 的目标是把整个工程串起来，让新接手的人知道“每一块是什么、入口在哪、先装什么、怎么跑”。

## 总览

这个项目不是单一应用，而是一组彼此关联的机器人能力：

1. `Control_Part/reBotArm_control_py` 提供机械臂底层控制、正逆运动学、轨迹规划和夹爪控制。
2. `Vision_Part/rebot_grasp` 负责相机采集、YOLO 检测、手眼标定和自主抓取。
3. `Vision_Part/TabletopSeg3D/3DDetection` 是独立的桌面三维分割/检测示例，支持 RealSense 和 Orbbec 后端。
4. `Language_Part` 将语音或文本请求转成果蔬推荐，并把结果写入 JSON。
5. 根目录下的 `run_eval_TASK1.sh`、`run_eval_TASK2.sh`、`run_eval_TASK3.sh` 用于 LeRobot 评测任务的录制和推理对接。

## 推荐阅读顺序

如果你是第一次看这个仓库，建议按下面顺序：

1. 先看本文件，理解整体结构。
2. 再看 `Control_Part/reBotArm_control_py/README.md`，确认机械臂控制环境。
3. 再看 `Vision_Part/rebot_grasp/README_zh.md`，这是视觉抓取主项目。
4. 如需语音功能，再看 `Language_Part/README.md` 和 `Language_Part/ARCHITECTURE.md`。
5. 如需桌面 3D 检测，再看 `Vision_Part/TabletopSeg3D/README.md` 和 `Vision_Part/TabletopSeg3D/3DDetection/README.md`。

## 环境要求

- 操作系统：Ubuntu 22.04+ 更稳妥
- Python：3.10 为主
- 机械臂：reBot Arm B601-DM
- 机械臂通信：USB2CAN 串口桥或等效 CAN 适配器
- 深度相机：Orbbec Gemini 2
- 语音模块：麦克风、扬声器或耳机
- 评测模块：`lerobot` 环境、对应策略权重、数据集包

## 目录结构

```text
.
├── Control_Part/
│   └── reBotArm_control_py/        # 机械臂控制库
├── Vision_Part/
│   ├── rebot_grasp/                # 视觉抓取主流程
│   ├── TabletopSeg3D/              # 桌面 3D 检测
│   └── TableFrult/                 # 与果蔬/评测相关的打包副本与资料
├── Language_Part/                  # 语音识别 + 果蔬推荐
├── Datasets/                       # 本地策略权重与评测资源
├── run_eval_TASK1.sh               # LeRobot 任务 1 评测脚本
├── run_eval_TASK2.sh               # LeRobot 任务 2 评测脚本
├── run_eval_TASK3.sh               # LeRobot 任务 3 评测脚本
└── command.txt                     # 你当前环境里的命令备注
```

## 控制模块

路径：[`Control_Part/reBotArm_control_py/`](./Control_Part/reBotArm_control_py)

这是机械臂控制的基础库，主要提供：

- 电机连接、使能、失能
- 正/逆运动学
- 轨迹规划
- 实机控制示例
- 仿真示例
- 夹爪控制

常用安装方式：

```bash
cd Control_Part/reBotArm_control_py
uv sync
```

常见示例入口：

```bash
uv run python example/1_damiao_text.py
uv run python example/2_zero_and_read.py
uv run python example/5_fk_test.py
uv run python example/6_ik_test.py
uv run python example/7_arm_ik_control.py
uv run python example/8_arm_traj_control.py
```

如果你的项目需要直接引用该库，优先参考该目录下的 README 和 `config/arm.yaml`、`config/gripper.yaml`。

## 视觉抓取主流程

路径：[`Vision_Part/rebot_grasp/`](./Vision_Part/rebot_grasp)

这是整个仓库里最接近“端到端抓取”的部分，流程如下：

1. 相机采集 RGB + Depth
2. YOLO 检测桌面目标
3. 计算目标抓取姿态
4. 使用手眼标定把相机坐标转换到机械臂基座坐标
5. 控制机械臂执行预抓取、下探、夹取和回位

主入口：

```bash
cd Vision_Part/rebot_grasp
python scripts/main.py
```

常用辅助入口：

```bash
python scripts/main.py --dry-run
python scripts/object_detection.py
python scripts/ordinary_grasp_pipeline.py
python scripts/collect_handeye_eih.py
```

关键配置文件：

- `config/default.yaml`：相机、YOLO、机械臂、抓取参数
- `config/calibration/orbbec_gemini2/hand_eye.npz`：Orbbec 方案的手眼标定结果
- `config/calibration/realsense_d435i/` 和 `config/calibration/realsense_d405/`：RealSense 方案配置

安装依赖：

```bash
cd Vision_Part/rebot_grasp
pip install -r requirements.txt
```

注意：

- 该模块会尝试从配置里找到 `Control_Part/reBotArm_control_py`
- 如果机械臂 SDK 不在默认位置，需要在 `config/default.yaml` 里设置 `robot.repo_root`
- Orbbec 方案需要额外安装 `pyorbbecsdk`

## 桌面 3D 检测

路径：[`Vision_Part/TabletopSeg3D/`](./Vision_Part/TabletopSeg3D)

这是一个独立的桌面物体三维检测工程，核心能力包括：

- YOLO 实例分割
- Open3D 场景可视化
- 终端固定顺序目标表
- RealSense 和 Orbbec 双后端

主入口：

```bash
cd Vision_Part/TabletopSeg3D/3DDetection
python scripts/realtime_open3d_scene.py --camera-backend auto
```

Orbbec 依赖：

```bash
pip install -r requirements-orbbec.txt
```

如果你只想做三维桌面检测，这是更轻量的入口；如果你要做完整抓取，请回到 `Vision_Part/rebot_grasp`。

## 语音与果蔬推荐

路径：[`Language_Part/`](./Language_Part)

这是一个独立的语音流程，输入可以是麦克风语音或直接文本，输出是一条果蔬推荐，并把结果写入 JSON。

主入口：

```bash
cd Language_Part
python voice_pipeline.py --text "我想吃点清爽的"
python voice_pipeline.py
python voice_pipeline.py --list-devices
```

主要文件：

- `voice_pipeline.py`：命令行入口
- `fruit_recommendation_core.py`：果蔬推荐逻辑
- `speech_core.py`：语音播报
- `audio_core.py`：录音与播放
- `tts_core.py`：TTS 后端
- `config.py`：环境变量和本地密钥加载

输出文件：

- `fruit_recommendation.json`
- 临时音频：`voice_command.wav`
- 播报音频：`command_reply.mp3`

配置方式：

- 通过环境变量控制 STT、LLM、TTS
- 也可以在 `secrets.local.json` 里写本地覆盖值

如果没有安装 `faster-whisper`，优先用 `--text` 做测试，不要直接进麦克风模式。

## 评测脚本

根目录下有三个评测脚本：

```bash
./run_eval_TASK1.sh
./run_eval_TASK2.sh
./run_eval_TASK3.sh
```

它们的共同假设是：

- 已经安装并激活 `lerobot` 环境
- 机械臂通过 `/dev/ttyACM0` 可访问
- Orbbec 相机已经可以被 `lerobot-record` 识别
- 对应策略权重位于：
  - `Datasets/NOODLE1/140000/pretrained_model`
  - `Datasets/NOODLE2/080000/pretrained_model`
  - `Datasets/NOODLE3/040000/pretrained_model`

脚本本身会：

- 生成唯一的 `dataset.repo_id`
- 调用 `lerobot-record`
- 指定机械臂、相机和策略路径
- 记录一次长时任务评测

## 设备权限

如果你要跑实机流程，通常要先处理设备权限：

```bash
sudo chmod 666 /dev/ttyUSB0
sudo chmod 666 /dev/ttyACM0
sudo chmod a+rw /dev/bus/usb/*/*
```

实际端口号可能不同，先用 `ls /dev/tty*` 和 `dmesg` 确认再改。

## 常见问题

### 1. 找不到机械臂 SDK

现象：

- 视觉抓取报错找不到 `reBotArm_control_py`
- 或者 `robot.repo_root` 不存在

处理：

- 确认 `Control_Part/reBotArm_control_py` 是否可用
- 或在 `Vision_Part/rebot_grasp/config/default.yaml` 里填入正确的 `robot.repo_root`

### 2. Orbbec 相机打不开

现象：

- 设备无权限
- `pyorbbecsdk` 导入失败
- 画面黑屏或无深度数据

处理：

- 先装 `pyorbbecsdk`
- 再安装 udev 规则
- 再确认 USB 线和供电

### 3. 语音模块没有麦克风输入

现象：

- `sounddevice` 找不到输入设备
- `faster-whisper` 缺失

处理：

- 先运行 `python voice_pipeline.py --list-devices`
- 若只是功能联调，先用 `--text`

### 4. 评测脚本跑不起来

现象：

- `lerobot-record` 不存在
- `Datasets/.../pretrained_model` 路径缺失
- 端口 `/dev/ttyACM0` 不对

处理：

- 先激活 `lerobot` 环境
- 再确认权重目录
- 再确认机械臂串口名

## 现有文档入口

下面这些文档已经存在，适合按模块深入阅读：

- [`SETUP.md`](./SETUP.md)
- [`PROJECT_GUIDE.md`](./PROJECT_GUIDE.md)
- [`DEPENDENCIES.md`](./DEPENDENCIES.md)
- [`Control_Part/reBotArm_control_py/README.md`](./Control_Part/reBotArm_control_py/README.md)
- [`Control_Part/reBotArm_control_py/README_zh.md`](./Control_Part/reBotArm_control_py/README_zh.md)
- [`Vision_Part/rebot_grasp/README.md`](./Vision_Part/rebot_grasp/README.md)
- [`Vision_Part/rebot_grasp/README_zh.md`](./Vision_Part/rebot_grasp/README_zh.md)
- [`Vision_Part/TabletopSeg3D/README.md`](./Vision_Part/TabletopSeg3D/README.md)
- [`Vision_Part/TabletopSeg3D/3DDetection/README.md`](./Vision_Part/TabletopSeg3D/3DDetection/README.md)
- [`Language_Part/README.md`](./Language_Part/README.md)
- [`Language_Part/ARCHITECTURE.md`](./Language_Part/ARCHITECTURE.md)

## 备注

- `Vision_Part/TableFrult/` 里有和机械臂相关的打包副本与说明，适合看特定分支/任务的历史资料。
- 仓库里有一些大模型和数据压缩包，克隆后要注意磁盘空间。
- 当前 README 侧重“如何上手和如何跑”，更细的调参仍然建议回到各子模块目录里的文档和配置文件。
