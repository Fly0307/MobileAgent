#!/bin/bash

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log_ma3_"$current_time".log"

MODEL_NAME="gui_owl"
MODEL=""
API_KEY="dummy_api_key"
BASE_URL="http://123.60.91.241:9000/v1"
TRAJ_OUTPUT_PATH="traj_"$current_time


# Task enhancement configuration
# Set to "true" to enable task enhancement with local experience retrieval (default)
# Set to "false" to disable task enhancement and use original task descriptions
USE_TASK_ENHANCEMENT="False"
# export TOKENIZERS_PARALLELISM=false
# CHECKPOINT_DIR="/home/zhaoxi/android_world/runs/"

# export GRPC_VERBOSITY=ERROR
# # export GRPC_TRACE=none
# export TF_CPP_MIN_LOG_LEVEL=3
# export PYTHONUNBUFFERED=1

python run_ma3.py \
  --suite_family=android_world \
  --agent_name=$MODEL_NAME \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --use_task_enhancement=$USE_TASK_ENHANCEMENT\
  --grpc_port=8554 \
  --console_port=5554 2>&1 | tee "$LOG"

echo ""
echo "日志已保存到: $LOG"
echo "轨迹已保存到: $TRAJ_OUTPUT_PATH"