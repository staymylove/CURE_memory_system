# Simple Agent Harness

一个最小化的agent运行框架和memory系统，只包含核心功能。

## 核心组件

1. **Message**: 消息格式定义
2. **MemorySystem**: 会话存储、恢复、压缩
3. **AgentHarness**: 运行循环、工具调用
4. **Tools**: 工具注册和执行

## 功能特性

- ✅ JSON格式存储会话
- ✅ 会话恢复（resume）
- ✅ 简单的消息压缩（compaction）
- ✅ 工具调用支持
- ✅ 流式输出
- ✅ 错误处理

## 快速开始

```python
from harness import AgentHarness
from tools import register_tool

# 注册工具
@register_tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

# 创建harness
harness = AgentHarness(
    model_name="your-model",
    session_dir="./sessions"
)

# 运行
harness.run("帮我计算 123 * 456")

# 恢复之前的会话
harness.resume("session_20250604_123456")
harness.run("继续上次的对话")
```

## 目录结构

```
simple_agent_harness/
├── README.md
├── harness.py          # 主运行框架
├── memory.py           # 内存管理
├── tools.py            # 工具系统
├── compaction.py       # 压缩策略
├── example.py          # 使用示例
└── sessions/           # 会话存储目录
```
