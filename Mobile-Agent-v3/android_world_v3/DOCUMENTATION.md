# Android World 服务器和客户端文档

## 概述

本文档详细说明了 Android World 框架中的服务器端（`android_server.py`）和客户端（`run_suite_on_docker.py`）的架构、逻辑和使用方法。

## 目录

- [系统架构](#系统架构)
- [服务器端 (android_server.py)](#服务器端-android_serverpy)
  - [核心组件](#核心组件)
  - [API 端点](#api-端点)
  - [生命周期管理](#生命周期管理)
- [客户端 (run_suite_on_docker.py)](#客户端-run_suite_on_dockerpy)
  - [AndroidEnvClient 类](#androidenvclient-类)
  - [主要方法](#主要方法)
  - [使用示例](#使用示例)
- [完整工作流程](#完整工作流程)
- [错误处理](#错误处理)
- [最佳实践](#最佳实践)

---

## 系统架构

整个系统采用 **客户端-服务器（Client-Server）架构**：

```
┌─────────────────────────┐         HTTP API          ┌──────────────────────────┐
│                         │    (localhost:5000)       │                          │
│  run_suite_on_docker.py │ ◄─────────────────────► │   android_server.py      │
│      (客户端)            │                          │      (服务器端)           │
│                         │                          │                          │
│  - AndroidEnvClient     │                          │  - FastAPI 应用          │
│  - 发送请求             │                          │  - Android 环境管理       │
│  - 处理响应             │                          │  - 任务套件管理           │
└─────────────────────────┘                          └──────────────────────────┘
                                                                │
                                                                │ 控制
                                                                ▼
                                                      ┌──────────────────────┐
                                                      │  Android Emulator    │
                                                      │  (模拟器/设备)        │
                                                      └──────────────────────┘
```

**关键特性：**
- 服务器运行在 Docker 容器中，监听端口 5000
- 客户端通过 HTTP REST API 与服务器通信
- 服务器管理 Android 模拟器和任务执行
- 支持并发请求和异步操作

---

## 服务器端 (android_server.py)

### 核心组件

#### 1. FastAPI 应用

```python
app = fastapi.FastAPI(lifespan=lifespan)
```

使用 FastAPI 框架构建 RESTful API 服务器，提供高性能的异步处理能力。

#### 2. 生命周期管理

```python
@contextlib.asynccontextmanager
async def lifespan(fast_api_app: fastapi.FastAPI):
```

**功能：**
- **启动阶段：**
  - 初始化 Android 环境（模拟器）
  - 加载任务注册表（TaskRegistry）
  - 创建初始任务套件（Suite）
  - 配置 ADB 路径和端口

- **运行阶段：**
  - 维护环境和任务套件的状态
  - 处理客户端请求

- **关闭阶段：**
  - 清理 Android 环境
  - 释放资源

**初始化参数：**
```python
app_android_env = env_launcher.load_and_setup_env(
    console_port=5554,        # 模拟器控制台端口
    emulator_setup=True,      # 启用模拟器设置
    freeze_datetime=True,     # 冻结时间（确保可重复性）
    adb_path="/opt/android/platform-tools/adb"  # ADB 工具路径
)
```

#### 3. 状态管理

服务器在 `app.state` 中维护以下全局状态：
- `app_android_env`: Android 环境实例
- `suite`: 当前任务套件
- `task_registry`: 任务注册表

#### 4. 路由器

服务器使用两个独立的路由器组织 API：
- **Suite Router** (`/suite`): 管理任务套件
- **Task Router** (`/task`): 管理单个任务

### API 端点

#### 环境控制端点

##### 1. POST `/reset`

**功能：** 重置 Android 环境

**参数：**
- `go_home` (bool): 是否返回主屏幕

**返回：**
```json
{
  "status": "success",
  "message": "Environment reset with go_home=True."
}
```

**用途：**
- 任务执行前清理环境
- 任务执行后恢复初始状态
- 从错误状态中恢复

##### 2. GET `/screenshot`

**功能：** 获取当前屏幕截图

**参数：**
- `wait_to_stabilize` (bool): 是否等待屏幕稳定

**返回：**
```json
{
  "pixels": [/* 像素数组 */]
}
```

**用途：**
- 获取环境的视觉状态
- 用于 Agent 决策
- 调试和日志记录

##### 3. POST `/execute_action`

**功能：** 在 Android 环境中执行操作

**请求体：**
```json
{
  "action_type": "click",
  "x": 100,
  "y": 200
}
```

**支持的动作类型：**
- `click`: 点击操作
- `type`: 文本输入
- `scroll`: 滚动操作
- 其他 JSONAction 支持的动作

**返回：**
```json
{
  "status": "success",
  "message": "Action click executed."
}
```

##### 4. GET `/health`

**功能：** 检查服务器健康状态

**返回：**
```json
{
  "status": "success"
}
```

**用途：**
- 客户端连接前检查服务器是否就绪
- 监控服务器状态

##### 5. POST `/close`

**功能：** 关闭 Android 环境

**返回：**
```json
{
  "status": "success"
}
```

#### 套件管理端点 (Suite Router)

##### 1. GET `/suite/task_list`

**功能：** 获取任务套件中的任务列表

**参数：**
- `max_index` (int): 返回的最大任务数量，-1 表示全部

**返回：**
```json
{
  "task_list": ["SimpleCalculatorAddition", "ContactsLookUp", ...]
}
```

**用途：**
- 发现可用的任务类型
- 迭代执行所有任务

##### 2. GET `/suite/task_length`

**功能：** 获取特定任务类型的实例数量

**参数：**
- `task_type` (str): 任务类型名称

**返回：**
```json
{
  "length": 5
}
```

**说明：**
每个任务类型可能有多个实例（不同参数配置）。

##### 3. GET `/suite/reinitialize`

**功能：** 重新初始化任务套件

**参数：**
- `n_task_combinations` (int, 默认: 2): 每个任务类型的组合数
- `seed` (int, 默认: 42): 随机种子（保证可重复性）
- `task_family` (str, 默认: "android_world"): 任务家族名称

**返回：**
```json
{
  "status": "success",
  "message": "Task suite re-initialized with n_task_combinations=2, seed=42."
}
```

**用途：**
- 更改任务配置
- 生成新的任务组合
- 使用不同的随机种子

#### 任务管理端点 (Task Router)

##### 1. POST `/task/initialize`

**功能：** 初始化特定任务

**参数：**
- `task_type` (str): 任务类型
- `task_idx` (int): 任务索引

**返回：**
```json
{
  "status": "success",
  "message": "Task SimpleCalculatorAddition 0 initialized."
}
```

**内部操作：**
- 设置任务所需的初始状态
- 安装/配置必要的应用
- 准备测试数据

##### 2. POST `/task/tear_down`

**功能：** 清理任务

**参数：**
- `task_type` (str): 任务类型
- `task_idx` (int): 任务索引

**返回：**
```json
{
  "status": "success",
  "message": "Task SimpleCalculatorAddition 0 torn down."
}
```

**内部操作：**
- 清理任务产生的数据
- 卸载临时安装的应用
- 恢复环境状态

##### 3. GET `/task/score`

**功能：** 获取任务完成分数

**参数：**
- `task_type` (str): 任务类型
- `task_idx` (int): 任务索引

**返回：**
```json
{
  "score": 1.0
}
```

**分数说明：**
- `1.0`: 任务完全成功
- `0.0`: 任务失败
- `0.0 ~ 1.0`: 部分完成

##### 4. GET `/task/goal`

**功能：** 获取任务目标描述

**参数：**
- `task_type` (str): 任务类型
- `task_idx` (int): 任务索引

**返回：**
```json
{
  "goal": "Use the calculator to add 5 and 3, then verify the result is 8."
}
```

**用途：**
- 向 Agent 提供任务说明
- 人类可读的任务描述

##### 5. GET `/task/template`

**功能：** 获取任务模板信息

**参数：**
- `task_type` (str): 任务类型
- `task_idx` (int): 任务索引

**返回：**
```json
{
  "template": "SimpleCalculatorAddition(num1=5, num2=3)"
}
```

**用途：**
- 获取任务的详细配置
- 调试和日志记录

---

## 客户端 (run_suite_on_docker.py)

### AndroidEnvClient 类

这是一个封装了所有服务器交互的 Python 客户端类。

#### 初始化

```python
client = AndroidEnvClient()
```

**功能：**
- 设置服务器基础 URL (`http://localhost:5000`)
- 打印初始化日志

### 主要方法

#### 1. 健康检查

```python
def health(self) -> bool:
```

**使用：**
```python
if client.health():
    print("Server is ready")
```

**说明：**
- 检查服务器是否在线
- 验证环境是否正确初始化
- 建议在开始任务前调用

#### 2. 环境重置

```python
def reset(self, go_home: bool) -> Response:
```

**使用：**
```python
response = client.reset(go_home=True)
```

**参数：**
- `go_home`: True 返回主屏幕，False 保持当前界面

#### 3. 获取屏幕截图

```python
def get_screenshot(self, wait_to_stabilize: bool = False) -> np.ndarray:
```

**使用：**
```python
screenshot = client.get_screenshot(wait_to_stabilize=True)
print(f"Screenshot shape: {screenshot.shape}")
```

**返回：**
- NumPy 数组格式的屏幕像素
- 形状通常为 `(height, width, channels)`

#### 4. 执行动作

```python
def execute_action(self, action: json_action.JSONAction) -> Response:
```

**使用示例：**

```python
# 点击操作
action = json_action.JSONAction(action_type="click", x=100, y=200)
client.execute_action(action)

# 文本输入
action = json_action.JSONAction(action_type="type", text="Hello World")
client.execute_action(action)

# 滚动操作
action = json_action.JSONAction(action_type="scroll", direction="down")
client.execute_action(action)
```

#### 5. 获取任务列表

```python
def get_suite_task_list(self, max_index: int) -> list[str]:
```

**使用：**
```python
# 获取所有任务
all_tasks = client.get_suite_task_list(max_index=-1)

# 获取前10个任务
first_10 = client.get_suite_task_list(max_index=10)
```

#### 6. 获取任务数量

```python
def get_suite_task_length(self, task_type: str) -> int:
```

**使用：**
```python
num_instances = client.get_suite_task_length("SimpleCalculatorAddition")
```

#### 7. 重新初始化套件

```python
def reinitialize_suite(
    self, 
    n_task_combinations: int = 2,
    seed: int = 42,
    task_family: str = "android_world"
) -> Response:
```

**使用：**
```python
# 使用不同配置重新初始化
client.reinitialize_suite(n_task_combinations=5, seed=12345)
```

#### 8. 任务操作

```python
# 初始化任务
def initialize_task(self, task_type: str, task_idx: int) -> Response:

# 获取任务目标
def get_task_goal(self, task_type: str, task_idx: int) -> str:

# 获取任务模板
def get_task_template(self, task_type: str, task_idx: int) -> str:

# 获取任务分数
def get_task_score(self, task_type: str, task_idx: int) -> float:

# 清理任务
def tear_down_task(self, task_type: str, task_idx: int) -> Response:
```

**完整任务执行示例：**

```python
task_type = "SimpleCalculatorAddition"
task_idx = 0

# 1. 获取任务信息
goal = client.get_task_goal(task_type, task_idx)
template = client.get_task_template(task_type, task_idx)
print(f"Goal: {goal}")
print(f"Template: {template}")

# 2. 初始化任务
client.initialize_task(task_type, task_idx)

# 3. 执行任务（使用你的 Agent 逻辑）
# ... 你的 Agent 代码 ...

# 4. 检查分数
score = client.get_task_score(task_type, task_idx)
print(f"Score: {score}")

# 5. 清理任务
client.tear_down_task(task_type, task_idx)
```

#### 9. 关闭客户端

```python
def close(self) -> None:
```

**使用：**
```python
client.close()
```

### 使用示例

#### 示例 1: 基础工作流

```python
from run_suite_on_docker import AndroidEnvClient
from android_world.env import json_action
import time

# 创建客户端
client = AndroidEnvClient()

# 等待服务器就绪
while not client.health():
    print("Waiting for server...")
    time.sleep(1)

# 重置环境
client.reset(go_home=True)

# 获取截图
screenshot = client.get_screenshot(wait_to_stabilize=True)
print(f"Screenshot dimensions: {screenshot.shape}")

# 执行一些操作
client.execute_action(json_action.JSONAction(action_type="click", x=500, y=800))

# 关闭
client.close()
```

#### 示例 2: 执行完整任务套件

```python
client = AndroidEnvClient()

# 等待服务器就绪
while not client.health():
    time.sleep(1)

# 获取所有任务
task_list = client.get_suite_task_list(max_index=-1)
print(f"Total task types: {len(task_list)}")

# 遍历所有任务
for task_name in task_list:
    num_tasks = client.get_suite_task_length(task_type=task_name)
    print(f"\n{task_name}: {num_tasks} instances")
    
    for cur_idx in range(num_tasks):
        try:
            # 获取任务信息
            goal = client.get_task_goal(task_type=task_name, task_idx=cur_idx)
            print(f"  Task {cur_idx}: {goal}")
            
            # 初始化任务
            client.initialize_task(task_type=task_name, task_idx=cur_idx)
            
            # ========================================
            # 在这里实现你的 Agent 逻辑
            # ========================================
            # 例如:
            # for step in range(max_steps):
            #     screenshot = client.get_screenshot(wait_to_stabilize=True)
            #     action = your_agent.decide(screenshot, goal)
            #     client.execute_action(action)
            #     
            #     记录截图、操作、思考等轨迹信息
            #     if action.is_done:
            #         break
            #     if max_steps <= step:
            #         break
            # 
            # 获取最终分数
            score = client.get_task_score(task_type=task_name, task_idx=cur_idx)
            print(f"  Score: {score}")
            # 记录任务信息
            # ...
            # ========================================
            
            # 清理任务
            client.tear_down_task(task_type=task_name, task_idx=cur_idx)
            
        except Exception as e:
            print(f"  Error: {e}")
            # 重置环境以防止错误传播
            client.reset(go_home=True)
            continue
        
        # 重置环境准备下一个任务
        client.reset(go_home=True)

client.close()
```

#### 示例 3: 单个任务调试

```python
client = AndroidEnvClient()

# 等待服务器
while not client.health():
    time.sleep(1)

# 选择要调试的任务
task_type = "SimpleCalculatorAddition"
task_idx = 0

# 初始化
client.reset(go_home=True)
client.initialize_task(task_type, task_idx)

# 获取任务详情
goal = client.get_task_goal(task_type, task_idx)
template = client.get_task_template(task_type, task_idx)
print(f"Goal: {goal}")
print(f"Template: {template}")

# 逐步执行并观察，或循环调用模型分析并获得执行动作
for i in range(5):
    screenshot = client.get_screenshot(wait_to_stabilize=True)
    print(f"Step {i}: Screenshot captured")
    
    # 手动测试操作
    if i == 0:
        client.execute_action(json_action.JSONAction(action_type="click", x=100, y=200))
    elif i == 1:
        client.execute_action(json_action.JSONAction(action_type="type", text="5"))
    # ... 更多步骤
    
    # 检查当前分数
    score = client.get_task_score(task_type, task_idx)
    print(f"Step {i}: Current score = {score}")

# 清理
client.tear_down_task(task_type, task_idx)
client.close()
```

---

## 完整工作流程

### 1. 启动流程

```
┌────────────────────────────────────────────────────────────┐
│ 1. 启动 Docker 容器                                         │
│    docker run --privileged -p 5000:5000 -it android_world  │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│ 2. 服务器启动 (android_server.py)                          │
│    - 加载 Android 环境                                      │
│    - 初始化任务注册表                                       │
│    - 创建任务套件                                           │
│    - 监听端口 5000                                          │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│ 3. 客户端启动 (run_suite_on_docker.py)                     │
│    - 创建 AndroidEnvClient                                 │
│    - 检查服务器健康状态                                     │
└────────────────────────────────────────────────────────────┘
```

### 2. 任务执行流程

```
┌──────────────────────┐
│ 开始                 │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 1. 重置环境          │
│    reset(go_home=True)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 获取任务列表      │
│    get_suite_task_list│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. 遍历任务类型      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 4. 对每个任务实例：                  │
│    a. get_task_goal()                │
│    b. initialize_task()              │
│    c. [执行 Agent 逻辑]              │
│    d. get_task_score()               │
│    e. tear_down_task()               │
│    f. reset(go_home=True)            │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────┐
│ 5. 关闭客户端        │
│    close()           │
└──────────────────────┘
```

### 3. Agent 执行循环（详细）

```
initialize_task()
      │
      ▼
┌─────────────────────────────────┐
│ 获取任务目标和初始状态          │
│ goal = get_task_goal()          │
│ screenshot = get_screenshot()   │
└─────────────┬───────────────────┘
              │
              ▼
         ┌────────────┐
         │ Agent 决策  │◄─────────┐
         │           │          │
         └────┬───────┘          │
              │                  │
              ▼                  │
    ┌─────────────────┐          │
    │ 执行动作        │          │
    │ execute_action()│          │
    └────┬────────────┘          │
         │                       │
         ▼                       │
    ┌─────────────────┐          │
    │ 检查任务状态    │          │
    │ get_task_score()│          │
    └────┬────────────┘          │
         │                       │
         ▼                       │
    ┌─────────────────┐          │
    │ 是否完成？      │          │
    │ score == 1.0?   │          │
    └────┬────────────┘          │
         │                       │
         ├─ 否 ───────────────────┘
         │
         └─ 是
              │
              ▼
       tear_down_task()
```

---

## 错误处理

### 常见错误和解决方案

#### 1. 服务器未就绪

**问题：**
```python
requests.exceptions.ConnectionError: Connection refused
```

**解决：**
```python
# 使用健康检查等待服务器
import time
while not client.health():
    print("Waiting for server to be ready...")
    time.sleep(1)
```

#### 2. 任务初始化失败

**问题：**
某些任务可能因为数据库或资源问题初始化失败。

**解决：**
```python
try:
    client.initialize_task(task_type=task_name, task_idx=cur_idx)
except Exception as e:
    print(f"Failed to initialize task {task_name} {cur_idx}: {e}")
    continue  # 跳过这个任务
```

**已知问题任务：**
- `RetroPlayingQueue`: 数据库表缺失
- `SimpleSmsReplyMostRecent`: 索引越界

#### 3. HTTP 请求超时

**问题：**
长时间操作可能导致超时。

**解决：**
```python
import requests

# 增加超时时间
response = requests.post(
    f"{self.base_url}/task/initialize",
    params=params,
    timeout=300  # 5分钟超时
)
```

#### 4. 响应解析错误

**问题：**
```python
pydantic.error_wrappers.ValidationError
```

**解决：**
```python
try:
    response = client.get_task_score(task_type, task_idx)
except pydantic.ValidationError as e:
    print(f"Invalid response format: {e}")
    # 处理错误
```

---

## 最佳实践

### 1. 资源管理

```python
# 使用上下文管理器模式
class AndroidEnvContext:
    def __init__(self):
        self.client = AndroidEnvClient()
    
    def __enter__(self):
        while not self.client.health():
            time.sleep(1)
        return self.client
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

# 使用
with AndroidEnvContext() as client:
    # 执行任务
    pass
# 自动清理
```

### 2. 日志记录

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('android_world.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 记录任务执行
logger.info(f"Starting task {task_type} {task_idx}")
logger.info(f"Goal: {goal}")
logger.info(f"Final score: {score}")
```

### 3. 重试机制

```python
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def initialize_task_with_retry(client, task_type, task_idx):
    return client.initialize_task(task_type, task_idx)

# 使用
try:
    initialize_task_with_retry(client, task_type, task_idx)
except Exception as e:
    logger.error(f"Failed after 3 retries: {e}")
```

### 4. 性能优化

```python
# 批量获取任务信息
def get_all_task_info(client, task_list):
    task_info = {}
    for task_type in task_list:
        num_tasks = client.get_suite_task_length(task_type)
        task_info[task_type] = {
            'count': num_tasks,
            'instances': []
        }
        for idx in range(num_tasks):
            goal = client.get_task_goal(task_type, idx)
            template = client.get_task_template(task_type, idx)
            task_info[task_type]['instances'].append({
                'idx': idx,
                'goal': goal,
                'template': template
            })
    return task_info
```

### 5. 截图保存和分析

```python
import numpy as np
from PIL import Image
import os

def save_screenshot(screenshot: np.ndarray, task_name: str, step: int):
    """保存截图到文件"""
    # 确保目录存在
    os.makedirs(f"screenshots/{task_name}", exist_ok=True)
    
    # 转换并保存
    img = Image.fromarray(screenshot.astype('uint8'))
    img.save(f"screenshots/{task_name}/step_{step:03d}.png")

# 使用
screenshot = client.get_screenshot(wait_to_stabilize=True)
save_screenshot(screenshot, task_type, step=0)
```

### 6. 结果跟踪

```python
import json
from datetime import datetime

class TaskTracker:
    def __init__(self):
        self.results = []
    
    def record_task(self, task_type, task_idx, goal, score, duration):
        self.results.append({
            'timestamp': datetime.now().isoformat(),
            'task_type': task_type,
            'task_idx': task_idx,
            'goal': goal,
            'score': score,
            'duration': duration
        })
    
    def save_results(self, filename='results.json'):
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
    
    def get_statistics(self):
        total_tasks = len(self.results)
        successful_tasks = sum(1 for r in self.results if r['score'] == 1.0)
        avg_score = sum(r['score'] for r in self.results) / total_tasks
        return {
            'total': total_tasks,
            'successful': successful_tasks,
            'success_rate': successful_tasks / total_tasks,
            'average_score': avg_score
        }

# 使用
tracker = TaskTracker()
start_time = time.time()
# ... 执行任务 ...
duration = time.time() - start_time
tracker.record_task(task_type, task_idx, goal, score, duration)
tracker.save_results()
print(tracker.get_statistics())
```

---

## 高级用法

### 自定义任务套件

```python
# 创建自定义任务套件
response = client.reinitialize_suite(
    n_task_combinations=10,  # 每个任务10个变体
    seed=12345,              # 自定义种子
    task_family="android_world"
)

# 获取新的任务列表
new_task_list = client.get_suite_task_list(max_index=-1)
```

### 并行任务执行

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def execute_single_task(task_info):
    """在单独的客户端实例中执行任务"""
    client = AndroidEnvClient()
    # ... 执行任务逻辑 ...
    client.close()
    return result

# 并行执行（注意：需要多个模拟器实例）
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(execute_single_task, task) 
               for task in task_list]
    
    for future in as_completed(futures):
        result = future.result()
        print(f"Task completed: {result}")
```

### 集成自定义 Agent

```python
class MyAgent:
    def __init__(self, client):
        self.client = client
    
    def decide_action(self, screenshot, goal):
        """基于截图和目标决定下一步动作"""
        # 实现你的 Agent 逻辑
        # 例如：使用视觉模型、LLM 等
        return json_action.JSONAction(action_type="click", x=100, y=200)
    
    def execute_task(self, task_type, task_idx, max_steps=50):
        """执行完整任务"""
        # 初始化
        goal = self.client.get_task_goal(task_type, task_idx)
        self.client.initialize_task(task_type, task_idx)
        
        # 执行循环
        for step in range(max_steps):
            screenshot = self.client.get_screenshot(wait_to_stabilize=True)
            action = self.decide_action(screenshot, goal)
            self.client.execute_action(action)
            
            score = self.client.get_task_score(task_type, task_idx)
            if score == 1.0:
                break
        
        # 清理
        final_score = self.client.get_task_score(task_type, task_idx)
        self.client.tear_down_task(task_type, task_idx)
        return final_score

# 使用
client = AndroidEnvClient()
agent = MyAgent(client)
score = agent.execute_task("SimpleCalculatorAddition", 0)
```

---

## 总结

这个框架提供了一个强大且灵活的方式来：

1. **管理 Android 测试环境**：通过 Docker 容器实现隔离和可重复性
2. **执行多样化任务**：支持广泛的 Android 应用任务
3. **开发和测试 Agent**：提供清晰的 API 用于 Agent 开发
4. **评估性能**：内置任务评分系统

**关键优势：**
- ✅ 标准化的 HTTP API
- ✅ 容器化部署
- ✅ 支持任务批量执行
- ✅ 灵活的任务配置
- ✅ 完整的生命周期管理
- ✅ 详细的错误处理

**适用场景：**
- 自动化 Android 应用测试
- AI Agent 开发和训练
- GUI 自动化研究
- 移动应用质量保证
- 机器学习模型评估

---

## 附录

### API 速查表

| 端点 | 方法 | 功能 | 关键参数 |
|------|------|------|----------|
| `/reset` | POST | 重置环境 | `go_home` |
| `/screenshot` | GET | 获取截图 | `wait_to_stabilize` |
| `/execute_action` | POST | 执行动作 | `action_dict` |
| `/health` | GET | 健康检查 | - |
| `/close` | POST | 关闭环境 | - |
| `/suite/task_list` | GET | 任务列表 | `max_index` |
| `/suite/task_length` | GET | 任务数量 | `task_type` |
| `/suite/reinitialize` | GET | 重新初始化 | `n_task_combinations`, `seed` |
| `/task/initialize` | POST | 初始化任务 | `task_type`, `task_idx` |
| `/task/tear_down` | POST | 清理任务 | `task_type`, `task_idx` |
| `/task/score` | GET | 获取分数 | `task_type`, `task_idx` |
| `/task/goal` | GET | 获取目标 | `task_type`, `task_idx` |
| `/task/template` | GET | 获取模板 | `task_type`, `task_idx` |

### 常用代码片段

```python
# 1. 快速启动
client = AndroidEnvClient()
while not client.health(): time.sleep(1)
client.reset(go_home=True)

# 2. 单任务执行
client.initialize_task(task_type, task_idx)
# ... Agent 逻辑 ...
score = client.get_task_score(task_type, task_idx)
client.tear_down_task(task_type, task_idx)

# 3. 批量执行
for task_type in client.get_suite_task_list(-1):
    for idx in range(client.get_suite_task_length(task_type)):
        # ... 执行任务 ...
        pass
```

---

**文档版本：** 1.0  
**最后更新：** 2026年1月15日  
**作者：** GitHub Copilot
