# 架构决策记录（Architecture Decision Records）

本目录记录 Hermes Agent 项目的重要架构决策。

## ADR 索引

| ID | 标题 | 状态 | 日期 | 图表 |
|----|------|------|------|------|
| [ADR-001](./001-sync-agent-loop.md) | 同步代理循环 | ✅ 接受 | 2024-01-15 | ✅ |
| [ADR-002](./002-tool-registry.md) | 中央化工具注册表 | ✅ 接受 | 2024-01-20 | ✅ |
| [ADR-003](./003-multi-instance.md) | 多实例配置隔离 | ✅ 接受 | 2024-02-01 | ✅ |
| [ADR-004](./004-prompt-cache.md) | 提示缓存保护 | ✅ 接受 | 2024-02-10 | ✅ |
| [ADR-005](./005-plugin-memory.md) | 记忆提供者插件系统 | ✅ 接受 | 2024-03-01 | ✅ |
| [ADR-006](./006-command-system.md) | 命令系统设计 | ✅ 接受 | 2024-03-15 | ✅ |
| [ADR-007](./007-session-management.md) | 会话管理系统 | ✅ 接受 | 2024-03-20 | ✅ |
| [ADR-008](./008-skill-system.md) | 技能系统架构 | ✅ 接受 | 2024-04-01 | ✅ |

## ADR 模板

```markdown
# ADR-XXX: 决策标题

## 状态
[提案/接受/已弃用/已替代]

## 日期
YYYY-MM-DD

## 背景
[描述问题或决策背景]

## 决策
[描述做出的决策]

## 理由
[解释为什么做出这个决策]

## 后果
- **正面**：[好处]
- **负面**：[代价]

## 替代方案
- [替代方案 1]
- [替代方案 2]

## 相关决策
- [ADR-XXX]
```

## 变更日志

详细的 ADR 变更历史请参阅 [CHANGELOG.md](./CHANGELOG.md)。

## 参考

- 📋 [ADR 索引](./README.md)
- 📜 [ADR 变更日志](./CHANGELOG.md)
- 💬 [ADR 反馈表](./FEEDBACK.md)
- 🔗 [ADR 仓库](https://github.com/joelparkerhenderson/architecture-decision-record)
- 🔗 [ADR 规范](https://adr.github.io/)
