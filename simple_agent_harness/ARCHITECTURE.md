"""
架构文档 - Simple Agent Harness

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    AgentHarness                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Run Loop (主循环)                                │  │
│  │  1. 接收用户输入                                   │  │
│  │  2. 检查是否需要压缩                               │  │
│  │  3. 调用模型                                       │  │
│  │  4. 解析工具调用                                   │  │
│  │  5. 执行工具                                       │  │
│  │  6. 重复直到完成                                   │  │
│  └──────────────────────────────────────────────────┘  │
│          │              │              │                │
│          ▼              ▼              ▼                │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│   │ Memory   │   │ Tools    │   │Compaction│         │
│   │ System   │   │ Registry │   │ Strategy │         │
│   └──────────┘   └──────────┘   └──────────┘         │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Message (消息)
- **职责**: 表示单条对话消息
- **字段**:
  - role: 'user' | 'assistant' | 'system' | 'tool'
  - content: 消息内容
  - metadata: 元数据（工具调用信息、错误标记等）
  - timestamp: 时间戳

### 2. MemorySystem (内存系统)
- **职责**: 管理会话的存储、加载、查询
- **核心方法**:
  - create_session(): 创建新会话
  - add_message(): 添加消息
  - save_session(): 保存到JSON文件
  - load_session(): 从JSON加载
  - get_context(): 获取上下文用于模型输入
  - count_tokens(): 估算token数

- **存储格式**:
```json
{
  "session_id": "session_20260604_112511",
  "created_at": "2026-06-04T11:25:11.162401",
  "updated_at": "2026-06-04T11:25:11.169680",
  "message_count": 10,
  "messages": [
    {
      "role": "user",
      "content": "你好",
      "metadata": {},
      "timestamp": "2026-06-04T11:25:11.162401"
    }
  ]
}
```

### 3. ToolRegistry (工具注册)
- **职责**: 管理所有可用工具
- **核心方法**:
  - register(): 注册工具（装饰器）
  - execute(): 执行工具
  - list_tools(): 列出所有工具
  - get(): 获取单个工具

- **工具定义**:
```python
@register_tool(description="计算数学表达式")
def calculator(expression: str) -> str:
    return str(eval(expression))
```

### 4. CompactionStrategy (压缩策略)
- **职责**: 在上下文超限时压缩消息
- **内置策略**:
  - SlidingWindowCompaction: 滑动窗口（保留最近N条）
  - ImportanceBasedCompaction: 基于重要性打分
  - HybridCompaction: 混合策略（保留首尾+关键消息）
  - SummarizationCompaction: 总结式压缩

### 5. AgentHarness (主框架)
- **职责**: 协调所有组件，管理对话循环
- **核心流程**:
```
1. 用户输入 → add_message('user', input)
2. 检查token数 → 超限则压缩
3. 获取上下文 → get_context()
4. 调用模型 → model_fn(context)
5. 解析响应 → ToolCallParser.parse()
6. 如有工具调用:
   - 执行工具 → tool_registry.execute()
   - 添加结果 → add_message('tool', result)
   - 返回步骤3
7. 保存会话 → save_session()
```

## 数据流

```
User Input
    ↓
[Memory: add_message]
    ↓
[Compaction Check]
    ↓
[Model Call] → Response
    ↓
[Parse Tool Calls]
    ↓
[Execute Tools] → Results
    ↓
[Memory: add_message]
    ↓
[Loop if needed]
    ↓
Final Response
    ↓
[Save Session]
```

## 扩展点

### 1. 添加新工具
```python
from tools import register_tool

@register_tool(description="你的工具描述")
def your_tool(param1: str, param2: int) -> str:
    # 工具逻辑
    return result
```

### 2. 自定义压缩策略
```python
from compaction import CompactionStrategy

class MyCompaction(CompactionStrategy):
    def compact(self, messages, target_tokens):
        # 你的压缩逻辑
        return compressed_messages
```

### 3. 集成不同的模型
```python
def my_model_wrapper(messages: List[Dict]) -> str:
    # 调用你的模型API
    response = your_api_call(messages)
    return response['text']

harness = AgentHarness(model_fn=my_model_wrapper)
```

## 关键设计决策

### 1. 为什么用JSON存储？
- ✅ 人类可读，易于调试
- ✅ 标准格式，跨语言支持
- ✅ Git友好（可以diff）
- ✅ 不需要数据库

### 2. 为什么用简单的token估算？
- ✅ 快速，无需tokenizer
- ✅ 对于压缩决策足够准确
- ✅ 可以根据需要替换为精确tokenizer

### 3. 为什么工具调用用简单解析而不是function calling？
- ✅ 模型无关，任何模型都可用
- ✅ 支持多种格式（JSON、函数调用语法）
- ✅ 易于调试和修改

### 4. 为什么使用decorator注册工具？
- ✅ 代码清晰，声明式
- ✅ 自动提取参数信息
- ✅ 易于添加新工具

## 性能考虑

### Token计数
- 当前: `len(content) // 2` (快速估算)
- 可优化: 集成tiktoken等精确计数器

### 压缩触发
- 当前: 每次run前检查
- 可优化: 只在添加消息后检查

### 会话保存
- 当前: 每轮对话后保存
- 可优化: 异步保存、批量保存

### 工具执行
- 当前: 同步执行
- 可优化: 并行执行多个工具

## 安全考虑

### 1. 工具执行沙箱
- ⚠️ python_executor 使用 exec() - 生产环境需要沙箱
- 建议: 使用 RestrictedPython 或容器化

### 2. 文件操作限制
- ⚠️ read_file/write_file 无路径限制
- 建议: 添加白名单机制

### 3. Shell命令
- ⚠️ shell_command 可执行任意命令
- 建议: 命令白名单或禁用

## 未来改进方向

### 短期
- [ ] 添加精确的token计数
- [ ] 异步工具执行
- [ ] 更好的错误恢复
- [ ] 日志系统

### 中期
- [ ] 向量数据库集成（长期记忆）
- [ ] 多会话管理
- [ ] 工具权限系统
- [ ] 流式输出优化

### 长期
- [ ] 多智能体协作
- [ ] 分布式执行
- [ ] 可视化界面
- [ ] 插件系统
