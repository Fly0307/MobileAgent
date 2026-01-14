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

"""Experience utilities for task description enhancement.

This module provides functionality to match task descriptions with experience
templates and generate enhanced task descriptions using LLM-based planning.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional, Tuple

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from openai import OpenAI

# Disable default OpenAI LLM globally
Settings.llm = None

# 获取当前文件的绝对路径
_current_file_path = Path(__file__).resolve()
_current_dir = _current_file_path.parent

# 默认模板路径
_DEFAULT_TEMPLATE_PATH = _current_dir / "experience" / "experience.json"
# 默认持久化存储路径
_DEFAULT_STORAGE_DIR = _current_dir / "experience" / "storage"
# 默认 prompt 模板路径
_DEFAULT_PROMPT_TEMPLATE_PATH = _current_dir / "experience" / "planner_oneshot.md"

# 当主 Planner LLM 调用失败时使用的固定备用配置。
_FALLBACK_PLANNER_CONFIG = {
  "api_key": "sk-xxx",
  "base_url": "http://ipads.chat.gpt:3006/v1",
  "model": "deepseek/deepseek-v3.1-terminus",
}

def _load_prompt_template(template_path: Path) -> str:
  """加载 prompt 模板文件."""
  try:
    with open(template_path, 'r', encoding='utf-8') as f:
      return f.read()
  except FileNotFoundError:
    print(f"[EXPERIENCE] Prompt template not found at {template_path}, using default.", flush=True)
    return _get_default_planner_prompt()


def _get_default_planner_prompt() -> str:
  """返回默认的 planner prompt."""
  return """## Role Definition
You are a task planning expert responsible for understanding user intent, selecting the most appropriate application, and generating a structured, executable final task description.

## Input
1. Original user task description: "{task_description}"
2. Relevant experience/template:
```
"{experience_content}"
```

## Requirements
1. **Generate final task description**: Reference the most appropriate "relevant experience/template" to transform the user's original task description into a detailed, complete, and structured task description.
   - **Maintain semantic consistency**: The final description must be identical to the user's original intent.
   - **Fill and trim**:
       - If the experience/template is not relevant to the original user task description, briefly complete the task detailed steps based on the real usage of the corresponding APP.
       - Only fill steps in the template that are directly related to user needs, preserving the original user task description.
       - Handle "optional" steps: Only fill "optional" steps when explicitly required in the original task description, and remove the "optional:" label. If the original task does not explicitly require it, remove the corresponding steps.
       - Steps in the template that are not implicitly or explicitly mentioned in the original task cannot be added, and redundant steps should be removed.
       - If placeholders in the template (such as `{{city/type}}`) do not have specific information provided in the user description, remove them.
   - **Natural expression**: The output description should follow natural English language conventions and avoid redundancy.

