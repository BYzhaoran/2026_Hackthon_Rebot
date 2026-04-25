#!/usr/bin/env python3
"""ArmEndPos 交互控制示例（IK 模式）。

用法:
    python example/7_arm_ik_control.py

输入:
    x y z [roll pitch yaw]   目标末端位置（米 / 弧度）
    q / quit / exit          退出
    state                    当前状态
    pos                      当前末端位置
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
            print(f"  目标关节 (rad): {[f'{v:+.3f}' for v in Arm_endpos_control._q_target]}")
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
            print("  格式: x y z [roll pitch yaw]")
            continue

        x, y, z = vals[0], vals[1], vals[2]
        roll = vals[3] if len(vals) >= 6 else 0.0
        pitch = vals[4] if len(vals) >= 6 else 0.0
        yaw = vals[5] if len(vals) >= 6 else 0.0

        ok = Arm_endpos_control.move_to_ik(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw)
        print(f"  -> ({x:+.3f}, {y:+.3f}, {z:+.3f})  "
              f"rpy=[{roll:+.2f} {pitch:+.2f} {yaw:+.2f}]  "
              f"{'ok' if ok else 'fail'}")

    Arm_endpos_control.end()
    print("\n完成。")


if __name__ == "__main__":
    main()
