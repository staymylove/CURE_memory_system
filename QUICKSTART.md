# 快速开始指南 - CURE Memory System

5分钟上手，从简单到工业级

---

## 🎯 你将学到什么

- ✅ 运行第一个agent memory示例
- ✅ 理解基本概念
- ✅ 选择合适的版本
- ✅ 集成到你的项目

---

## 📦 项目结构一览

```bash
CURE_memory_system/
├── simple_agent_harness/    # V1: 简单版 - 适合学习
└── industrial_memory/        # V2: 工业级 - 适合生产
```

---

## 🚀 第一步：运行示例

### 选项A：Simple版本（推荐新手）

```bash
cd CURE_memory_system/simple_agent_harness

# 运行基础示例
python example.py basic

# 看到输出：
# ✓ Created session
# ✓ [user] 你好
# ✓ [assistant] 回复
```

**特点：** 
- 无需安装依赖
- 代码简单易懂
- 5分钟搞定

### 选项B：Industrial版本（准备生产）

```bash
cd CURE_memory_system/industrial_memory

# 运行完整演示
python demo.py

# 看到输出：
# ✓ Creating session...
# ✓ Simulating conversation...
# ✓ Semantic search test...
# ✓ Knowledge base query...
```

**特点：**
- 数据库持久化
- 语义检索
- 知识管理

---

## 💡 核心概念（3分钟理解）

### 1. Session（会话）
一次完整的对话，从开始到结束

```python
# 创建会话
session_id = harness.create_session()

# 一个会话包含多条消息
```

### 2. Message（消息）
对话中的单条消息

```python
# 添加用户消息
harness.add_message("user", "你好")

# 添加助手回复
harness.add_message("assistant", "你好！")
```

### 3. Context（上下文）
发送给模型的历史消息

```python
# 获取最近的上下文
context = harness.get_context()

# 发送给模型
response = model(context)
```

### 4. Compaction（压缩）
当上下文太长时，压缩旧消息

```python
# 自动压缩
if token_count > max_tokens:
    compress_old_messages()
```

---

## 🎓 选择合适的版本

### 用Simple版本，如果...

✅ **你是新手**
```python
# 代码简单直观
harness = AgentHarness(model_fn=my_model)
harness.run("帮我写代码")
```

✅ **快速原型**
- 从0到运行：5分钟
- 无需配置数据库
- JSON文件存储

✅ **小规模项目**
- <100用户
- <10000条消息
- 单机部署

✅ **学习目的**
- 理解agent原理
- 代码清晰易读
- 完整单元测试

### 用Industrial版本，如果...

✅ **生产部署**
```python
# 配置齐全
config = MemoryConfig(
    enable_semantic_search=True,
    db_path="production.db"
)
manager = MemoryManager(config=config)
```

✅ **需要语义搜索**
```python
# 智能检索
context = await manager.get_context(
    strategy="semantic",
    query="用户偏好"
)
```

✅ **规模较大**
- >1000用户
- >100000条消息
- 需要扩展

✅ **长期知识**
```python
# 知识库
await manager.save_knowledge(
    user_id="123",
    key="language",
    value="Python"
)
```

---

## 🔧 集成到你的项目

### Simple版本集成

**步骤1：复制核心文件**
```bash
cp simple_agent_harness/memory.py your_project/
cp simple_agent_harness/harness.py your_project/
```

**步骤2：使用**
```python
from harness import AgentHarness

# 定义你的模型函数
def my_model(messages):
    # 调用OpenAI/Claude/本地模型
    return model_api_call(messages)

# 创建harness
harness = AgentHarness(model_fn=my_model)

# 使用
harness.create_session()
response = harness.run("用户输入")
```

### Industrial版本集成

**步骤1：安装依赖**
```bash
pip install numpy  # 必需
# pip install faiss-cpu  # 可选，用于高性能向量检索
```

**步骤2：初始化**
```python
from memory_manager import MemoryManager, MemoryConfig
import asyncio

async def main():
    # 配置
    config = MemoryConfig(
        db_path="your_app.db",
        enable_semantic_search=True
    )
    
    # 初始化
    manager = MemoryManager(config=config)
    await manager.initialize()
    
    # 创建会话
    await manager.create_session(
        session_id="user_session_001",
        user_id="user_123"
    )
    
    # 添加消息
    await manager.add_message("user", "用户输入")
    await manager.add_message("assistant", "助手回复")
    
    # 获取上下文
    context = await manager.get_context(
        strategy="hybrid",  # 混合检索
        query="最近的话题",
        max_messages=20
    )
    
    # 关闭
    await manager.close()

asyncio.run(main())
```

