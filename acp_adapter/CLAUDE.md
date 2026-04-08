[根目录](../CLAUDE.md) > **acp_adapter**

# ACP Adapter 模块 - ACP 协议适配器

> 最后更新：2026-04-08 18:28:35

## 模块职责

`acp_adapter/` 模块实现 ACP（Agent Communication Protocol）协议适配器，使 Hermes Agent 能够集成到各种开发工具和 IDE 中，如 VS Code、Zed、JetBrains 等。

主要职责：
- **ACP 服务器**：实现 ACP 协议的服务器端
- **会话管理**：管理来自 IDE 的客户端会话
- **工具暴露**：将 Hermes 工具暴露为 ACP 工具
- **消息路由**：在 IDE 和 Hermes 之间路由消息
- **状态同步**：保持 IDE 和 Hermes 的状态同步

## 入口与启动

### 主要入口点
- **`acp_adapter/entry.py`**：`main()` 函数 - ACP 适配器入口
- **`acp_adapter/server.py`**：`ACPServer` 类 - ACP 服务器

### 启动流程
```
IDE 启动 ACP 客户端
  ↓
连接到 ACP 服务器 (acp_adapter/entry.py)
  ↓
初始化会话 (acp_adapter/session.py)
  ↓
注册工具 (acp_adapter/tools.py)
  ↓
开始消息循环
```

## 对外接口

### ACPServer 类 (server.py)

**主要方法**：
```python
class ACPServer:
    def __init__(self, host: str = "localhost", port: int = 8080):
        """初始化 ACP 服务器。"""

    async def start(self) -> None:
        """启动服务器。"""

    async def stop(self) -> None:
        """停止服务器。"""

    async def handle_client(self, reader, writer):
        """处理客户端连接。"""

    async def handle_message(self, message: dict) -> dict:
        """处理 ACP 消息。"""
```

### ACPSession 类 (session.py)

**主要方法**：
```python
class ACPSession:
    def __init__(self, session_id: str, client_info: dict):
        """初始化会话。"""

    async def send_message(self, message: dict) -> None:
        """发送消息到客户端。"""

    async def receive_message(self) -> dict:
        """接收来自客户端的消息。"""

    def get_state(self) -> dict:
        """获取会话状态。"""

    def update_state(self, state: dict) -> None:
        """更新会话状态。"""
```

### 工具暴露 (tools.py)

**主要函数**：
```python
def expose_hermes_tools() -> list[dict]:
    """将 Hermes 工具暴露为 ACP 工具。"""

def convert_tool_schema(hermes_tool: dict) -> dict:
    """转换 Hermes 工具 schema 为 ACP 格式。"""

def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """处理工具调用。"""
```

### ACP 消息格式

**请求消息**：
```python
{
    "id": str,              # 消息 ID
    "type": str,            # 消息类型
    "method": str,          # 方法名
    "params": dict,         # 参数
    "timestamp": str,       # 时间戳
}
```

**响应消息**：
```python
{
    "id": str,              # 消息 ID（匹配请求）
    "type": str,            # "response"
    "result": dict,         # 结果
    "error": dict,          # 错误（如果有）
    "timestamp": str,       # 时间戳
}
```

## 关键依赖与配置

### 依赖项
- **aiohttp**：异步 HTTP 服务器
- **websockets**：WebSocket 支持
- **pydantic**：数据验证

### 配置文件
- `~/.hermes/acp.yaml` - ACP 配置
- `~/.hermes/config.yaml` - 主配置文件
- `acp_registry/agent.json` - ACP 注册表

### 环境变量
- `HERMES_ACP_ENABLED` - 启用 ACP 适配器
- `HERMES_ACP_HOST` - ACP 服务器主机
- `HERMES_ACP_PORT` - ACP 服务器端口

## 数据模型

### ACP 工具格式
```python
{
    "name": str,
    "description": str,
    "parameters": {
        "type": "object",
        "properties": dict,
        "required": list[str],
    },
}
```

### 会话状态格式
```python
{
    "session_id": str,
    "client_info": dict,
    "connected_at": str,
    "last_activity": str,
    "state": dict,
}
```

## IDE 集成

### VS Code 集成
**配置**：
```json
{
    "acp.servers": [
        {
            "name": "hermes",
            "host": "localhost",
            "port": 8080,
        }
    ]
}
```

### Zed 集成
**配置**：
```json
{
    "lsp": {
        "hermes": {
            "command": "hermes-acp",
            "args": []
        }
    }
}
```

### JetBrains 集成
**配置**：
1. 安装 ACP 插件
2. 配置服务器：`localhost:8080`
3. 启用 Hermes 工具

## 测试与质量

### 测试文件
- `tests/acp/test_server.py` - ACP 服务器测试
- `tests/acp/test_session.py` - 会话管理测试
- `tests/acp/test_tools.py` - 工具暴露测试
- `tests/acp/test_protocol.py` - 协议测试

### 测试覆盖
- **单元测试**：每个模块都有对应的测试文件
- **集成测试**：测试与 IDE 的交互
- **约 8 个测试文件**覆盖核心功能

### 质量指标
- 高测试覆盖率（~75%+）
- 符合 ACP 协议标准
- 详细的日志记录
- 良好的错误处理

## 常见问题 (FAQ)

### Q: 如何在 IDE 中使用 Hermes？
A:
1. 启动 ACP 适配器：`hermes acp start`
2. 在 IDE 中配置 ACP 服务器
3. 刷新 IDE 工具面板
4. 开始使用 Hermes 工具

### Q: 如何暴露自定义工具？
A: 在 `acp_adapter/tools.py` 中添加工具定义，然后重启适配器。

### Q: 如何处理多个 IDE 会话？
A: ACP 适配器支持多个并发会话，每个 IDE 连接有独立的会话状态。

### Q: 如何调试 ACP 连接？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的 ACP 消息日志。

### Q: 如何支持新的 IDE？
A: 实现 IDE 的 ACP 客户端，连接到 Hermes ACP 服务器。

### Q: 如何限制工具访问？
A: 在 `acp_adapter/tools.py` 中过滤工具列表，只暴露允许的工具。

## 相关文件清单

### 核心文件
- `acp_adapter/__init__.py` - 模块初始化
- `acp_adapter/entry.py` - 适配器入口
- `acp_adapter/server.py` - ACP 服务器
- `acp_adapter/session.py` - 会话管理
- `acp_adapter/tools.py` - 工具暴露

### 协议实现
- `acp_adapter/protocol.py` - ACP 协议实现
- `acp_adapter/messages.py` - 消息定义
- `acp_adapter/validation.py` - 数据验证

### 注册表
- `acp_registry/agent.json` - ACP 注册表

### 辅助文件
- `acp_adapter/logging.py` - 日志配置
- `acp_adapter/metrics.py` - 指标收集

### 测试文件
- `tests/acp/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 acp_adapter 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明 ACP 协议和 IDE 集成
- 🔧 **接口文档**：记录主要对外接口
- 📖 **使用指南**：提供 IDE 集成和调试的步骤
- 🎯 **下一步**：需要补充详细的 ACP 协议规范文档
