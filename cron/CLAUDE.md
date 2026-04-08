[根目录](../CLAUDE.md) > **cron**

# Cron 模块 - 定时任务调度器

> 最后更新：2026-04-08 18:28:35

## 模块职责

`cron/` 模块提供定时任务调度功能，允许用户安排 Hermes Agent 在特定时间执行任务。该模块集成了标准的 cron 语法，支持向任何消息平台传递定时任务。

主要职责：
- **调度器**：管理定时任务的执行
- **作业定义**：定义和管理定时作业
- **持久化**：保存和加载作业配置
- **通知**：在指定平台发送任务结果
- **时区支持**：处理不同时区的调度

## 入口与启动

### 主要入口点
- **`cron/scheduler.py`**：`CronScheduler` 类 - 调度器
- **`cron/jobs.py`**：作业定义和注册

### 使用示例
```python
from cron.scheduler import CronScheduler
from cron.jobs import CronJob

# 创建调度器
scheduler = CronScheduler()

# 定义作业
job = CronJob(
    name="daily_summary",
    cron_expr="0 9 * * *",  # 每天 9:00
    command="/summary",
    platform="telegram",
    channel_id="MY_CHANNEL_ID",
)

# 添加作业
scheduler.add_job(job)

# 启动调度器
scheduler.start()
```

## 对外接口

### CronScheduler 类 (scheduler.py)

**主要方法**：
```python
class CronScheduler:
    def __init__(self, hermes_home: Path = None):
        """初始化调度器。"""

    def start(self) -> None:
        """启动调度器。"""

    def stop(self) -> None:
        """停止调度器。"""

    def add_job(self, job: CronJob) -> None:
        """添加定时作业。"""

    def remove_job(self, job_name: str) -> None:
        """移除定时作业。"""

    def list_jobs(self) -> list[CronJob]:
        """列出所有作业。"""

    def get_job(self, job_name: str) -> CronJob:
        """获取作业。"""

    def load_jobs(self) -> None:
        """从文件加载作业。"""

    def save_jobs(self) -> None:
        """保存作业到文件。"""
```

### CronJob 类 (jobs.py)

**主要属性和方法**：
```python
@dataclass
class CronJob:
    name: str                          # 作业名称
    cron_expr: str                     # Cron 表达式
    command: str                       # 要执行的命令
    platform: str                      # 目标平台
    channel_id: str                    # 目标频道
    enabled: bool = True               # 是否启用
    timezone: str = "UTC"              # 时区
    last_run: str = None               # 最后运行时间
    next_run: str = None               # 下次运行时间

    def should_run(self, now: datetime) -> bool:
        """检查是否应该运行。"""

    def to_dict(self) -> dict:
        """转换为字典。"""

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        """从字典创建。"""
```

### 作业注册表 (jobs.py)

**预定义作业**：
```python
BUILTIN_JOBS = [
    CronJob(
        name="daily_summary",
        cron_expr="0 9 * * *",
        command="/summary",
        platform="telegram",
        channel_id="DEFAULT",
    ),
    CronJob(
        name="weekly_review",
        cron_expr="0 10 * * 0",
        command="/review",
        platform="discord",
        channel_id="DEFAULT",
    ),
]
```

## 关键依赖与配置

### 依赖项
- **croniter**：Cron 表达式解析
- **pytz**：时区处理
- **apscheduler**（可选）：高级调度功能

### 配置文件
- `~/.hermes/cron.yaml` - Cron 作业配置
- `~/.hermes/config.yaml` - 主配置文件

### 环境变量
- `HERMES_CRON_ENABLED` - 启用 cron 调度器
- `HERMES_CRON_TIMEZONE` - 默认时区

## 数据模型

### Cron 表达式格式
```
分钟 小时 日 月 星期
*    *    *  *   *
```

**示例**：
- `0 9 * * *` - 每天 9:00
- `0 */2 * * *` - 每 2 小时
- `0 9 * * 1-5` - 周一到周五 9:00
- `0 0 1 * *` - 每月 1 日 0:00

### 作业配置格式
```yaml
cron:
  enabled: true
  timezone: "UTC"
  jobs:
    - name: "daily_summary"
      cron_expr: "0 9 * * *"
      command: "/summary"
      platform: "telegram"
      channel_id: "MY_CHANNEL_ID"
      enabled: true

    - name: "weekly_review"
      cron_expr: "0 10 * * 0"
      command: "/review"
      platform: "discord"
      channel_id: "MY_CHANNEL_ID"
      enabled: true
```

### 作业执行记录格式
```python
{
    "job_name": str,
    "run_time": str,
    "status": str,  # "success", "failed"
    "result": str,
    "error": str,
}
```

## 测试与质量

### 测试文件
- `tests/cron/test_scheduler.py` - 调度器测试
- `tests/cron/test_jobs.py` - 作业测试
- `tests/cron/test_cron_expr.py` - Cron 表达式测试

### 测试覆盖
- **单元测试**：每个模块都有对应的测试文件
- **集成测试**：测试与网关的交互
- **约 8 个测试文件**覆盖核心功能

### 质量指标
- 高测试覆盖率（~80%+）
- 准确的 cron 解析
- 详细的日志记录
- 良好的错误处理

## 常见问题 (FAQ)

### Q: 如何添加新的定时作业？
A:
1. 在 `~/.hermes/cron.yaml` 中定义作业
2. 使用 `hermes cron add` 命令添加
3. 或直接在代码中创建 `CronJob` 并添加到调度器

### Q: 如何处理时区？
A: 在作业定义中指定 `timezone` 参数，调度器会自动处理时区转换。

### Q: 如何查看作业执行历史？
A: 使用 `hermes cron history <job_name>` 命令查看。

### Q: 如何禁用作业？
A: 在作业定义中设置 `enabled: false`，或使用 `hermes cron disable <job_name>`。

### Q: 如何调试调度问题？
A: 设置 `HERMES_DEBUG=1` 环境变量，查看详细的调度日志。

### Q: 如何支持秒级调度？
A: 使用 6 段 cron 表达式（秒 分 时 日 月 星期）。

## 相关文件清单

### 核心文件
- `cron/__init__.py` - 模块初始化
- `cron/scheduler.py` - 调度器
- `cron/jobs.py` - 作业定义
- `cron/config.py` - 配置加载

### 辅助文件
- `cron/parser.py` - Cron 表达式解析器
- `cron/executor.py` - 作业执行器
- `cron/notifier.py` - 通知发送器
- `cron/persistence.py` - 持久化

### 命令行工具
- `cron/cli.py` - Cron 命令行接口

### 测试文件
- `tests/cron/` - 完整的测试套件

## 变更记录 (Changelog)

### 2026-04-08 - 初始化模块文档 🚀
- ✅ **创建模块文档**：生成 cron 模块的完整 CLAUDE.md
- 📊 **架构分析**：详细说明调度器和作业管理
- 🔧 **接口文档**：记录主要对外接口
- 📖 **使用指南**：提供添加作业和调试的步骤
- 🎯 **下一步**：需要补充详细的高级调度功能文档
