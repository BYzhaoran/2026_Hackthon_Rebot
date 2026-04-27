#!/usr/bin/env bash
set -euo pipefail

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate lerobot

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ts="$(date +%Y%m%d_%H%M%S)"
suffix="$(tr -dc 'a-z0-9' </dev/urandom | head -c 6)"
repo_id="seeed/eval_TASK3_${ts}_${suffix}"

exec lerobot-record \
  --robot.type=seeed_b601_dm_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.can_adapter=damiao \
  --robot.cameras="{ up: {type: orbbec, width: 640, height: 880, fps: 30, focus_area:[200,1200]}}" \
  --robot.id=follower1 \
  --display_data=true \
  --dataset.repo_id="${repo_id}" \
  --dataset.single_task="Put lego brick into the transparent box" \
  --policy.path="${project_root}/Datasets/NOODLE3/040000/pretrained_model" \
  --dataset.episode_time_s=18000
