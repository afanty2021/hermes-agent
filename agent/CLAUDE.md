[根目录](../CLAUDE.md) > **agent**

# Agent 模块 - 代理核心逻辑

> 最后更新：2026-04-08 18:28:11

## 模块职责

`agent/` 模块是 Hermes Agent 的核心，负责代理的内部逻辑和状态管理。该模块不直接处理用户交互或工具执行，而是提供构建代理行为所需的基础设施。

主要职责：
- **提示构建**：组装系统提示、技能索引、上下文文件
- **上下文管理**：压缩、缓存、引用解析
- **记忆管理**：持久化记忆的构建和注入
- **显示格式化**：工具输出、进度指示器、错误消息
- **技能系统**：技能命令、工具提示、技能加载
- **模型元数据**：上下文长度、令牌估算、定价
- **轨迹保存**：保存对话轨迹用于训练

## 入口与启动

### 主要入口点
- **`agent/__init__.py`**：模块初始化，导出核心类和函数
- **`run_agent.py`**：`AIAgent` 类 - 主代理循环（在项目根目录）

### 关键类和函数

#### AIAgent (run_agent.py)
```python
class AIAgent:
    def __init__(self,
        model: str = "anthropic/claude-opus-4.6",
        max_iterations: int = 90,
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
        quiet_mode: bool = False,
        save_trajectories: bool = False,
        platform: str = None,
        session_id: str = None,
        skip_context_files: bool = False,
        skip_memory: bool = False,
        # ... plus provider, api_mode, callbacks, routing params
    ): ...

    def chat(self, message: str) -> str:
        """简单接口 - 返回最终响应字符串。"""

    def run_conversation(self, user_message: str, system_message: str = None,
                         conversation_history: list = None, task_id: str = None) -> dict:
        """完整接口 - 返回包含 final_response + messages 的字典。"""
```

#### 代理循环
核心循环在 `run_conversation()` 中 - 完全同步：

```python
while api_call_count < self.max_iterations and self.iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

## 对外接口

### 提示构建 (prompt_builder.py)

**主要函数**：
- `build_system_prompt()` - 构建完整系统提示
- `build_skills_system_prompt()` - 从技能目录生成技能索引
- `build_context_files_prompt()` - 扫描并注入上下文文件（AGENTS.md、.cursorrules、SOUL.md）
- `load_soul_md()` - 加载用户定义的个性文件

**安全特性**：
- 上下文文件注入前进行提示注入检测
- 扫描不可见 Unicode 字符和威胁模式
- 自动阻止可疑内容

### 上下文压缩 (context_compressor.py)

**ContextCompressor 类**：
```python
class ContextCompressor:
    def compress_context(self, messages: list, target_tokens: int) -> list:
        """压缩对话历史以适应目标令牌限制。"""
```

**策略**：
- 保留最近的工具调用和结果
- 保留系统提示
- 压缩中间对话轮次
- 维持对话连贯性

### 提示缓存 (prompt_caching.py)

**主要函数**：
- `apply_anthropic_cache_control()` - 为 Anthropic API 添加缓存控制头
- 在系统提示和工具定义上启用缓存
- 减少重复令牌使用

### 记忆管理 (memory_manager.py)

**主要函数**：
- `build_memory_context_block()` - 从记忆提供者构建记忆上下文
- 集成多个记忆提供者（内置、Honcho、Mem0 等）
- 为每轮对话注入持久化记忆

### 显示 (display.py)

**KawaiiSpinner 类**：
```python
class KawaiiSpinner:
    def __init__(self, faces: list = None, verbs: list = None):
        """动画 spinner，用于 API 调用期间。"""
    def start(self, message: str): ...
    def stop(self, message: str = None): ...
