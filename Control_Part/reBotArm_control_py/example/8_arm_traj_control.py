#!/usr/bin/env python3
"""ArmEndPos 交互控制示例（轨迹规划模式）。

用法:
    python example/8_arm_traj_control.py

输入:
    x y z [roll pitch yaw] [duration]   目标末端位置（米 / 弧度 / 秒）
    q / quit / exit                     退出
    state                               当前状态
    pos                                 当前末端位置
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reBotArm_control_py.actuator import RobotArm
from reBotArm_control_py.controllers import ArmEndPos


def main() -> None:
    arm = RobotArm()
    Arm_endpos_control = ArmEndPos(arm)

    Arm_endpos_control.start()
    print("--- 已启动末端位置控制器 ---\n")

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
            q, _, _ = arm.get_state()
            print(f"  当前关节 (rad): {[f'{v:+.3f}' for v in q]}")
            print(f"  moving: {Arm_endpos_control._moving}  "
                  f"traj_pts: {len(Arm_endpos_control._traj)}  "
                  f"idx: {Arm_endpos_control._traj_idx}")
            continue

        if line.lower() == "end_state":
            q, _, _ = arm.get_state()
            from reBotArm_control_py.kinematics import joint_to_pose
            pos, rpy = joint_to_pose(q)
            px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
            rx, ry, rz = float(rpy[0]), float(rpy[1]), float(rpy[2])
            print(f"  pos=[{px:+.3f} {py:+.3f} {pz:+.3f}] m  rpy=[{rx:+.2f} {ry:+.2f} {rz:+.2f}] rad")
            continue

        try:
            vals = [float(v) for v in line.split()]
        except ValueError:
            print("  格式: x y z [roll pitch yaw] [duration]")
            continue

        x, y, z = vals[0], vals[1], vals[2]
        roll = vals[3] if len(vals) >= 6 else 0.0
        pitch = vals[4] if len(vals) >= 6 else 0.0
        yaw = vals[5] if len(vals) >= 6 else 0.0
        duration = vals[6] if len(vals) >= 7 else 2.0

        ok = Arm_endpos_control.move_to_traj(
            x=x, y=y, z=z,
            roll=roll, pitch=pitch, yaw=yaw,
            duration=duration,
        )
        print(f"  -> ({x:+.3f}, {y:+.3f}, {z:+.3f})  "
              f"T={duration:.1f}s  {'ok' if ok else 'fail'}")

    Arm_endpos_control.end()
    print("\n完成。")


if __name__ == "__main__":
    main()
