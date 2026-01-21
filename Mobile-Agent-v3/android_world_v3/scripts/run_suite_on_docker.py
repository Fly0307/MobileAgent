# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Client for interacting with Android environment servers over HTTP.

Supports parallel execution across multiple Docker containers.
"""

import json
import logging
import time
import queue
import threading
from typing import Any, Optional
import os
import sys

# Add parent directory to path to ensure local modules are imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from absl import app
from absl import flags
import numpy as np
import pydantic
import requests

from android_world.env import json_action
from android_world.agents import gui_owl_docker
from android_world.agents import infer_ma3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

Params = dict[str, int | str]

FLAGS = flags.FLAGS

flags.DEFINE_list(
    'docker_urls',
    ['http://localhost:5000'],
    'List of Docker container URLs to use for execution.'
)
flags.DEFINE_string('model', 'gui_owl', 'Model name to use.')
flags.DEFINE_string('api_key', 'dummy_api_key', 'API key for the model.')
flags.DEFINE_string(
    'base_url',
    'http://123.60.91.241:9003/v1',
    'Base URL for the model API.'
)
flags.DEFINE_list(
    'tasks',
    None,
    'List of specific tasks to run. If None, run all available tasks.'
)
flags.DEFINE_integer(
    'n_task_combinations', 1, 'Number of combinations per task.'
)
flags.DEFINE_string(
    'output_path', 'traj_docker_output', 'Path to save trajectories.'
)
flags.DEFINE_boolean('mock_model', False, 'Use a mock model for testing.')
flags.DEFINE_boolean(
    'use_task_enhancement',
    False,
    'Whether to enable task enhancement with local experience retrieval.'
)


class Response(pydantic.BaseModel):
  status: str
  message: str


class AndroidEnvClient:
  """Client for interacting with the Android environment server."""

  def __init__(self, base_url: str):
    self.base_url = base_url
    logger.info(f"Initialized client for {self.base_url}")

  def reset(self, go_home: bool) -> Response:
    """Resets the environment."""
    response = requests.post(
        f"{self.base_url}/reset", params={"go_home": go_home}
    )
    response.raise_for_status()
    return Response(**response.json())

  def get_screenshot(
      self, wait_to_stabilize: bool = False
  ) -> np.ndarray[Any, Any]:
    """Gets the current screenshot of the environment."""
    response = requests.get(
        f"{self.base_url}/screenshot",
        params={"wait_to_stabilize": wait_to_stabilize},
    )
    response.raise_for_status()
    image = response.json()
    return np.array(image["pixels"], dtype=np.uint8)

  def execute_action(
      self,
      action: json_action.JSONAction,
  ) -> Response:
    """Executes an action in the environment."""
    print(f"Executing action on {self.base_url}: {action.json_str()}")
    response = requests.post(
        f"{self.base_url}/execute_action", json=json.loads(action.json_str())
    )
    response.raise_for_status()
    return Response(**response.json())

  def get_suite_task_list(self, max_index: int) -> list[str]:
    """Gets the list of tasks in the suite."""
    response = requests.get(
        f"{self.base_url}/suite/task_list", params={"max_index": max_index}
    )
    response.raise_for_status()
    return response.json()["task_list"]

  def get_suite_task_length(self, task_type: str) -> int:
    """Gets the length of the suite of tasks."""
    response = requests.get(
        f"{self.base_url}/suite/task_length", params={"task_type": task_type}
    )
    response.raise_for_status()
    return response.json()["length"]

  def reinitialize_suite(
      self,
      n_task_combinations: int = 1,
      seed: int = 42,
      task_family: str = "android_world",
  ) -> Response:
    """Reinitializes the suite of tasks."""
    response = requests.get(
        f"{self.base_url}/suite/reinitialize",
        params={
            "n_task_combinations": n_task_combinations,
            "seed": seed,
            "task_family": task_family,
        },
    )
    response.raise_for_status()
    return Response(**response.json())

  def initialize_task(self, task_type: str, task_idx: int) -> Response:
    """Initializes the task in the environment."""
    params: Params = {"task_type": task_type, "task_idx": task_idx}
    response = requests.post(f"{self.base_url}/task/initialize", params=params)
    response.raise_for_status()
    return Response(**response.json())

  def tear_down_task(self, task_type: str, task_idx: int) -> Response:
    """Tears down the task in the environment."""
    params: Params = {"task_type": task_type, "task_idx": task_idx}
    response = requests.post(f"{self.base_url}/task/tear_down", params=params)
    response.raise_for_status()
    return Response(**response.json())

  def get_task_score(self, task_type: str, task_idx: int) -> float:
    """Gets the score of the current task."""
    params: Params = {"task_type": task_type, "task_idx": task_idx}
    response = requests.get(f"{self.base_url}/task/score", params=params)
    response.raise_for_status()
    return response.json()["score"]

  def get_task_goal(self, task_type: str, task_idx: int) -> str:
    """Gets the goal of the current task."""
    params: Params = {"task_type": task_type, "task_idx": task_idx}
    response = requests.get(f"{self.base_url}/task/goal", params=params)
    response.raise_for_status()
    return response.json()["goal"]

  def get_task_template(self, task_type: str, task_idx: int) -> str:
    """Gets the template of the current task."""
    params: Params = {"task_type": task_type, "task_idx": task_idx}
    response = requests.get(f"{self.base_url}/task/template", params=params)
    response.raise_for_status()
    return response.json()["template"]

  def close(self) -> None:
    """Closes the environment."""
    try:
        response = requests.post(f"{self.base_url}/close")
        response.raise_for_status()
    except Exception as e:
        logger.warning(f"Error closing environment: {e}")

  def health(self) -> bool:
    """Checks the health of the environment."""
    try:
      response = requests.get(f"{self.base_url}/health")
      response.raise_for_status()
    except Exception as e:
      print(f"Environment {self.base_url} is not healthy: {e}")
      return False
    return True


class MockLLMWrapper:
    """Mock LLM wrapper for testing."""
    def __init__(self, *args, **kwargs):
        pass

    def predict_mm(self, text_prompt, images, messages=None):
        print("[MOCK LLM] Generating random action...")
        # Simulate a simple action (e.g. status complete or click)
        # For meaningful testing, we might want to alternate actions
        # But for framework test, a single action or finish is enough
        # Returning a formatted thought/action string often expected by the agent
        # GUI Owl parsing logic:
        # thought in <think> or <thinking>, action in {"name": "mobile_use"...}
        
        response_template = """<thinking>