## Output Format
Please strictly follow the JSON format below and output in English. Do not include any additional content or comments:
```json
{{
  "reasoning": "Briefly explain how you combined user requirements and the template to generate the final task description.",
  "final_task_description": "The final complete and structured task description text."
}}
```"""


class ExperienceMatcher:
  """经验模板匹配器，使用向量检索找到最相关的经验模板."""

  def __init__(
      self,
      template_path: Path = _DEFAULT_TEMPLATE_PATH,
      storage_dir: Path = _DEFAULT_STORAGE_DIR,
      embed_model_path: Optional[str] = None,
  ):
    """初始化经验匹配器.

    Args:
      template_path: 经验模板 JSON 文件路径
      storage_dir: 向量索引持久化存储目录
      embed_model_path: 嵌入模型路径，如果为 None 则尝试使用默认路径
    """
    self.template_path = Path(template_path)
    self.storage_dir = Path(storage_dir)
    self.templates = []
    self.index = None

    # 初始化嵌入模型
    if embed_model_path is None:
      # 尝试多个可能的路径
      possible_paths = [
          _current_dir / "experience" / "BAAI" / "bge-small-en-v1.5",
          Path("./MobiAgent/utils/experience/BAAI/bge-small-en-v1.5"),
      ]
      for path in possible_paths:
        if Path(path).exists():
          embed_model_path = str(path)
          break
      else:
        # 如果都找不到，使用 HuggingFace 模型名称
        embed_model_path = "BAAI/bge-small-en-v1.5"
        print(
            f"[EXPERIENCE] 本地嵌入模型未找到，使用 HuggingFace 模型: {embed_model_path}",
            flush=True
        )

    print(f"[EXPERIENCE] 使用嵌入模型路径: {embed_model_path}", flush=True)
    self.embed_model = HuggingFaceEmbedding(model_name=embed_model_path)

    # 加载或构建索引
    self._load_or_build_index()

  def _load_templates(self):
    """从 JSON 文件加载模板."""
    with open(self.template_path, 'r', encoding='utf-8') as f:
      data = json.load(f)
      # 处理列表格式
      if isinstance(data, list):
        self.templates = data
      elif isinstance(data, dict) and "templates" in data:
        self.templates = data["templates"]
      else:
        self.templates = []

  def _load_or_build_index(self):
    """如果存储中存在索引，则加载它，否则构建它."""
    if (self.storage_dir / "docstore.json").exists():
      try:
        print(f"[EXPERIENCE] 从 {self.storage_dir} 加载现有索引...", flush=True)
        storage_context = StorageContext.from_defaults(persist_dir=self.storage_dir)
        self.index = load_index_from_storage(
            storage_context, embed_model=self.embed_model
        )
        print("[EXPERIENCE] 索引加载成功。", flush=True)
      except Exception as e:
        print(f"[EXPERIENCE] 从存储加载索引失败: {e}。正在重建索引...", flush=True)
        self._build_index()
    else:
      print(f"[EXPERIENCE] 在 {self.storage_dir} 未找到现有索引。正在构建新索引...", flush=True)
      self._build_index()

  def _build_index(self):
    """从加载的模板构建 llama_index 并将其保存到存储中."""
    self._load_templates()
    if not self.templates:
      print("[EXPERIENCE] 未加载任何模板。无法构建索引。", flush=True)
      return

    print("[EXPERIENCE] 正在从模板创建文档...", flush=True)
    documents = []

    for template in self.templates:
      # AndroidWorld_templates-70.json 格式
      if 'task_name' in template and 'full_experience' in template:
        document_text = json.dumps(
            {
                "task_name": template.get("task_name", ""),
                "description": template.get("description", ""),
                "full_experience": template.get("full_experience", ""),
            },
            ensure_ascii=False,
        )

        metadata = {
            "keywords": template.get("keywords", []),
            "description": template.get("description", ""),
            "task_name": template.get("task_name", ""),
        }

        documents.append(Document(text=document_text, metadata=metadata))

    if not documents:
      print("[EXPERIENCE] 没有有效的文档可以构建索引。", flush=True)
      return

    # 创建存储上下文并构建索引
    storage_context = StorageContext.from_defaults()
    print("[EXPERIENCE] 正在从文档构建索引...", flush=True)
    self.index = VectorStoreIndex.from_documents(
        documents, embed_model=self.embed_model, storage_context=storage_context
    )

    # 持久化到磁盘
    print(f"[EXPERIENCE] 正在将索引保存到 {self.storage_dir}...", flush=True)
    self.storage_dir.mkdir(parents=True, exist_ok=True)
    self.index.storage_context.persist(persist_dir=self.storage_dir)
    print("[EXPERIENCE] 索引构建并保存成功。", flush=True)

  def query(self, task_description: str, top_k: int = 1):
    """查询索引以查找最相关的模板.

    Args:
      task_description: 任务描述
      top_k: 返回最相关的 k 个结果

    Returns:
      查询结果对象
    """
    if not self.index:
      print("[EXPERIENCE] 索引未初始化。", flush=True)
      return None
    query_engine = self.index.as_query_engine(llm=None, similarity_top_k=top_k)
    response = query_engine.query(task_description)
    return response

  def extract_full_experience(self, result) -> Tuple[Optional[str], Optional[float]]:
    """从查询结果中提取 full_experience 内容和相似度分数.

    Args:
      result: 查询结果对象

    Returns:
      (full_experience 字符串, 相似度分数) 的元组，如果未找到则返回 (None, None)
    """
    if not result or not hasattr(result, 'response'):
      return None, None

    result_str = str(result.response)
    # print(f"[EXPERIENCE] 提取 full_experience 字段内容: {result_str}", flush=True)  # Debug 日志，暂时注释

    # 尝试从响应中提取 JSON 对象
    # 方法 1: 查找包含 full_experience 的 JSON 对象
    json_pattern = r'\{[^{}]*"full_experience"[^{}]*\}'
    matches = re.findall(json_pattern, result_str, re.DOTALL)

    for match in matches:
      try:
        parsed = json.loads(match)
        full_experience = parsed.get("full_experience")
        if full_experience:
          # 尝试从 source_nodes 获取相似度分数
          similarity_score = None
          if hasattr(result, 'source_nodes') and result.source_nodes:
            for node in result.source_nodes:
              if hasattr(node, 'score'):
                similarity_score = node.score
                break
          return full_experience, similarity_score
      except json.JSONDecodeError:
        continue

    # 方法 2: 尝试从源文档中提取
    if hasattr(result, 'source_nodes') and result.source_nodes:
      for node in result.source_nodes:
        similarity_score = None
        if hasattr(node, 'score'):
          similarity_score = node.score
        
        if hasattr(node, 'node') and hasattr(node.node, 'text'):
          try:
            doc_data = json.loads(node.node.text)
            full_experience = doc_data.get("full_experience")
            if full_experience:
              return full_experience, similarity_score
          except (json.JSONDecodeError, AttributeError):
            continue

    return None, None

  def get_experience(
      self, 
      task_description: str, 
      top_k: int = 1,
      similarity_threshold: float = 0.7
  ) -> Optional[str]:
    """通过查询模板并提取 full_experience 字段来获取经验.

    Args:
      task_description: 任务描述
      top_k: 返回最相关的 k 个结果
      similarity_threshold: 相似度阈值，低于此值则不使用经验（默认 0.7）

    Returns:
      full_experience 字符串，如果未找到或相似度太低则返回 None
    """
    result = self.query(task_description, top_k)
    if result:
      full_experience, similarity_score = self.extract_full_experience(result)
      if full_experience is None:
        return None
      
      # 检查相似度分数
      if similarity_score is not None:
        print(f"[EXPERIENCE] 检索到的经验相似度分数: {similarity_score:.4f} (阈值: {similarity_threshold})", flush=True)
        if similarity_score < similarity_threshold:
          print(f"[EXPERIENCE] 相似度分数 {similarity_score:.4f} 低于阈值 {similarity_threshold}，不使用经验。", flush=True)
          return None
      else:
        print("[EXPERIENCE] 无法获取相似度分数，使用经验（可能存在风险）。", flush=True)
      
      return full_experience
    return None


def parse_planner_response(response_str: str) -> Optional[dict[str, Any]]:
  """解析 planner LLM 的响应为 JSON.

  Args:
    response_str: LLM 响应字符串

  Returns:
    解析后的 JSON 字典，如果解析失败则返回 None
  """
  # 尝试匹配 ```json ... ``` 代码块
  pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
  match = pattern.search(response_str)

  json_str = None
  if match:
    json_str = match.group(1)
  else:
    # 如果没有代码块，直接当成 JSON
    json_str = response_str.strip()

  try:
    data = json.loads(json_str)
    return data
  except json.JSONDecodeError as e:
    print(f"[EXPERIENCE] 解析 JSON 失败: {e}\n内容为:\n{json_str}", flush=True)
    return None


class PlannerLLMClient:
  """Planner 专用的 LLM 客户端，从环境变量读取配置."""

  def __init__(self):
    """从环境变量初始化 planner LLM 客户端."""
    # 从环境变量读取配置
    # self.model = os.environ.get("PLANNER_MODEL", "")
    # self.api_key = os.environ.get("OPENAI_API_KEY", "")
    # self.base_url = os.environ.get("OPENAI_BASE_URL", None)
    self.model = ""
    self.api_key = "dummy"
    self.base_url = "http://123.60.91.241:8000/v1"
    self.temperature = float(os.environ.get("PLANNER_TEMPERATURE", "0.0"))

    # if not self.model:
    #   raise RuntimeError(
    #       "PLANNER_MODEL 环境变量未设置。请设置 planner 模型名称。"
    #   )
    # if not self.api_key:
    #   raise RuntimeError(
    #       "OPENAI_API_KEY 环境变量未设置。请设置 OpenAI API key。"
    #   )

    # 初始化 OpenAI 客户端
    # 如果设置了 OPENAI_BASE_URL，则使用自定义 base_url；否则使用标准 OpenAI API
    client_kwargs = {"api_key": self.api_key}
    if self.base_url:
      client_kwargs["base_url"] = self.base_url
      print(
          f"[EXPERIENCE] Planner LLM 客户端已初始化: model={self.model}, base_url={self.base_url}",
          flush=True
      )
    else:
      print(
          f"[EXPERIENCE] Planner LLM 客户端已初始化: model={self.model} (使用标准 OpenAI API)",
          flush=True
      )
    self.client = OpenAI(**client_kwargs)

  def predict_json(self, prompt: str) -> str:
    """调用 LLM 并强制返回 JSON 格式响应.

    Args:
      prompt: 输入 prompt

    Returns:
      LLM 响应字符串（JSON 格式）

    Raises:
      RuntimeError: 如果 API 调用失败
    """
    def _call_with_client(client: OpenAI, model: str) -> str:
      response = client.chat.completions.create(
          model=model,
          messages=[
              {
                  "role": "user",
                  "content": prompt,
              }
          ],
          temperature=self.temperature,
          response_format={"type": "json_object"},
      )
      if not response.choices:
        raise RuntimeError("API returned no choices in response")
      content = response.choices[0].message.content
      if content is None or content.strip() == "":
        raise RuntimeError("API returned empty or None content in response")
      return content

    last_primary_error: Optional[Exception] = None

    try:
      return _call_with_client(self.client, self.model)
    except Exception as primary_error:
      print(
          f"[EXPERIENCE] Planner LLM 调用失败: {primary_error}，尝试使用备用配置...",
          flush=True,
      )
      last_primary_error = primary_error

    try:
      fallback_client = OpenAI(
          api_key=_FALLBACK_PLANNER_CONFIG["api_key"],
          base_url=_FALLBACK_PLANNER_CONFIG["base_url"],
      )
      fallback_result = _call_with_client(
          fallback_client,
          _FALLBACK_PLANNER_CONFIG["model"],
      )
      print("[EXPERIENCE] 备用 Planner LLM 调用成功。", flush=True)
      return fallback_result
    except Exception as fallback_error:
      error_msg = (
        "Planner LLM 调用失败: primary 配置与备用配置均不可用; "
        f"primary_error={last_primary_error}; fallback_error={fallback_error}"
      )
      print(f"[EXPERIENCE] {error_msg}", flush=True)
      raise RuntimeError(error_msg) from fallback_error


# 全局 planner 客户端实例（懒加载）
_planner_client: Optional[PlannerLLMClient] = None


def _get_planner_client() -> PlannerLLMClient:
  """获取全局 planner 客户端实例（懒加载）."""
  global _planner_client
  if _planner_client is None:
    _planner_client = PlannerLLMClient()
  return _planner_client


class ExperienceLoader:
  """经验加载器，支持按 task name 直接查找经验."""

  def __init__(self, template_path: Path = _DEFAULT_TEMPLATE_PATH):
    """初始化经验加载器.

    Args:
      template_path: 经验模板 JSON 文件路径
    """
    self.template_path = Path(template_path)
    self.templates = []
    self.experience_dict = {}  # 按 task_name 索引的经验字典
    self._load_templates()

  def _load_templates(self):
    """从 JSON 文件加载模板并构建索引."""
    try:
      with open(self.template_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # 处理列表格式
        if isinstance(data, list):
          self.templates = data
        elif isinstance(data, dict) and "templates" in data:
          self.templates = data["templates"]
        else:
          self.templates = []

      # 按 task_name 构建索引
      for template in self.templates:
        if 'task_name' in template and 'full_experience' in template:
          task_name = template['task_name']
          self.experience_dict[task_name] = template
          print(f"[EXPERIENCE] 加载经验: {task_name}", flush=True)

      print(
          f"[EXPERIENCE] 成功加载 {len(self.experience_dict)} 个经验模板。",
          flush=True
      )
    except Exception as e:
      print(f"[EXPERIENCE] 加载经验模板失败: {e}", flush=True)

  def get_experience_by_name(self, task_name: str) -> Optional[dict]:
    """按 task_name 查找经验.

    Args:
      task_name: 任务名称

    Returns:
      包含经验的字典，如果未找到则返回 None
    """
    return self.experience_dict.get(task_name)


# 全局经验加载器实例（懒加载）
_experience_loader: Optional[ExperienceLoader] = None


def _get_experience_loader() -> ExperienceLoader:
  """获取全局经验加载器实例（懒加载）."""
  global _experience_loader
  if _experience_loader is None:
    _experience_loader = ExperienceLoader()
  return _experience_loader


def enhance_task_with_experience(
    original_task: str,
    experience_matcher: Optional[ExperienceMatcher] = None,
    prompt_template_path: Optional[Path] = None,
) -> str:
  """使用经验模板增强任务描述.

  Args:
    original_task: 原始任务描述
    experience_matcher: 经验匹配器，如果为 None 则创建新的
    prompt_template_path: Prompt 模板路径，如果为 None 则使用默认路径

  Returns:
    增强后的任务描述
  """
  # 初始化经验匹配器
  if experience_matcher is None:
    experience_matcher = ExperienceMatcher()

  # 检索相关经验
  experience_content = experience_matcher.get_experience(original_task, top_k=1, similarity_threshold=0.6)
  if not experience_content:
    print(f"[EXPERIENCE] 未找到相关经验，返回原始任务描述:{original_task}。", flush=True)
    return original_task

  print(f"[EXPERIENCE] 检索到的相关经验:\n{experience_content}", flush=True)

  # 加载 prompt 模板
  if prompt_template_path is None:
    prompt_template_path = _DEFAULT_PROMPT_TEMPLATE_PATH

  planner_prompt_template = _load_prompt_template(prompt_template_path)

  # 构建 prompt
  prompt = planner_prompt_template.format(
      task_description=original_task, experience_content=experience_content
  )

  # 获取 planner 客户端并调用 LLM（强制 JSON 模式）
  print(f"[EXPERIENCE] 调用 Planner LLM 生成增强的任务描述（JSON 模式）...\n\toriginal_task is: {original_task}", flush=True)
  try:
    planner_client = _get_planner_client()
    response_str = planner_client.predict_json(prompt)
    print(f"[EXPERIENCE] Planner 响应: \n{response_str}", flush=True)
  except Exception as e:
    print(f"[EXPERIENCE] 调用 Planner LLM 失败: {e}，返回原始任务描述。", flush=True)
    return original_task

  # 解析响应
  response_json = parse_planner_response(response_str)
  if response_json is None:
    print("[EXPERIENCE] 无法解析模型响应为 JSON，返回原始任务描述。", flush=True)
    return original_task

  final_description = response_json.get("final_task_description", original_task)
  return final_description


def enhance_task_with_experience_v2(
    original_task: str,
    task_name: str,
    prompt_template_path: Optional[Path] = None,
    use_planner: bool = True,
) -> str:
  """使用经验模板增强任务描述（V2 版本，直接按 task_name 匹配）.

  此版本支持直接按 task_name 从 experience.json 查找经验，无需 RAG 检索。

  Args:
    original_task: 原始任务描述
    task_name: 任务名称（用于直接查找经验）
    prompt_template_path: Prompt 模板路径，如果为 None 则使用默认路径
    use_planner: 是否使用 Planner LLM 进行增强，如果为 False 则直接返回经验内容

  Returns:
    增强后的任务描述。如果未找到对应的经验，返回原始任务描述。
  """
  # 获取全局经验加载器
  experience_loader = _get_experience_loader()

  # 按 task_name 查找经验
  experience_template = experience_loader.get_experience_by_name(task_name)
  if not experience_template:
    print(
        f"[EXPERIENCE_V2] 未找到 task_name 为 '{task_name}' 的经验，返回原始任务描述。",
        flush=True
    )
    return original_task

  experience_content = experience_template.get('full_experience', '')
  if not experience_content:
    print(
        f"[EXPERIENCE_V2] 任务 '{task_name}' 的经验内容为空，返回原始任务描述。",
        flush=True
    )
    return original_task

  print(
      f"[EXPERIENCE_V2] 成功匹配经验 (task_name: {task_name}):\n{experience_content}",
      flush=True
  )

  # 如果不使用 planner，直接返回经验内容
  if not use_planner:
    print(
        f"[EXPERIENCE_V2] Planner 已禁用，直接返回经验内容。",
        flush=True
    )
    return experience_content

  # 加载 prompt 模板
  if prompt_template_path is None:
    prompt_template_path = _DEFAULT_PROMPT_TEMPLATE_PATH

  planner_prompt_template = _load_prompt_template(prompt_template_path)

  # 构建 prompt
  prompt = planner_prompt_template.format(
      task_description=original_task, experience_content=experience_content
  )

  # 获取 planner 客户端并调用 LLM（强制 JSON 模式）
  print(
      f"[EXPERIENCE_V2] 调用 Planner LLM 生成增强的任务描述（JSON 模式）...\n\t"
      f"original_task: {original_task}\n\ttask_name: {task_name}",
      flush=True
  )
  try:
    planner_client = _get_planner_client()
    response_str = planner_client.predict_json(prompt)
    print(f"[EXPERIENCE_V2] Planner 响应: \n{response_str}", flush=True)
  except Exception as e:
    print(
        f"[EXPERIENCE_V2] 调用 Planner LLM 失败: {e}，返回原始任务描述。",
        flush=True
    )
    return original_task

  # 解析响应
  response_json = parse_planner_response(response_str)
  if response_json is None:
    print(
        "[EXPERIENCE_V2] 无法解析模型响应为 JSON，返回原始任务描述。",
        flush=True
    )
    return original_task

  final_description = response_json.get("final_task_description", original_task)
  print(
      f"[EXPERIENCE_V2] 任务增强完成。\n"
      f"  原始任务: {original_task}\n"
      f"  增强后任务: {final_description}",
      flush=True
  )
  return final_description

