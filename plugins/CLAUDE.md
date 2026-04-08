[根目录](../CLAUDE.md) > **plugins**

# Plugins 模块 - 插件系统

> 最后更新：2026-04-08 18:28:35

## 模块职责

`plugins/` 模块提供插件系统，允许扩展 Hermes Agent 的功能，特别是记忆提供者插件。该模块支持多种记忆后端，包括内置记忆、Honcho、Mem0、Holographic 等。

主要职责：
- **插件管理**：发现、加载、管理插件
- **记忆提供者**：统一的记忆提供者接口
- **插件开发**：插件开发指南和工具
- **配置管理**：插件配置和持久化
- **扩展性**：支持自定义插件

## 入口与启动

### 主要入口点
- **`plugins/__init__.py`**：插件管理器
- **`plugins/memory/`**：记忆提供者插件目录

### 使用示例
```python
from plugins import load_plugin

# 加载记忆提供者插件
memory_provider = load_plugin("memory", "honcho")

# 使用记忆提供者
context = memory_provider.build_memory_context(user_id="user123")
```

## 对外接口

### PluginManager 类

**主要方法**：
```python
class PluginManager:
    def __init__(self, hermes_home: Path = None):
        """初始化插件管理器。"""

    def discover_plugins(self) -> list[Plugin]:
        """发现所有插件。"""

    def load_plugin(self, plugin_type: str, plugin_name: str) -> Plugin:
        """加载插件。"""

    def unload_plugin(self, plugin_name: str) -> None:
        """卸载插件。"""

    def list_plugins(self, plugin_type: str = None) -> list[Plugin]:
        """列出插件。"""

    def get_plugin(self, plugin_name: str) -> Plugin:
        """获取插件。"""
```

### MemoryProvider 接口

**主要方法**：
```python
class MemoryProvider(ABC):
    @abstractmethod
    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        """构建记忆上下文。"""

    @abstractmethod
    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        """添加记忆。"""

    @abstractmethod
    def search_memories(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        """搜索记忆。"""

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆。"""
```

### 内置记忆提供者 (plugins/memory/builtin/)

**BuiltinMemoryProvider 类**：
```python
class BuiltinMemoryProvider(MemoryProvider):
    def __init__(self, hermes_home: Path = None):
        """初始化内置记忆提供者。"""

    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        """从本地 SQLite 数据库构建记忆上下文。"""

    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        """添加记忆到本地数据库。"""

    def search_memories(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        """使用 FTS5 搜索记忆。"""
```

### Honcho 记忆提供者 (plugins/memory/honcho/)

**HonchoMemoryProvider 类**：
```python
class HonchoMemoryProvider(MemoryProvider):
    def __init__(self, api_key: str = None):
        """初始化 Honcho 记忆提供者。"""

    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        """从 Honcho API 构建记忆上下文。"""

    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        """添加记忆到 Honcho。"""
```

### Mem0 记忆提供者 (plugins/memory/mem0/)

**Mem0MemoryProvider 类**：
```python
class Mem0MemoryProvider(MemoryProvider):
    def __init__(self, api_key: str = None):
        """初始化 Mem0 记忆提供者。"""

    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        """从 Mem0 API 构建记忆上下文。"""

    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        """添加记忆到 Mem0。"""
```

### Holographic 记忆提供者 (plugins/memory/holographic/)

**HolographicMemoryProvider 类**：
```python
class HolographicMemoryProvider(MemoryProvider):
    def __init__(self, config: dict = None):
        """初始化 Holographic 记忆提供者。"""

    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        """从 Holographic 向量数据库构建记忆上下文。"""

    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        """添加记忆到 Holographic。"""
```

## 关键依赖与配置

### 依赖项
- **honcho**（可选）：Honcho 记忆服务
- **mem0ai**（可选）：Mem0 记忆服务
- **chromadb**（可选）：Holographic 向量数据库
- **sqlite3**：内置记忆存储

### 配置文件
- `~/.hermes/config.yaml` - 主配置文件
- `~/.hermes/plugins.yaml` - 插件配置

### 环境变量
- `HERMES_MEMORY_PROVIDER` - 默认记忆提供者
- `HONCHO_API_KEY` - Honcho API 密钥
- `MEM0_API_KEY` - Mem0 API 密钥
- `HOLOGRAPHIC_API_KEY` - Holographic API 密钥

## 数据模型

