#!/bin/bash

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log_ma3_"$current_time".log"

# AGENT_NAME="mobile_agent_v3"
AGENT_NAME="gui_owl"
MODEL=""
API_KEY="dummy_api_key"
BASE_URL="http://123.60.91.241:9003/v1"
TRAJ_OUTPUT_PATH="traj_"$current_time


# Task enhancement configuration
# Set to "true" to enable task enhancement with local experience retrieval (default)
# Set to "false" to disable task enhancement and use original task descriptions
USE_TASK_ENHANCEMENT="False"


# export TOKENIZERS_PARALLELISM=false
# CHECKPOINT_DIR="/home/zhaoxi/android_world/runs/run_20251116T160606037432"

# export GRPC_VERBOSITY=ERROR
# # export GRPC_TRACE=none
# export TF_CPP_MIN_LOG_LEVEL=3
# export PYTHONUNBUFFERED=1

echo "======================================"
echo "Starting Mobile Agent 3 with GUI-Owl"
echo "======================================"
echo "模型名称: $AGENT_NAME"
echo "使用任务增强: $USE_TASK_ENHANCEMENT"
echo "日志文件: $LOG"
echo "轨迹输出: $TRAJ_OUTPUT_PATH"
echo "======================================"
echo ""

python run_ma3.py \
  --suite_family=android_world \
  --agent_name=$AGENT_NAME \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --grpc_port=8554 \
  --console_port=5554 \
  --fixed_task_seed=False \
  --n_task_combinations=1 \
  --use_task_enhancement=$USE_TASK_ENHANCEMENT \
   2>&1 | tee "$LOG"
    # --checkpoint_dir=$CHECKPOINT_DIR \
    
    # --tasks=AudioRecorderRecordAudioWithFileName,CameraTakePhoto,RetroPlayingQueue,SaveCopyOfReceiptTaskEval,MarkorMergeNotes,MarkorChangeNoteContent,MarkorTranscribeVideo,OsmAndTrack,RecipeAddMultipleRecipesFromMarkor2,BrowserDraw,BrowserMultiply,ExpenseAddMultiple,ExpenseAddMultipleFromGallery,ExpenseAddMultipleFromMarkor,ExpenseDeleteDuplicates2,MarkorAddNoteHeader,MarkorDeleteNewestNote,MarkorMoveNote,MarkorTranscribeReceipt,OsmAndMarker,RecipeAddMultipleRecipes,RecipeAddMultipleRecipesFromImage,RecipeAddMultipleRecipesFromMarkor,RecipeDeleteDuplicateRecipes2,RecipeDeleteDuplicateRecipes3,RetroPlaylistDuration,SimpleDrawProCreateDrawing,SportsTrackerActivitiesOnDate,SportsTrackerLongestDistanceActivity,SportsTrackerTotalDistanceForCategoryOverInterval,SystemBrightnessMax,SystemBrightnessMin,SystemCopyToClipboard,TasksCompletedTasksForDate,TasksDueNextWeek,TasksHighPriorityTasksDueOnDate,VlcCreatePlaylist,VlcCreateTwoPlaylists  \
  # --tasks=AudioRecorderRecordAudioWithFileName,CameraTakePhoto,RetroPlayingQueue,SaveCopyOfReceiptTaskEval,MarkorMergeNotes,MarkorChangeNoteContent,OsmAndTrack,BrowserDraw,BrowserMultiply,ExpenseAddMultiple,ExpenseAddMultipleFromGallery,ExpenseAddMultipleFromMarkor,ExpenseDeleteDuplicates2,MarkorAddNoteHeader,MarkorDeleteNewestNote,MarkorMoveNote,MarkorTranscribeReceipt,RecipeAddMultipleRecipes,RecipeAddMultipleRecipesFromImage,RecipeAddMultipleRecipesFromMarkor,RecipeDeleteDuplicateRecipes2,RecipeDeleteDuplicateRecipes3,RetroPlaylistDuration,SimpleDrawProCreateDrawing,SportsTrackerActivitiesOnDate,SportsTrackerLongestDistanceActivity,SportsTrackerTotalDistanceForCategoryOverInterval,SystemBrightnessMax,SystemBrightnessMin,SystemCopyToClipboard,TasksCompletedTasksForDate,TasksDueNextWeek,TasksHighPriorityTasksDueOnDate,VlcCreatePlaylist,VlcCreateTwoPlaylists  \
  # --tasks=AudioRecorderRecordAudioWithFileName,CameraTakePhoto,RetroPlayingQueue,SaveCopyOfReceiptTaskEval,MarkorMergeNotes,MarkorChangeNoteContent,MarkorTranscribeVideo,OsmAndTrack,RecipeAddMultipleRecipesFromMarkor2,BrowserDraw,BrowserMultiply,ExpenseAddMultiple,ExpenseAddMultipleFromGallery,ExpenseAddMultipleFromMarkor,ExpenseDeleteDuplicates2,MarkorAddNoteHeader,MarkorDeleteNewestNote,MarkorMoveNote,MarkorTranscribeReceipt,OsmAndMarker,RecipeAddMultipleRecipes,RecipeAddMultipleRecipesFromImage,RecipeAddMultipleRecipesFromMarkor,RecipeDeleteDuplicateRecipes2,RecipeDeleteDuplicateRecipes3,RetroPlaylistDuration,SimpleDrawProCreateDrawing,SportsTrackerActivitiesOnDate,SportsTrackerLongestDistanceActivity,SportsTrackerTotalDistanceForCategoryOverInterval,SystemBrightnessMax,SystemBrightnessMin,SystemCopyToClipboard,TasksCompletedTasksForDate,TasksDueNextWeek,TasksHighPriorityTasksDueOnDate,VlcCreatePlaylist,VlcCreateTwoPlaylists  \

echo ""
echo "日志已保存到: $LOG"
echo "轨迹已保存到: $TRAJ_OUTPUT_PATH"
