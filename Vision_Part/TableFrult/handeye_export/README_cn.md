# reBot 手眼标定模块

这个目录只服务当前 TableFrult + reBot 项目，用于完成眼在手外手眼标定。

## 坐标约定

- 相机固定在桌面/外部环境中。
- ChArUco 标定板固定在 reBot 末端。
- 每个样本保存 `T_base_ee` 和 `T_camera_board`。
- 求解结果是 `T_base_camera`，用于把相机坐标系中的点变换到 reBot 基座坐标系。

```text
T_x_y 表示 p_x = T_x_y * p_y

T_ee_board = inv(T_base_ee) @ T_base_camera @ T_camera_board
```

## reBot 配置

默认机械臂模型集中在 `robot/rebot_model.py`：

- `REBOT_URDF_PATH`
- `REBOT_ROOT_LINK`
- `REBOT_EE_LINK`

采样脚本默认通过 `robot/runtime_bridge_client.py` 连接已运行的 reBot bridge，并读取：

```json
{
  "ok": true,
  "joint_state": {
    "joint_names": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"],
    "joint_positions": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  }
}
```

## 主要脚本

- `calibrate_by_handeye/start_handeye_session.py`：连续手动采样。
- `calibrate_by_handeye/collect_handeye_sample.py`：单条样本采集。
- `calibrate_by_handeye/solve_eye_to_hand.py`：离线求解 `T_base_camera`。
- `calibrate_by_handeye/validate_eye_to_hand.py`：验证外参是否自洽。
- `calibration/detect_charuco.py`：ChArUco 检测和板位姿估计。
- `calibration/robot_fk.py`：用 reBot URDF 和 joint positions 计算 `T_base_ee`。

## 环境

```bash
conda activate rebot_F
```

依赖见 `requirements.txt`，当前环境还需要安装 `reBotArm_control_py`。
