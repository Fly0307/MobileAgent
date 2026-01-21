#!/bin/bash

# ============================================================
# Docker-based GUI Owl Runner Script
# ============================================================
# This script runs the GUI Owl agent in Docker containers
# with configurable parameters for parallel execution.
# ============================================================

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log_docker_ma3_"$current_time".log"

# ============================================================
# Configuration Parameters
# ============================================================

# Agent Configuration
AGENT_NAME="gui_owl"
MODEL="GUI-Owl-32B"
API_KEY="dummy_api_key"
BASE_URL="http://123.60.91.241:9000/v1"

# Docker Configuration
# Comma-separated list of Docker URLs (e.g., "http://localhost:5000,http://localhost:5001")
DOCKER_URLS="http://localhost:5000"

# Task Configuration
# Comma-separated list of tasks to run (leave empty to run all tasks)
# Example: "AudioRecorderRecordAudio,CameraTakePhoto,SystemBrightnessMin"
TASKS=""

# Task seed configuration
# 1-42的任务种子
TASK_SEED=$(( (RANDOM % 42) + 1 ))
FIXED_TASK_SEED="False"  # Set to "True" to use fixed seed for reproducibility
N_TASK_COMBINATIONS=1    # Number of task combinations per task type

# Output Configuration
TRAJ_OUTPUT_PATH="traj_docker_"$current_time

# Task Enhancement Configuration
# Set to "True" to enable task enhancement with local experience retrieval
# Set to "False" to disable task enhancement and use original task descriptions
USE_TASK_ENHANCEMENT="False"

# Mock Model (for testing)
# Set to "True" to use mock model responses instead of actual LLM
MOCK_MODEL="False"

# ============================================================
# Display Configuration
# ============================================================

echo "======================================"
echo "Starting Docker-based GUI Owl Agent"
echo "======================================"
echo "Agent: $AGENT_NAME"
echo "Model: $MODEL"
echo "Docker URLs: $DOCKER_URLS"
echo "Tasks: ${TASKS:-All tasks}"
echo "Task Seed: $TASK_SEED"
echo "Fixed Task Seed: $FIXED_TASK_SEED"
echo "Task Combinations: $N_TASK_COMBINATIONS"
echo "Task Enhancement: $USE_TASK_ENHANCEMENT"
echo "Mock Model: $MOCK_MODEL"
echo "Log File: $LOG"
echo "Trajectory Output: $TRAJ_OUTPUT_PATH"
echo "======================================"
echo ""

# ============================================================
# Build Python Command
# ============================================================

CMD="python scripts/run_suite_on_docker.py"
CMD="$CMD --docker_urls=\"$DOCKER_URLS\""
CMD="$CMD --model=\"$MODEL\""
CMD="$CMD --api_key=\"$API_KEY\""
CMD="$CMD --base_url=\"$BASE_URL\""
CMD="$CMD --output_path=\"$TRAJ_OUTPUT_PATH\""
CMD="$CMD --n_task_combinations=$N_TASK_COMBINATIONS"
CMD="$CMD --use_task_enhancement=$USE_TASK_ENHANCEMENT"

# Add tasks if specified
if [ -n "$TASKS" ]; then
  CMD="$CMD --tasks=\"$TASKS\""
fi

# Add mock model flag if enabled
if [ "$MOCK_MODEL" = "True" ]; then
  CMD="$CMD --mock_model=True"
fi

# ============================================================
# Execute
# ============================================================

echo "Executing command:"
echo "$CMD"
echo ""

eval "$CMD" 2>&1 | tee "$LOG"

# ============================================================
# Summary
# ============================================================

echo ""
echo "======================================"
echo "Execution completed"
echo "======================================"
echo "Log saved to: $LOG"
echo "Trajectories saved to: $TRAJ_OUTPUT_PATH"
echo "======================================"
