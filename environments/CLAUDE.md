[根目录](../CLAUDE.md) > **environments**

# Environments 模块 - RL 训练环境

> 最后更新：2026-04-08 18:28:35

## 模块职责

`environments/` 模块提供强化学习（RL）训练环境，用于训练和评估 Hermes Agent 的工具使用能力。该模块集成了 Gymnasium 接口，支持标准的 RL 训练流程。

主要职责：
- **RL 环境**：提供符合 Gymnasium 接口的训练环境
- **Atropos 集成**：与 Atropos RL 框架集成
- **基准测试**：评估代理在不同任务上的表现
- **工具调用解析**：解析模型输出为工具调用
- **轨迹收集**：收集训练数据用于微调

## 入口与启动

### 主要入口点
- **`environments/agent_loop.py`**：`AgentLoopEnv` - 主要的 RL 环境
- **`environments/hermes_base_env.py`**：`HermesBaseEnv` - 基础环境类

### 使用示例
```python
from environments.agent_loop import AgentLoopEnv

# 创建环境
env = AgentLoopEnv(task="write_file")

# 重置环境
observation, info = env.reset()

# 执行步骤
action = env.action_space.sample()
observation, reward, terminated, truncated, info = env.step(action)
```

## 对外接口

### AgentLoopEnv 类 (agent_loop.py)

**主要方法**：
```python
class AgentLoopEnv(gym.Env):
    def __init__(
        self,
        task: str = "generic",
        max_steps: int = 100,
        hermes_config: dict = None,
    ):
        """初始化环境。"""

    def reset(self, seed: int = None, options: dict = None):
        """重置环境。"""

    def step(self, action):
        """执行一步。返回 (observation, reward, terminated, truncated, info)。"""

    def render(self):
        """渲染环境。"""

    def close(self):
        """关闭环境。"""
```

### HermesBaseEnv 类 (hermes_base_env.py)

**主要方法**：
```python
class HermesBaseEnv(gym.Env):
    def __init__(self, config: dict = None):
        """初始化基础环境。"""

    def setup_task(self, task: str):
        """设置任务。"""

    def get_observation(self) -> dict:
        """获取观察。"""

    def compute_reward(self, action, result) -> float:
        """计算奖励。"""

    def is_done(self) -> bool:
        """检查是否完成。"""
```

### HermesSWEEnv 类 (hermes_swe_env/hermes_swe_env.py)

**主要方法**：
```python
class HermesSWEEnv(HermesBaseEnv):
    def __init__(self, repo_path: str, issue: str):
        """初始化 SWE 环境。"""

    def reset(self):
        """重置环境到初始状态。"""

    def step(self, action):
        """执行一步并返回结果。"""

    def evaluate(self) -> float:
        """评估解决方案质量。"""
```

### 工具调用解析器 (tool_call_parsers/)

**主要类和函数**：
```python
class BaseToolCallParser:
    def parse(self, response: str) -> list[dict]:
        """解析响应为工具调用列表。"""

class AnthropicToolCallParser(BaseToolCallParser):
    def parse(self, response: str) -> list[dict]:
        """解析 Anthropic 格式的工具调用。"""

class OpenAIToolCallParser(BaseToolCallParser):
    def parse(self, response: str) -> list[dict]:
        """解析 OpenAI 格式的工具调用。"""

def detect_parser(model: str) -> BaseToolCallParser:
    """自动检测适当的解析器。"""
```

## 关键依赖与配置

### 依赖项
- **Gymnasium**：RL 环境接口
- **Atropos**：Nous Research 的 RL 训练框架
- **numpy**：数值计算
- **datasets**：数据集管理

### 配置文件
- `~/.hermes/config.yaml` - 主配置文件
- `~/.hermes/rl_config.yaml` - RL 特定配置

### 环境变量
- `HERMES_RL_MODE` - 启用 RL 模式
- `HERMES_RL_TRAJECTORY_DIR` - 轨迹保存目录

## 数据模型

### 观察空间格式
```python
{
    "messages": list[dict],  # 对话历史
    "tools": list[dict],     # 可用工具
    "context": dict,         # 上下文信息
}
```

### 动作空间格式
```python
{
    "tool_name": str,        # 工具名称
    "arguments": dict,       # 工具参数
}
```

### 奖励格式
```python
{
    "reward": float,         # 奖励值
    "done": bool,            # 是否完成
    "info": dict,            # 额外信息
}
```

## 基准测试

### SWE 基准测试
**任务**：修复 GitHub 仓库中的 bug
**评估**：测试通过率、代码质量、时间效率

### 文件操作基准测试
**任务**：执行各种文件操作
**评估**：成功率、效率、正确性

### Web 浏览基准测试
**任务**：使用浏览器自动化工具
**评估**：任务完成率、步骤数、时间

## 测试与质量

### 测试文件
- `tests/environments/test_agent_loop.py` - Agent loop 环境测试
- `tests/environments/test_hermes_base_env.py` - 基础环境测试
- `tests/environments/test_hermes_swe_env.py` - SWE 环境测试
- `tests/environments/test_tool_call_parsers.py` - 工具调用解析器测试

### 测试覆盖
- **单元测试**：每个环境都有对应的测试文件
- **集成测试**：测试与 Hermes 代理的交互
- **约 15 个测试文件**覆盖核心功能

### 质量指标
- 中等测试覆盖率（~60%+）
- 符合 Gymnasium 标准
- 详细的文档字符串
- 良好的错误处理

## 常见问题 (FAQ)

### Q: 如何创建新的 RL 环境？
A: 继承 `HermesBaseEnv` 类，实现 `reset()` 和 `step()` 方法。

### Q: 如何集成 Atropos？
A: 使用 `AtroposTrainer` 类，配置环境和训练参数。

### Q: 如何收集训练数据？
A: 启用 `save_trajectories` 选项，轨迹会自动保存到 `~/.hermes/trajectories/`。

### Q: 如何评估代理性能？
A: 使用基准测试套件，运行 `pytest tests/benchmarks/`。

### Q: 如何自定义奖励函数？
A: 在环境类中重写 `compute_reward()` 方法。

### Q: 如何调试环境问题？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的环境日志。

## 相关文件清单

### 核心文件
- `environments/__init__.py` - 模块初始化
- `environments/agent_loop.py` - Agent loop 环境
- `environments/hermes_base_env.py` - 基础环境类
- `environments/hermes_swe_env/__init__.py` - SWE 环境初始化
- `environments/hermes_swe_env/hermes_swe_env.py` - SWE 环境实现

### 工具调用解析器
- `environments/tool_call_parsers/__init__.py` - 解析器基类
- `environments/tool_call_parsers/anthropic.py` - Anthropic 解析器
- `environments/tool_call_parsers/openai.py` - OpenAI 解析器
- `environments/tool_call_parsers/generic.py` - 通用解析器

### 基准测试
- `environments/benchmarks/` - 基准测试套件
- `environments/benchmarks/swe_benchmark.py` - SWE 基准测试
- `environments/benchmarks/file_ops_benchmark.py` - 文件操作基准测试
- `environments/benchmarks/web_benchmark.py` - Web 浏览基准测试

### 辅助文件
- `environments/reward_functions.py` - 奖励函数
- `environments/trajectory_collector.py` - 轨迹收集器
- `environments/evaluation.py` - 评估工具

### 测试文件
- `tests/environments/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 environments 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明 RL 环境和工具调用解析
- 🔧 **接口文档**：记录主要对外接口
- 📖 **使用指南**：提供创建新环境和评估的步骤
- 🎯 **下一步**：需要补充详细的 RL 训练指南和基准测试文档
