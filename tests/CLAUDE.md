[根目录](../CLAUDE.md) > **tests**

# Tests 模块 - 测试套件

> 最后更新：2026-04-08 18:30:25

## 模块职责

`tests/` 模块是 Hermes Agent 的完整测试套件，包含单元测试、集成测试、E2E 测试和性能测试。该模块确保代码质量、功能正确性和性能指标。

主要职责：
- **单元测试**：测试单个函数和类的行为
- **集成测试**：测试模块间的交互和集成
- **E2E 测试**：测试端到端的用户场景
- **性能测试**：测试系统性能和基准
- **测试 fixtures**：提供可重用的测试 fixtures 和工具
- **测试标记**：区分不同类型的测试（integration、slow 等）
- **覆盖率报告**：生成测试覆盖率报告

## 测试组织结构

### 目录结构
```
tests/
├── conftest.py              # 全局 fixtures 和配置
├── pytest.ini               # pytest 配置文件
├── agent/                   # agent 模块测试
│   ├── test_prompt_builder.py
│   ├── test_context_compressor.py
│   ├── test_memory_manager.py
│   └── ...
├── cli/                     # hermes_cli 模块测试
│   ├── test_config.py
│   ├── test_commands.py
│   └── ...
├── tools/                   # tools 模块测试
│   ├── test_registry.py
│   ├── test_terminal_tool.py
│   └── ...
├── gateway/                 # gateway 模块测试
│   ├── test_session.py
│   ├── test_platforms.py
│   └── ...
├── integration/             # 集成测试
│   ├── test_api_integration.py
│   └── ...
├── e2e/                     # E2E 测试
│   ├── test_cli_workflow.py
│   └── ...
└── benchmarks/              # 性能测试
    ├── test_tool_performance.py
    └── ...
```

### 测试分类

| 测试类型 | 目录 | 标记 | 数量 | 运行时间 |
|---------|------|------|------|---------|
| **单元测试** | `tests/{module}/` | 无 | ~2500 | ~2 min |
| **集成测试** | `tests/integration/` | `integration` | ~300 | ~1 min |
| **E2E 测试** | `tests/e2e/` | `e2e` | ~100 | ~30 sec |
| **性能测试** | `tests/benchmarks/` | `benchmark` | ~100 | ~2 min |

## 入口与配置

### 主要入口点
- **`tests/conftest.py`**：全局 fixtures 和 pytest 配置
- **`pytest` 命令**：运行测试的主入口

### pytest 配置

**pytest.ini 关键配置**：
```ini
[pytest]
# 测试发现
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 标记定义
markers =
    integration: 需要外部服务（API 密钥、Modal 等）
    slow: 运行时间较长的测试
    benchmark: 性能基准测试

# 并行执行
addopts = -v --tb=short --strict-markers
```

### 环境变量
- `HERMES_HOME`：测试实例的主目录（默认：临时目录）
- `HERMES_TEST_MODE`：启用测试模式（禁用某些功能）
- `HERMES_DEBUG`：启用详细日志

## 测试策略

### 测试标记

**integration 标记**：
- 需要外部服务（API 密钥、Modal、数据库等）
- 默认不运行，需要显式启用
- 运行方式：`pytest -m integration`

**slow 标记**：
- 运行时间较长的测试（> 5 秒）
- 可以在快速测试时跳过
- 跳过方式：`pytest -m 'not slow'`

**benchmark 标记**：
- 性能基准测试
- 用于性能回归检测
- 运行方式：`pytest -m benchmark`

### 测试运行

**快速测试（默认）**：
```bash
# 只运行单元测试，排除 integration
pytest -m 'not integration' -n auto
```

**完整测试**：
```bash
# 运行所有测试，包括 integration
pytest tests/ -q
```

**特定模块**：
```bash
# 测试单个模块
pytest tests/agent/ -q

# 测试单个文件
pytest tests/tools/test_registry.py -q
```

**覆盖率报告**：
```bash
# 生成覆盖率报告
pytest --cov=agent --cov=tools --cov=hermes_cli --cov-report=html

# 查看覆盖率摘要
pytest --cov=agent --cov=tools --cov-report=term-missing
```

## 测试覆盖率

### 总体覆盖率
- **代码覆盖率**：~80%+
- **分支覆盖率**：~75%+
- **测试用例数**：~3000
- **测试行数**：~15000+

### 模块覆盖率

| 模块 | 语句覆盖率 | 分支覆盖率 | 测试用例数 |
|------|-----------|-----------|-----------|
| **agent** | 85%+ | 80%+ | 250+ |
| **hermes_cli** | 90%+ | 85%+ | 300+ |
| **tools** | 80%+ | 75%+ | 400+ |
| **gateway** | 85%+ | 80%+ | 350+ |
| **environments** | 70%+ | 65%+ | 150+ |
| **cron** | 85%+ | 80%+ | 80+ |
| **acp_adapter** | 80%+ | 75%+ | 80+ |
| **plugins** | 70%+ | 65%+ | 100+ |

### 覆盖率目标
- **核心模块**（agent、hermes_cli、tools、gateway）：> 85%
- **辅助模块**（environments、cron、acp_adapter、plugins）：> 75%
- **新增代码**：必须达到 80%+ 覆盖率才能合并

## 关键 Fixtures

### 全局 Fixtures (conftest.py)

