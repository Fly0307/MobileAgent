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

"""Docker version of GUI Owl agent."""

from typing import Any, Optional
import numpy as np
import time

from android_world.env import interface
from android_world.env import json_action
from android_world.agents import gui_owl
from android_world.env import representation_utils


class DockerEnvAdapter(interface.AsyncEnv):
  """Adapter for interacting with the Android environment via Docker client."""

  def __init__(self, client: Any):
    """Initializes the adapter.
    
    Args:
      client: An instance of AndroidEnvClient from run_suite_on_docker.py
    """
    self.client = client
    self._interaction_cache = ''

  @property
  def controller(self) -> Any:
    """Returns the controller. Not used in Docker mode usually."""
    return None

  def reset(self, go_home: bool = False) -> interface.State:
    """Resets the environment."""
    self.client.reset(go_home=go_home)
    self._interaction_cache = ''
    return self.get_state()

  def get_state(self, wait_to_stabilize: bool = False) -> interface.State:
    """Gets the state of the environment."""
    # The client returns a numpy array of pixels
    pixels = self.client.get_screenshot(wait_to_stabilize=wait_to_stabilize)
    
    # We create a State object. Docker client currently doesn't return forest/ui_elements
    # so we provide empty/dummy values. GUI Owl relies on vision (pixels).
    return interface.State(
        pixels=pixels,
        forest=None,
        ui_elements=[],
        auxiliaries={}
    )

  def display_message(self, message: str, header: str = '') -> None:
    """Displays a message on the screen."""
    # Not supported or requires server-side implementation
    pass

  def ask_question(
      self, question: str, timeout_seconds: float = -1.0
  ) -> str | None:
    raise NotImplementedError('ask_question is not implemented.')

  def execute_action(self, action: json_action.JSONAction) -> None:
    """Executes action on the environment."""
    if action.action_type == json_action.ANSWER:
      self._interaction_cache = action.text
      # We could log this or send to server if supported
      return
    if action.action_type == json_action.STATUS:
      return
    print("[DEBUG] Executing action on http://localhost:5000:", action)
    self.client.execute_action(action)

  @property
  def foreground_activity_name(self) -> str:
    # Not supported by current simple client
    return ''

  @property
  def device_screen_size(self) -> tuple[int, int]:
    # We can infer from screenshot or hardcode if standard
    screenshot = self.client.get_screenshot()
    return (screenshot.shape[1], screenshot.shape[0])

  @property
  def logical_screen_size(self) -> tuple[int, int]:
    # Assuming logical = physical for now or query server if added
    return self.device_screen_size

  @property
  def interaction_cache(self) -> str:
    return self._interaction_cache

  def hide_automation_ui(self) -> None:
    pass

  @property
  def orientation(self) -> int:
    return 0  # Assume portrait

  @property
  def physical_frame_boundary(self) -> tuple[int, int, int, int]:
    return (0, 0, 0, 0)

  def close(self) -> None:
    self.client.close()


class GUIOwlDocker(gui_owl.GUIOwl):
  """GUI Owl agent for Docker environment."""

  def __init__(
      self,
      client: Any,
      vllm,
      src_format,
      api_key,
      url,
      name: str = "Mobile_Agent_Docker",
      output_path="",
      use_task_enhancement: bool = True,
  ):
    # Create the adapter
    env_adapter = DockerEnvAdapter(client)
    
    super().__init__(
        env=env_adapter,
        vllm=vllm,
        src_format=src_format,
        api_key=api_key,
        url=url,
        name=name,
        output_path=output_path,
        use_task_enhancement=use_task_enhancement
    )

  def initialize_chrome(self):
    print("Running additional chrome initialization (Docker optimized)...")
    # In Docker mode, we prefer 'open_app' action which is robust
    try:
        # We can use the open_app action directly via execute_action
        open_chrome = json_action.JSONAction(
            action_type=json_action.OPEN_APP,
            app_name='chrome'
        )
        self.env.execute_action(open_chrome)
        time.sleep(5)
    except Exception as e:
        print(f"Failed to open chrome: {e}")

    # For the specific UI clicks (Terms accept etc), we might need to blindly click
    # or rely on the agent's general capability if this initialization is part of the task.
    # If it's a pre-step, we might skip strict 'No thanks' flows if env is already set up.
    print("Done additional chrome initialization")

    # Override step to ensure we handle any Docker-specific quirks if needed
    # But base implementation should work thanks to DockerEnvAdapter
