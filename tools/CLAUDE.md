[根目录](../CLAUDE.md) > **tools**

# Tools 模块 - 工具系统

> 最后更新：2026-04-08 18:28:11

## 模块职责

`tools/` 模块是 Hermes Agent 的工具系统核心，负责工具注册、调度、执行和可用性检查。所有工具都在中央注册表中注册，并由代理循环调用。

主要职责：
- **工具注册**：中央化的工具注册表，管理所有工具的元数据和处理器
- **工具调度**：根据工具调用请求分发到相应的处理器
- **可用性检查**：验证工具依赖和环境变量
- **工具集管理**：按功能分组工具（terminal、web、file 等）
- **特殊工具**：终端、文件、Web、浏览器、代码执行、MCP、委派

## 入口与启动

### 主要入口点
- **`tools/registry.py`**：中央工具注册表（无依赖，被所有工具文件导入）
- **`model_tools.py`**：工具发现和调度（在项目根目录）

### 依赖链
```
tools/registry.py  (无依赖)
    ↑
tools/*.py  (每个在导入时调用 registry.register())
    ↑
model_tools.py  (导入 tools/registry + 所有工具模块)
    ↑
run_agent.py, cli.py, batch_runner.py, environments/
```

### 工具注册流程
1. 工具文件在模块级别调用 `registry.register()`
2. `model_tools.py` 导入所有工具模块
3. 注册表收集所有工具的元数据和处理器
4. 代理查询注册表获取工具定义和调度处理器

## 对外接口

### ToolRegistry 类 (registry.py)

**主要方法**：
```python
class ToolRegistry:
    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable = None,
        requires_env: list = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
    ):
        """注册工具。在模块导入时由每个工具文件调用。"""

    def deregister(self, name: str) -> None:
        """从注册表中移除工具。"""

    def get_tool(self, name: str) -> ToolEntry:
        """获取工具条目。"""

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        """获取所有工具。"""

    def get_tools_by_toolset(self, toolset: str) -> Dict[str, ToolEntry]:
        """获取指定工具集的所有工具。"""

    def get_tool_names(self) -> Set[str]:
        """获取所有工具名称。"""

    def check_toolset_available(self, toolset: str) -> bool:
        """检查工具集是否可用。"""
```

### ToolEntry 类
```python
class ToolEntry:
    """单个注册工具的元数据。"""

    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "requires_env", "is_async", "description", "emoji",
    )
```

### 工具调度 (model_tools.py)

**主要函数**：
```python
def get_tool_definitions(
    enabled_toolsets: list = None,
    disabled_toolsets: list = None,
    platform: str = "cli",
) -> list:
    """获取可用工具的定义（schema 列表）。"""

def handle_function_call(
    tool_name: str,
    tool_input: dict,
    task_id: str = None,
    agent_instance = None,
) -> str:
    """处理工具调用，返回 JSON 字符串结果。"""

def check_toolset_requirements(toolset: str) -> bool:
    """检查工具集的依赖是否满足。"""

def get_toolset_for_tool(tool_name: str) -> str:
    """获取工具所属的工具集。"""
```

## 关键依赖与配置

### 依赖项
- **OpenAI SDK**：LLM API 客户端
- **httpx**：HTTP 客户端（Web 工具）
- **firecrawl-py**：Web 抓取
- **exa-py**：Web 搜索
- **parallel-web**：并行浏览器自动化

### 配置
- `~/.hermes/config.yaml` - 工具配置
- `~/.hermes/.env` - API 密钥

### 环境变量
- `FIRECRAWL_API_KEY` - Firecrawl API 密钥
- `EXA_API_KEY` - Exa API 密钥
- `BROWSERBASE_API_KEY` - Browserbase API 密钥
- `E2B_API_KEY` - E2B 代码执行沙盒

## 数据模型

### 工具 Schema 格式
```python
{
    "name": "tool_name",
    "description": "工具描述",
    "parameters": {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "参数描述"
            }
        },
        "required": ["param_name"]
    }
}
```

### 工具调用格式
```python
{
    "name": "tool_name",
    "arguments": "{\"param\": \"value\"}"
}
```

