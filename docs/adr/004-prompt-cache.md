# ADR-004: 提示缓存保护

## 状态
✅ 接受

## 日期
2024-02-10

## 背景

AI 模型的 API 调用（特别是 OpenAI 和 Anthropic）依赖提示缓存来提高性能和降低成本。如果提示格式在对话过程中发生变化，缓存会失效，导致性能下降和成本增加。

**问题**：
- 如何确保提示缓存在整个对话过程中有效？
- 如何避免意外的提示格式变化？
- 如何在添加新功能时不破坏缓存？

## 决策

**将提示缓存保护作为核心设计原则**。整个对话过程中保持提示格式的一致性，任何可能影响缓存的更改都需要严格审查。

## 理由

1. **性能优化**：缓存可以减少 API 响应时间
2. **成本控制**：缓存显著降低 API 调用成本（特别是长对话）
3. **用户体验**：缓存使响应更快，用户体验更好

## 后果

**正面**：
- 显著降低 API 成本（可达 50-90%）
- 提高响应速度
- 优化长对话体验

**负面**：
- 限制了提示格式的灵活性
- 需要额外的开发注意事项
- 调试更困难（不能随意修改提示）

## 实现指南

### ✅ 允许的操作

```python
# ✅ 在系统提示后追加内容
system_prompt = "You are Hermes..."
system_prompt += f"\n\nSkills: {skill_index}"

# ✅ 保持对话顺序一致
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_message},
    {"role": "assistant", "content": assistant_response},
    # ... 继续追加
]

# ✅ 使用稳定的工具描述
tool_schema = {
    "name": "terminal",
    "description": "Execute terminal commands",  # 保持不变
    "parameters": {...}
}
```

### ❌ 禁止的操作

```python
# ❌ 在对话中间插入系统消息
messages = [
    {"role": "user", "content": "..."},
    {"role": "system", "content": "..."},  # 破坏缓存！
    {"role": "assistant", "content": "..."}
]

# ❌ 修改工具描述格式
tool_schema = {
    "name": "terminal",
    "description": f"Execute commands on {platform}",  # 动态内容破坏缓存！
}

# ❌ 在对话过程中重新排序消息
messages.sort(key=lambda x: x["timestamp"])  # 破坏缓存！
```

## 检查清单

在提交任何影响提示的代码更改前，确认：

- [ ] 不会在对话中间插入系统消息
- [ ] 不会修改工具的名称或描述
- [ ] 不会重新排序对话消息
- [ ] 不会在对话过程中更改提示模板
- [ ] 不会动态生成工具模式描述

## 替代方案

- **不使用缓存**：接受更高的成本和延迟（不推荐）
- **部分缓存**：只缓存系统提示（但仍需小心）

## 相关决策

- [ADR-001: 同步代理循环](./001-sync-agent-loop.md)
- [ADR-002: 中央化工具注册表](./002-tool-registry.md)