```

**工具输出格式化**：
- `build_tool_preview()` - 生成工具调用的预览字符串
- `get_cute_tool_message()` - 生成可爱的工具成功/失败消息
- `get_tool_emoji()` - 获取工具的表情符号

### 技能命令 (skill_commands.py)

**主要函数**：
- `get_all_skills_dirs()` - 扫描技能目录
- `extract_skill_description()` - 提取技能描述
- `skill_matches_platform()` - 检查技能是否在平台可用

### 模型元数据 (model_metadata.py)

**主要函数**：
- `fetch_model_metadata()` - 从 models.dev 获取模型元数据
- `estimate_tokens_rough()` - 粗略估算文本令牌数
- `estimate_messages_tokens_rough()` - 估算消息列表的令牌数
- `parse_context_limit_from_error()` - 从 API 错误解析上下文限制
- `is_local_endpoint()` - 检查端点是否为本地

### 定价 (usage_pricing.py)

**主要函数**：
- `estimate_usage_cost()` - 估算 API 使用成本
- `normalize_usage()` - 标准化使用记录
- `format_duration_compact()` - 格式化持续时间
- `format_token_count_compact()` - 格式化令牌计数

### 轨迹保存 (trajectory.py)

**主要函数**：
- `save_trajectory()` - 保存对话轨迹到文件
- `compress_trajectory()` - 压缩轨迹用于训练

## 关键依赖与配置

### 依赖项
- **OpenAI SDK**：LLM API 客户端
- **Anthropic SDK**：Claude API 客户端
- **PyYAML**：配置文件解析
- **Rich**：终端格式化

### 配置
- `~/.hermes/config.yaml` - 主配置文件
- `~/.hermes/.env` - API 密钥
- `~/.hermes/skills/` - 技能目录
- `~/.hermes/SOUL.md` - 个性文件

### 环境变量
- `HERMES_HOME` - Hermes 主目录（支持多实例）
- `HERMES_QUIET` - 抑制启动消息
- `ANTHROPIC_API_KEY` - Anthropic API 密钥
- `OPENAI_API_KEY` - OpenAI API 密钥

## 数据模型

### 消息格式
遵循 OpenAI 格式：
```python
{
    "role": "system|user|assistant|tool",
    "content": "消息内容",
    # 可选字段：
    "tool_calls": [...],  # assistant 消息
    "tool_call_id": "...",  # tool 消息
    "reasoning": "..."  # 推理内容
}
```

### 工具调用格式
```python
{
    "id": "call_...",
    "type": "function",
    "function": {
        "name": "tool_name",
        "arguments": "{\"param\": \"value\"}"
    }
}
```

### 技能索引格式
```python
{
    "name": "skill_name",
    "description": "技能描述",
    "conditions": ["平台条件"],
    "examples": ["使用示例"]
}
```

## 测试与质量

### 测试文件
- `tests/agent/test_prompt_builder.py` - 提示构建测试
- `tests/agent/test_context_compressor.py` - 上下文压缩测试
- `tests/agent/test_memory_provider.py` - 记忆提供者测试
- `tests/agent/test_display.py` - 显示格式化测试
- `tests/agent/test_model_metadata.py` - 模型元数据测试
- `tests/agent/test_usage_pricing.py` - 定价测试

### 测试覆盖
- **单元测试**：每个模块都有对应的测试文件
- **集成测试**：测试与其他模块的交互
- **约 25 个测试文件**覆盖核心功能

### 质量指标
- 高测试覆盖率（~80%+）
- 类型提示完整
- 详细的文档字符串
- 安全的提示注入检测

## 常见问题 (FAQ)

### Q: 如何添加新的提示组件？
A: 在 `prompt_builder.py` 中创建新函数，然后在 `build_system_prompt()` 中调用。

### Q: 如何自定义记忆提供者？
A: 实现 `MemoryProvider` 接口，然后在 `memory_manager.py` 中注册。

### Q: 如何添加新的 spinner 主题？
A: 创建自定义的 `faces` 和 `verbs` 列表，传递给 `KawaiiSpinner`。

### Q: 如何调试提示构建？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的提示构建日志。

### Q: 如何处理不同的模型上下文长度？
A: `model_metadata.py` 自动获取模型元数据，并在需要时压缩上下文。

## 相关文件清单

### 核心文件
- `agent/__init__.py` - 模块初始化
- `agent/prompt_builder.py` - 提示构建
- `agent/context_compressor.py` - 上下文压缩
- `agent/prompt_caching.py` - 提示缓存
- `agent/memory_manager.py` - 记忆管理
- `agent/display.py` - 显示格式化
- `agent/skill_commands.py` - 技能命令
- `agent/model_metadata.py` - 模型元数据
- `agent/usage_pricing.py` - 定价
- `agent/trajectory.py` - 轨迹保存

### 辅助文件
- `agent/anthropic_adapter.py` - Anthropic API 适配器
- `agent/auxiliary_client.py` - 辅助 LLM 客户端
- `agent/context_references.py` - 上下文引用解析
- `agent/credential_pool.py` - 凭证池管理
- `agent/insights.py` - 使用洞察
- `agent/redact.py` - 敏感信息编辑
- `agent/smart_model_routing.py` - 智能模型路由
- `agent/subdirectory_hints.py` - 子目录提示
- `agent/title_generator.py` - 对话标题生成
- `agent/builtin_memory_provider.py` - 内置记忆提供者
- `agent/memory_provider.py` - 记忆提供者接口
- `agent/skill_utils.py` - 技能工具函数
- `agent/models_dev.py` - models.dev 集成

### 测试文件
- `tests/agent/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 agent 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明核心类和函数
- 🔧 **接口文档**：记录主要对外接口
- 📖 **使用指南**：提供常见问题和调试技巧
- 🎯 **下一步**：需要补充详细的 API 文档和示例代码