### 插件配置格式
```yaml
plugins:
  memory:
    provider: "builtin"  # "builtin", "honcho", "mem0", "holographic"
    config:
      honcho:
        api_key: "YOUR_API_KEY"
      mem0:
        api_key: "YOUR_API_KEY"
      holographic:
        api_key: "YOUR_API_KEY"
        collection: "hermes_memories"
```

### 记忆格式
```python
{
    "memory_id": str,
    "user_id": str,
    "content": str,
    "metadata": dict,
    "created_at": str,
    "updated_at": str,
}
```

### 记忆上下文格式
```python
{
    "user_id": str,
    "memories": list[dict],
    "total_count": int,
    "context": str,  # 格式化的上下文字符串
}
```

## 插件开发

### 创建自定义记忆提供者

1. **创建插件目录**：
```bash
mkdir -p plugins/memory/my_provider
```

2. **实现 MemoryProvider 接口**：
```python
# plugins/memory/my_provider/__init__.py
from plugins.memory import MemoryProvider

class MyMemoryProvider(MemoryProvider):
    def build_memory_context(self, user_id: str, limit: int = 10) -> str:
        # 实现记忆上下文构建
        pass

    def add_memory(self, user_id: str, content: str, metadata: dict = None) -> str:
        # 实现记忆添加
        pass

    def search_memories(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        # 实现记忆搜索
        pass

    def delete_memory(self, memory_id: str) -> bool:
        # 实现记忆删除
        pass
```

3. **注册插件**：
```python
# plugins/memory/my_provider/plugin.py
from plugins import Plugin

plugin = Plugin(
    name="my_provider",
    type="memory",
    version="1.0.0",
    description="My custom memory provider",
    class_name="MyMemoryProvider",
    module="plugins.memory.my_provider",
)
```

4. **配置插件**：
```yaml
# ~/.hermes/plugins.yaml
plugins:
  memory:
    provider: "my_provider"
    config:
      my_provider:
        # 自定义配置
```

## 测试与质量

### 测试文件
- `tests/plugins/test_plugin_manager.py` - 插件管理器测试
- `tests/plugins/test_builtin_memory.py` - 内置记忆测试
- `tests/plugins/test_honcho_memory.py` - Honcho 记忆测试
- `tests/plugins/test_mem0_memory.py` - Mem0 记忆测试
- `tests/plugins/test_holographic_memory.py` - Holographic 记忆测试

### 测试覆盖
- **单元测试**：每个插件都有对应的测试文件
- **集成测试**：测试与记忆服务的交互
- **约 10 个测试文件**覆盖核心功能

### 质量指标
- 高测试覆盖率（~70%+）
- 统一的插件接口
- 详细的文档字符串
- 良好的错误处理

## 常见问题 (FAQ)

### Q: 如何切换记忆提供者？
A: 在 `~/.hermes/config.yaml` 中设置 `memory.provider` 为所需的提供者。

### Q: 如何添加新的记忆提供者？
A: 实现 `MemoryProvider` 接口，并在插件目录中注册。

### Q: 如何调试插件问题？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的插件日志。

### Q: 如何备份记忆数据？
A: 使用 `hermes memory export` 命令导出记忆数据。

### Q: 如何迁移记忆数据？
A: 使用 `hermes memory migrate` 命令在不同提供者之间迁移。

### Q: 如何禁用插件？
A: 在 `~/.hermes/plugins.yaml` 中设置 `enabled: false`。

## 相关文件清单

### 核心文件
- `plugins/__init__.py` - 插件管理器
- `plugins/base.py` - 插件基类
- `plugins/registry.py` - 插件注册表

### 记忆提供者
- `plugins/memory/__init__.py` - 记忆提供者接口
- `plugins/memory/builtin/__init__.py` - 内置记忆
- `plugins/memory/honcho/__init__.py` - Honcho 记忆
- `plugins/memory/mem0/__init__.py` - Mem0 记忆
- `plugins/memory/holographic/__init__.py` - Holographic 记忆

### 辅助文件
- `plugins/config.py` - 插件配置
- `plugins/utils.py` - 插件工具函数
- `plugins/exceptions.py` - 插件异常

### 测试文件
- `tests/plugins/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 plugins 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明插件系统和记忆提供者
- 🔧 **接口文档**：记录主要对外接口
- 📖 **使用指南**：提供插件开发和配置的步骤
- 🎯 **下一步**：需要补充详细的插件开发指南和最佳实践