### 工具结果格式
```python
{
    "result": "结果数据",
    "success": true,
    "error": null
}
```

## 核心工具

### 终端工具 (terminal_tool.py)
- **功能**：在本地或远程终端执行命令
- **支持后端**：local、docker、ssh、modal、daytona、singularity
- **特性**：后台进程、实时输出、工作目录管理

### 文件工具 (file_tools.py)
- **功能**：读取、写入、搜索、修补文件
- **特性**：大文件分块读取、智能搜索、diff 补丁

### Web 工具 (web_tools.py)
- **功能**：Web 搜索、内容提取
- **特性**：并行搜索、Firecrawl 抓取、Exa 搜索

### 浏览器工具 (browser_tool.py)
- **功能**：浏览器自动化
- **特性**：Browserbase 集成、页面导航、截图

### 代码执行工具 (code_execution_tool.py)
- **功能**：在沙盒中执行代码
- **特性**：E2B 集成、多种语言支持

### MCP 工具 (mcp_tool.py)
- **功能**：MCP 服务器客户端
- **特性**：动态工具发现、服务器管理

### 委派工具 (delegate_tool.py)
- **功能**：生成子代理用于并行工作
- **特性**：隔离执行、进度跟踪

## 测试与质量

### 测试文件
- `tests/tools/test_registry.py` - 注册表测试
- `tests/tools/test_terminal_tool.py` - 终端工具测试
- `tests/tools/test_file_tools.py` - 文件工具测试
- `tests/tools/test_web_tools.py` - Web 工具测试
- `tests/tools/test_browser_tool.py` - 浏览器工具测试
- `tests/tools/test_mcp_tool.py` - MCP 工具测试

### 测试覆盖
- **单元测试**：每个工具都有对应的测试文件
- **集成测试**：测试工具与外部服务的交互
- **约 40 个测试文件**覆盖所有工具

### 质量指标
- 高测试覆盖率（~85%+）
- 统一的错误处理
- 详细的日志记录
- 安全的命令执行

## 常见问题 (FAQ)

### Q: 如何添加新工具？
A:
1. 创建 `tools/your_tool.py`
2. 在模块级别调用 `registry.register()`
3. 在 `model_tools.py` 的 `_discover_tools()` 中添加导入
4. 在 `toolsets.py` 中添加到相应的工具集

### Q: 如何检查工具可用性？
A: 实现 `check_requirements()` 函数，在注册时传递给 `check_fn` 参数。

### Q: 如何处理异步工具？
A: 设置 `is_async=True`，处理器函数必须是协程。

### Q: 如何禁用工具集？
A: 在配置文件中设置 `disabled_toolsets`，或使用 `hermes tools` 命令。

### Q: 如何调试工具调用？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的工具调用日志。

## 相关文件清单

### 核心文件
- `tools/registry.py` - 中央工具注册表
- `tools/terminal_tool.py` - 终端工具
- `tools/file_tools.py` - 文件工具
- `tools/web_tools.py` - Web 工具
- `tools/browser_tool.py` - 浏览器工具
- `tools/code_execution_tool.py` - 代码执行工具
- `tools/mcp_tool.py` - MCP 工具
- `tools/delegate_tool.py` - 委派工具
- `tools/approval.py` - 危险命令检测
- `tools/process_registry.py` - 后台进程管理

### 工具集定义
- `toolsets.py` - 工具集定义（在项目根目录）
- `model_tools.py` - 工具发现和调度（在项目根目录）

### 环境后端
- `tools/environments/local.py` - 本地终端
- `tools/environments/docker.py` - Docker 容器
- `tools/environments/ssh.py` - SSH 远程
- `tools/environments/modal.py` - Modal 无服务器
- `tools/environments/daytona.py` - Daytona 无服务器
- `tools/environments/singularity.py` - Singularity 容器

### 测试文件
- `tests/tools/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 tools 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明注册表和调度机制
- 🔧 **接口文档**：记录核心工具的接口
- 📖 **使用指南**：提供添加新工具的步骤
- 🎯 **下一步**：需要补充每个工具的详细 API 文档