---

## 📖 接下来学什么？

### 如果选择了Simple版本

1. **理解架构**
   ```bash
   cat simple_agent_harness/ARCHITECTURE.md
   ```

2. **看集成示例**
   ```bash
   python example.py chat  # 交互模式
   python example.py compaction  # 压缩测试
   ```

3. **自定义工具**
   ```python
   from tools import register_tool
   
   @register_tool
   def my_tool(param: str) -> str:
       return "result"
   ```

4. **运行测试**
   ```bash
   python test_harness.py
   ```

### 如果选择了Industrial版本

1. **阅读设计文档**
   ```bash
   cat INDUSTRIAL_DESIGN.md
   ```

2. **理解分层架构**
   - Working Memory（工作记忆）
   - Long-term Memory（长期记忆）
   - Semantic Memory（语义记忆）

3. **测试各组件**
   ```bash
   python storage.py          # 数据库层
   python simple_semantic.py  # 向量检索
   ```

4. **配置优化**
   ```python
   config = MemoryConfig(
       working_memory_size=30,      # 增大工作记忆
       compression_threshold=200,    # 压缩阈值
       enable_semantic_search=True   # 启用语义搜索
   )
   ```

---

## 🐛 常见问题

### Q1: 运行报错找不到模块？

**A:** 确保在正确的目录
```bash
cd CURE_memory_system/simple_agent_harness
# 或
cd CURE_memory_system/industrial_memory
```

### Q2: Industrial版本提示需要faiss？

**A:** 两个选择：
1. 使用简化版（无需faiss）
   ```python
   from simple_semantic import SimpleSemanticMemory
   ```

2. 安装faiss
   ```bash
   pip install faiss-cpu
   ```

### Q3: 如何连接真实的LLM？

**Simple版本：**
```python
import openai

def openai_model(messages):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    return response.choices[0].message.content

harness = AgentHarness(model_fn=openai_model)
```

**Industrial版本：**
```python
# 在add_message后，获取context
context = await manager.get_context()

# 调用模型
response = your_llm_api(context)

# 添加回复
await manager.add_message("assistant", response)
```

### Q4: 数据存储在哪里？

**Simple版本：**
- `./sessions/*.json` - 会话文件

**Industrial版本：**
- `memory.db` - SQLite数据库
- `./vector_store/` - 向量索引

### Q5: 如何清理旧数据？

**Simple版本：**
```bash
rm -rf sessions/
```

**Industrial版本：**
```python
# 归档旧会话
session.status = "archived"
await storage.save_session(session)

# 删除SQLite文件重新开始
rm memory.db
```

---

## 🎯 快速参考卡

### Simple版本 - 常用操作

```python
# 创建
harness = AgentHarness(model_fn=my_model)
session_id = harness.create_session()

# 运行
response = harness.run("用户输入")

# 恢复
harness.resume("session_id")

# 状态
stats = harness.get_stats()
```

### Industrial版本 - 常用操作

```python
# 初始化
manager = MemoryManager(config=config)
await manager.initialize()

# 会话
await manager.create_session("id", "user")
await manager.load_session("id")

# 消息
await manager.add_message("user", "text")
context = await manager.get_context(strategy="hybrid")

# 知识
await manager.save_knowledge(user_id, key, value)
knowledge = await manager.get_knowledge(user_id)

# 关闭
await manager.close()
```

---

## 📞 获取帮助

1. **查看文档**
   - Simple: `simple_agent_harness/README.md`
   - Industrial: `industrial_memory/README.md`

2. **运行示例**
   - Simple: `python example.py`
   - Industrial: `python demo.py`

3. **查看代码**
   - 所有代码都有详细注释
   - 从测试文件学习用法

---

## ✅ 检查清单

完成这些步骤，你就上手了：

- [ ] 选择了合适的版本
- [ ] 成功运行了示例
- [ ] 理解了核心概念
- [ ] 知道如何添加消息
- [ ] 知道如何获取上下文
- [ ] 尝试了集成到项目

**恭喜！🎉 你已经准备好使用CURE Memory System了！**

---

## 🚀 下一步

根据你的需求：

**原型开发** → 使用Simple版本 → 快速迭代

**学习研究** → 阅读ARCHITECTURE.md → 理解设计

**生产部署** → 使用Industrial版本 → 配置优化

**功能扩展** → 查看INDUSTRIAL_DESIGN.md → 实现Phase 3-5

---

**时间投入估算：**
- 快速上手：5-10分钟
- 理解原理：30-60分钟
- 集成项目：1-2小时
- 深入掌握：1-2天

**开始你的journey吧！** 🚀