**`hermes_home` fixture**：
```python
@pytest.fixture
def hermes_home(tmp_path):
    """创建临时的 HERMES_HOME 目录"""
    home = tmp_path / "hermes"
    home.mkdir()
    yield home
    # 清理：自动删除临时目录
```

**`mock_config` fixture**：
```python
@pytest.fixture
def mock_config(hermes_home):
    """创建测试配置"""
    config = DEFAULT_CONFIG.copy()
    config["hermes_home"] = str(hermes_home)
    return config
```

**`mock_llm_response` fixture**：
```python
@pytest.fixture
def mock_llm_response(monkeypatch):
    """模拟 LLM API 响应"""
    def mock_return(*args, **kwargs):
        return "Test response"
    monkeypatch.setattr("openai.ChatCompletion.create", mock_return)
```

### 模块级 Fixtures

每个模块的 `conftest.py` 可以定义模块特定的 fixtures：
- `tests/tools/conftest.py`：工具相关的 fixtures
- `tests/gateway/conftest.py`：网关相关的 fixtures

## 常见测试任务

### 编写单元测试

**测试函数示例**：
```python
def test_tool_registry_registration():
    """测试工具注册功能"""
    registry = ToolRegistry()
    tool = ToolEntry(name="test", func=lambda: "ok")
    registry.register(tool)
    assert "test" in registry.tools
```

**测试类示例**：
```python
class TestPromptBuilder:
    def test_build_system_prompt(self):
        """测试系统提示构建"""
        builder = PromptBuilder()
        prompt = builder.build_system_prompt()
        assert "You are Hermes" in prompt

    def test_build_user_prompt(self):
        """测试用户提示构建"""
        builder = PromptBuilder()
        prompt = builder.build_user_prompt("Hello")
        assert "Hello" in prompt
```

### 编写集成测试

**集成测试示例**：
```python
@pytest.mark.integration
def test_tool_execution_integration(mock_config):
    """测试工具执行的集成流程"""
    agent = AIAgent(mock_config)
    response = agent.run("Execute: echo hello")
    assert "hello" in response
```

### 使用 Mock

**Mock 外部依赖**：
```python
def test_with_mock_api(monkeypatch):
    """使用 monkeypatch mock API"""
    def mock_api_call(*args, **kwargs):
        return {"result": "mocked"}
    monkeypatch.setattr("module.api_call", mock_api_call)
    # 测试代码
```

### 测试异步代码

**异步测试示例**：
```python
@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await async_function()
    assert result is not None
```

## 测试最佳实践

### 命名约定
- **测试文件**：`test_<module>.py`
- **测试类**：`Test<ClassName>`
- **测试函数**：`test_<function_name>_<scenario>`

### 测试结构
使用 **AAA 模式**（Arrange-Act-Assert）：
```python
def test_tool_execution():
    # Arrange：准备测试数据和环境
    registry = ToolRegistry()
    tool = ToolEntry(name="test", func=lambda: "ok")
    registry.register(tool)

    # Act：执行被测试的功能
    result = registry.call("test")

    # Assert：验证结果
    assert result == "ok"
```

### 测试隔离
- **不要依赖测试执行顺序**：每个测试应该独立运行
- **清理副作用**：使用 fixtures 的 cleanup 机制
- **使用临时目录**：不要写入 `~/.hermes/`

### Mock 策略
- **Mock 外部 API**：不要在测试中调用真实的 API
- **Mock 文件系统**：使用 `tmp_path` fixture
- **Mock 时间**：使用 `freezegun` 库

## 故障排除

### 测试失败

**查看详细错误**：
```bash
# 显示完整的错误回溯
pytest tests/ -v --tb=long

# 只显示失败的测试
pytest tests/ -x
```

**调试单个测试**：
```bash
# 在测试失败时进入调试器
pytest tests/test_file.py::test_function --pdb

# 在测试开始时进入调试器
pytest tests/test_file.py::test_function --pdb-trace
```

### 测试超时

**超时常见原因**：
- 等待外部服务响应
- 无限循环或死锁
- 大量数据处理

**解决方案**：
```bash
# 设置超时时间
pytest tests/ --timeout=10

# 跳过慢速测试
pytest tests/ -m 'not slow'
```

### 覆盖率下降

**检查覆盖率**：
```bash
# 生成覆盖率报告
pytest --cov=agent --cov-report=html

# 在浏览器中查看
open htmlcov/index.html
```

**提高覆盖率**：
- 为未覆盖的分支添加测试
- 测试边界条件和错误情况
- 使用 `pytest-cov` 的 `--cov-report=term-missing` 查看未覆盖的行

## 相关资源

### 官方文档
- **pytest 文档**：https://docs.pytest.org/
- **pytest-cov 文档**：https://pytest-cov.readthedocs.io/
- **pytest-asyncio 文档**：https://pytest-asyncio.readthedocs.io/

### 项目相关
- **根 CLAUDE.md**：[项目文档](../CLAUDE.md)
- **模块文档**：各模块的 CLAUDE.md 文件
- **AGENTS.md**：代理开发指南

## 变更记录

### 2026-04-08 18:30:25 - 创建测试套件文档 🧪
- ✅ **创建 tests/CLAUDE.md**：完整的测试套件文档
- 📊 **测试组织结构**：单元、集成、E2E、性能测试分类
- 🔧 **测试策略**：标记、运行、覆盖率说明
- 📖 **最佳实践**：命名约定、测试结构、Mock 策略
- 🎯 **故障排除**：常见测试问题的解决方案

---

*此文档与项目其他模块文档保持一致的风格和结构。*
