#!/usr/bin/env python3
"""reBotArm MIT 弹簧阻尼位置控制

用法:
    python example/3_mit_control.py

输入: n 个关节角度（度），空格分隔
示例:
    0 0 0 0 0 0
    10 -20 30 -40 50 60
    10 -20 30 -40 50 60 120 8   # 末尾可附加 kp kd 覆盖 yaml

MIT 模式: 力矩 = kp*(目标-当前) + kd*(0-当前速度)
"""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reBotArm_control_py.actuator import RobotArm

arm = RobotArm()
target_pos: np.ndarray
mit_kp: np.ndarray
mit_kd: np.ndarray


def mit_controller(ref: RobotArm, dt: float) -> None:
    ref.mit(target_pos, kp=mit_kp, kd=mit_kd)


arm.connect()
print("--- 连接成功 ---")
arm.enable()
print("--- 使能成功 ---")
arm.mode_mit()
print("--- MIT 模式 ---\n")

n = arm.num_joints
target_pos = np.zeros(n)
mit_kp = np.array([j.kp for j in arm._joints], dtype=np.float64)
mit_kd = np.array([j.kd for j in arm._joints], dtype=np.float64)

arm.start_control_loop(mit_controller)
print(f"关节数: {n} | 第1个关节电机 kp: {mit_kp[0]:.1f} | kd: {mit_kd[0]:.1f} | {arm._rate}Hz")
print("输入 n 个角度(度) q退出 state查看状态\n")

while True:
    try:
        line = input("> ").strip()
    except EOFError:
        break

    if not line:
        continue
    if line.lower() in ("q", "quit", "exit"):
        break

    if line.lower() == "state":
        pos = arm.get_positions()
        vel = arm.get_velocities()
        print(f"  pos: {[f'{x:+.2f}' for x in np.degrees(pos)]}")
        print(f"  vel: {[f'{x:+.2f}' for x in np.degrees(vel)]}")
        continue

    tokens = line.split()
    if len(tokens) < n:
        print(f"需要 {n} 个值")
        continue

    pos_deg = [float(x) for x in tokens[:n]]
    target_pos[:] = np.radians(pos_deg)

    if len(tokens) >= n + 1:
        mit_kp[:] = float(tokens[n])
    if len(tokens) >= n + 2:
        mit_kd[:] = float(tokens[n + 1])

    print(f"  -> {[f'{x:+.1f}' for x in pos_deg]}  kp={mit_kp[0]:.1f}  kd={mit_kd[0]:.1f}")

arm.disconnect()
