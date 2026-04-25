#!/usr/bin/env python3
"""reBotArm POS_VEL 位置速度控制

用法:
    python example/4_pos_vel_control.py

输入: n 个关节角度（度），空格分隔
示例:
    0 0 0 0 0 0
    10 -20 30 -40 50 60
    10 -20 30 -40 50 60 5.0   # 末尾可附加 vlim 覆盖 yaml

POS_VEL 模式: PI 位置环 + PI 速度环
"""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reBotArm_control_py.actuator import RobotArm

arm = RobotArm()
target_pos: np.ndarray
pv_vlim: np.ndarray


def pos_vel_controller(ref: RobotArm, dt: float) -> None:
    ref.pos_vel(target_pos, vlim=pv_vlim)


arm.connect()
print("--- 连接成功 ---")
arm.enable()
print("--- 使能成功 ---")
arm.mode_pos_vel()
print("--- POS_VEL 模式 ---\n")

n = arm.num_joints
target_pos = np.zeros(n)
pv_vlim = np.array([j.vlim for j in arm._joints], dtype=np.float64)

arm.start_control_loop(pos_vel_controller)
print(f"关节数: {n} | vlim: {pv_vlim[0]:.2f} rad/s | {arm._rate}Hz")
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

    if len(tokens) > n:
        pv_vlim[:] = float(tokens[n])

    print(f"  -> {[f'{x:+.1f}' for x in pos_deg]}  vlim={pv_vlim[0]:.2f}")

arm.disconnect()