I will complete the task.
</thinking>
<conclusion>
Task done.
</conclusion>
```json
{"name": "mobile_use", "arguments": {"action": "status", "goal_status": "complete"}}
```
"""
        return response_template, messages, None


def run_worker(
    worker_id: int,
    docker_url: str,
    task_queue: queue.Queue,
    result_list: list,
    lock: threading.Lock
):
    """Worker function to process tasks on a specific Docker container."""
    print(f"Worker {worker_id} starting on {docker_url}")


def print_progress_statistics(result_list):
    """Print cumulative task statistics after each task completion."""
    if not result_list:
        return
    
    print("\n" + "="*80)
    print("PROGRESS STATISTICS")
    print("="*80)
    
    # Group results by task_type
    task_stats = {}
    for idx, result in enumerate(result_list):
        task_type = result["task_type"]
        if task_type not in task_stats:
            task_stats[task_type] = {
                "task_num": idx,
                "num_trials": 0,
                "num_success": 0,
                "total_steps": 0,
                "scores": []
            }
        
        task_stats[task_type]["num_trials"] += 1
        if result["success"]:
            task_stats[task_type]["num_success"] += 1
        task_stats[task_type]["total_steps"] += result.get("steps", 0)
        task_stats[task_type]["scores"].append(result.get("score", 0.0))
    
    # Print table header
    print(f"\n{'Task':<40} {'Trials':<8} {'Success':<10} {'Avg Steps':<12} {'Avg Score':<10}")
    print("-" * 80)
    
    # Print each task
    total_trials = 0
    total_success = 0
    total_steps = 0
    total_score = 0.0
    
    for task_type in sorted(task_stats.keys()):
        stats = task_stats[task_type]
        num_trials = stats["num_trials"]
        success_rate = stats["num_success"] / num_trials if num_trials > 0 else 0.0
        avg_steps = stats["total_steps"] / num_trials if num_trials > 0 else 0.0
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0.0
        
        status_icon = "✅" if success_rate >= 0.5 else "❌"
        print(f"{task_type:<40} {num_trials:<8} {success_rate:>6.1%} {status_icon:<3} {avg_steps:>8.1f}    {avg_score:>8.2f}")
        
        total_trials += num_trials
        total_success += stats["num_success"]
        total_steps += stats["total_steps"]
        total_score += sum(stats["scores"])
    
    # Print average
    print("-" * 80)
    overall_success_rate = total_success / total_trials if total_trials > 0 else 0.0
    overall_avg_steps = total_steps / total_trials if total_trials > 0 else 0.0
    overall_avg_score = total_score / total_trials if total_trials > 0 else 0.0
    
    print(f"{'OVERALL AVERAGE':<40} {total_trials:<8} {overall_success_rate:>6.1%}     {overall_avg_steps:>8.1f}    {overall_avg_score:>8.2f}")
    print("="*80 + "\n")
    

def run_worker(
    worker_id: int,
    docker_url: str,
    task_queue: queue.Queue,
    result_list: list,
    lock: threading.Lock
):
    """Worker function to process tasks on a specific Docker container."""
    print(f"Worker {worker_id} starting on {docker_url}")
    
    try:
        client = AndroidEnvClient(base_url=docker_url)
        
        # Wait for health
        retry_count = 0
        while not client.health():
            if retry_count > 5:
                print(f"Worker {worker_id}: Cannot connect to {docker_url}, exiting.")
                return
            print(f"Worker {worker_id}: Waiting for {docker_url}...")
            time.sleep(2)
            retry_count += 1

        # Initialize Model Wrapper
        if FLAGS.mock_model:
            llm_wrapper = MockLLMWrapper()
            print(f"Worker {worker_id}: Using Mock LLM.")
        else:
            llm_wrapper = infer_ma3.GUIOwlWrapper(
                api_key=FLAGS.api_key,
                base_url=FLAGS.base_url,
                model_name=FLAGS.model
            )

        # Initialize Agent
        agent = gui_owl_docker.GUIOwlDocker(
            client=client,
            vllm=llm_wrapper,
            src_format="abs_resized", # Default format
            api_key=FLAGS.api_key, # Redundant but kept for init
            url=FLAGS.base_url,    # Redundant but kept for init
            name=FLAGS.model,
            output_path=FLAGS.output_path,
            use_task_enhancement=FLAGS.use_task_enhancement
        )

        while True:
            try:
                # Get task from queue
                # task_item is (task_type, task_idx)
                task_item = task_queue.get(block=False)
            except queue.Empty:
                break

            task_type, task_idx = task_item
            print(f"Worker {worker_id}: Processing {task_type} [{task_idx}]")

            try:
                # 1. Initialize Task on Server
                client.initialize_task(task_type=task_type, task_idx=task_idx)
                
                # 2. Get Goal
                goal = client.get_task_goal(task_type=task_type, task_idx=task_idx)
                print(f"Worker {worker_id}: Goal: {goal}")

                # 3. Reset Agent & Environment
                # Reset with go_home=True to ensure clean state
                agent.reset(go_home=True)
                agent.start_task(task_type)
                
                # 4. Agent Loop
                max_steps = 35 # Safety limit
                step = 0
                success = False
                
                while step < max_steps:
                    result = agent.step(goal)
                    if result.done:
                        break
                    step += 1
                
                # 5. Get Score
                score = client.get_task_score(task_type=task_type, task_idx=task_idx)
                print(f"Worker {worker_id}: Task finished. Score: {score}")
                success = score == 1.0

                # 6. Save task result to trajectory directory
                try:
                    # Get the trajectory directory path from agent's output_path
                    if hasattr(agent, 'output_path') and agent.output_path:
                        # Construct task directory path (same logic as in gui_owl.py)
                        # if goal not in agent.task_name:
                        #     task_dir_name = goal.replace(" ", "_")[:50]
                        # else:
                        #     task_dir_name = agent.task_name[goal]
                        
                        # task_output_dir = os.path.join(agent.output_path, task_dir_name)
                        # if hasattr(agent, 'task_index'):
                        #     task_output_dir = os.path.join(agent.output_path, task_dir_name, f"{agent.task_index}")
                        # if hasattr(agent, 'task_index'):
                        #     task_output_dir = os.path.join(agent.output_path, task_type, f"{agent.task_index}")
                        # else:
                        #     task_output_dir = os.path.join(agent.output_path, task_type)
                        # task_output_dir = os.path.join(self.output_path, task_name, f"task_{self.task_index}")
                        task_output_dir = agent._get_task_output_dir(goal)
                        print(f"Worker {worker_id}: Task output directory: {task_output_dir}")
                        
                        # Create directory if it doesn't exist
                        os.makedirs(task_output_dir, exist_ok=True)
                        
                        result_file = os.path.join(task_output_dir, "task_result.json")
                        task_result = {
                            "task_type": task_type,
                            "task_idx": task_idx,
                            "goal": goal,
                            "score": score,
                            "success": success,
                            "steps": step,
                            "max_steps": max_steps,
                            "worker_id": worker_id
                        }
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(task_result, f, ensure_ascii=False, indent=2)
                        print(f"Worker {worker_id}: Task result saved to {result_file}")
                    else:
                        print(f"Worker {worker_id}: Cannot save task result - agent has no output_path")
                except Exception as e:
                    print(f"Worker {worker_id}: Failed to save task result: {e}")
                    import traceback
                    traceback.print_exc()

                # 7. Tear Down
                client.tear_down_task(task_type=task_type, task_idx=task_idx)

                # Record Result
                with lock:
                    result_list.append({
                        "task_type": task_type,
                        "task_idx": task_idx,
                        "goal": goal,
                        "success": success,
                        "score": score,
                        "steps": step,
                        "worker": worker_id
                    })
                    
                    # Print progress statistics after each task
                    print_progress_statistics(result_list)

            except Exception as e:
                print(f"Worker {worker_id}: Error on task {task_type} [{task_idx}]: {e}")
                import traceback
                traceback.print_exc()
                # Try to clean up if possible
                try:
                    client.tear_down_task(task_type=task_type, task_idx=task_idx)
                except:
                    pass
                
                # Record failed task
                with lock:
                    result_list.append({
                        "task_type": task_type,
                        "task_idx": task_idx,
                        "goal": "Unknown",
                        "success": False,
                        "score": 0.0,
                        "steps": 0,
                        "worker": worker_id,
                        "error": str(e)
                    })
            finally:
                task_queue.task_done()
                # Clean reset between tasks
                try:
                    client.reset(go_home=True)
                except:
                    pass

    except Exception as e:
        print(f"Worker {worker_id}: Critical failure: {e}")
    finally:
        print(f"Worker {worker_id}: Finished.")


def main(argv):
    del argv
    
    docker_urls = FLAGS.docker_urls
    if not docker_urls:
        print("No docker URLs provided.")
        return

    # Use the first client to query the suite structure
    print(f"Querying suite structure from {docker_urls[0]}...")
    try:
        main_client = AndroidEnvClient(docker_urls[0])
        if not main_client.health():
             print(f"Main client {docker_urls[0]} is unhealthy. Please check env.")
             return
        
        # Reinitialize suite if needed configuration (optional, skipping for now to use default)
        # main_client.reinitialize_suite(...) 
        
        available_tasks = main_client.get_suite_task_list(max_index=-1)
        print(f"Available tasks in suite: {len(available_tasks)}")
    except Exception as e:
        print(f"Failed to query suite: {e}")
        return

    # Filter tasks
    tasks_to_run = []
    if FLAGS.tasks:
        for t in FLAGS.tasks:
            if t in available_tasks:
                tasks_to_run.append(t)
            else:
                print(f"-" * 50)
                print(f"Available tasks: {available_tasks}")
                print(f"Warning: Task {t} not found in suite.")
                print(f"-" * 50)
    else:
        tasks_to_run = available_tasks

    print(f"Selected {len(tasks_to_run)} task types to run.")
    
    # Create Task Queue
    # Each item is (task_type, task_idx)
    # We query how many combinations exist for each task type
    task_queue = queue.Queue()
    total_tasks_count = 0
    
    for task_type in tasks_to_run:
        try:
            n_tasks = main_client.get_suite_task_length(task_type)
            # Apply limit if needed, overrides server count if smaller? 
            # Usually server is source of truth for instantiated tasks.
            # But we might want to run only first N combinations.
            
            # If n_task_combinations flag is set, we might have re-initialized suite
            # But here we just assume suite on server is what we want.
            # Let's trust the server's count.
            for i in range(n_tasks):
                task_queue.put((task_type, i))
                total_tasks_count += 1
        except Exception as e:
            print(f"Error getting length for {task_type}: {e}")

    print(f"Total task instances to run: {total_tasks_count}")

    # Launch Workers
    threads = []
    result_list = []
    result_lock = threading.Lock()

    for i, url in enumerate(docker_urls):
        t = threading.Thread(
            target=run_worker,
            args=(i, url, task_queue, result_list, result_lock)
        )
        t.start()
        threads.append(t)

    # Wait for completion
    task_queue.join()
    
    # Wait for threads to finish (they should exit when queue is empty)
    for t in threads:
        t.join()

    # Print Summary
    print("\n" + "="*40)
    print(f"Execution Completed. Total tasks: {total_tasks_count}")
    print("="*40)
    success_count = sum(1 for r in result_list if r["success"])
    if len(result_list) > 0:
        print(f"Success Rate: {success_count}/{len(result_list)} ({success_count/len(result_list)*100:.1f}%)")
    else:
        print("No tasks were completed successfully.")
    
    # Detailed results
    # could save to csv/json
    output_result_file = os.path.join(FLAGS.output_path, "results_summary.json")
    if not os.path.exists(FLAGS.output_path):
        os.makedirs(FLAGS.output_path)
        
    with open(output_result_file, 'w') as f:
        json.dump(result_list, f, indent=2)
    
    print(f"Results saved to {output_result_file}")


if __name__ == '__main__':
    app.run(main)
