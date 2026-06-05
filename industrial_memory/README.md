# Industrial Memory System

一个功能齐全、工业级的Memory System实现。

## 🎯 特性

### ✅ 已实现

1. **分层记忆架构**
   - Working Memory（工作记忆）
   - Short-term Memory（短期记忆）
   - Long-term Memory（长期记忆）
   - Semantic Memory（语义记忆）

2. **持久化存储**
   - SQLite后端（开发/小规模）
   - 完整的数据库schema
   - 会话、消息、摘要、知识库

3. **向量检索**
   - 简化版（simple_semantic.py）- 无需依赖
   - FAISS版（semantic_memory.py）- 高性能

4. **智能检索**
   - 语义搜索
   - 混合检索
   - 过滤支持

### 🚧 规划中

5. **记忆巩固**
   - 后台任务系统
   - 自动摘要
   - 知识抽取

6. **性能优化**
   - 多级缓存
   - 批量操作
   - 连接池

7. **生产就绪**
   - 分布式锁
   - 监控指标
   - 日志系统

## 📁 项目结构

```
industrial_memory/
├── storage.py              # 数据库持久化层
├── semantic_memory.py      # FAISS向量检索（需要faiss）
├── simple_semantic.py      # 简化版向量检索（无依赖）
├── memory_manager.py       # 完整的Memory Manager
├── requirements.txt        # 依赖列表
└── README.md              # 本文件
```

## 🚀 快速开始

### 方式1: 简化版（无需额外依赖）

```bash
# 直接运行
python storage.py           # 测试存储层
python simple_semantic.py   # 测试简化版语义记忆
```

### 方式2: 完整版（需要faiss）

```bash
# 安装依赖
pip install faiss-cpu numpy

# 运行完整版
python semantic_memory.py   # 测试FAISS向量检索
python memory_manager.py    # 测试完整的Memory Manager
```

## 📖 使用示例

### 基础使用

```python
from memory_manager import MemoryManager, MemoryConfig
import asyncio

async def main():
    # 创建配置
    config = MemoryConfig(
        working_memory_size=20,
        enable_semantic_search=True,
        db_path="memory.db"
    )

    # 创建管理器
    manager = MemoryManager(config=config)
    await manager.initialize()

    # 创建会话
    session = await manager.create_session(
        session_id="session_001",
        user_id="user_123"
    )

    # 添加消息
    await manager.add_message("user", "Hello!")
    await manager.add_message("assistant", "Hi! How can I help?")

    # 获取上下文
    context = await manager.get_context(strategy="working")

    # 语义搜索
    relevant = await manager.get_context(
        strategy="semantic",
        query="greetings"
    )

    # 关闭
    await manager.close()

asyncio.run(main())
```

### 高级用法

```python
# 混合检索策略
context = await manager.get_context(
    strategy="hybrid",  # 结合工作记忆和语义搜索
    query="user's preferences",
    max_messages=20
)

# 保存长期知识
await manager.save_knowledge(
    user_id="user_123",
    knowledge_type="preference",
    key="language",
    value="Python",
    confidence=0.95
)

# 查询知识库
knowledge = await manager.get_knowledge("user_123")
for k in knowledge:
    print(f"{k.key}: {k.value}")
```

## 🏗️ 架构设计

### 分层记忆

```
┌─────────────────────────────────┐
│  Working Memory (20条)          │  ← 最热数据
│  内存存储，最快访问              │
└─────────────────────────────────┘
            ↓↑
┌─────────────────────────────────┐
│  Short-term Memory (会话级)     │
│  Redis缓存（规划中）             │
└─────────────────────────────────┘
            ↓↑
┌─────────────────────────────────┐
│  Long-term Memory (持久化)      │  ← 所有历史
│  SQLite/PostgreSQL               │
└─────────────────────────────────┘
            ↓↑
┌─────────────────────────────────┐
│  Semantic Memory (向量检索)     │  ← 智能搜索
│  FAISS/Pinecone                  │
└─────────────────────────────────┘
```

### 数据流

```
添加消息
    ↓
Working Memory (立即可用)
    ↓
Database (持久化)
    ↓
Vector Store (语义索引)
    ↓
完成
```

## 🔧 配置选项

```python
MemoryConfig(
    # 工作记忆大小
    working_memory_size=20,

    # 短期记忆TTL
    short_term_ttl=3600,

    # 压缩阈值
    compression_threshold=100,

    # 启用语义搜索
    enable_semantic_search=True,
    semantic_top_k=5,

    # 存储路径
    db_path="memory.db",
    vector_store_path="./vector_store"
)
```

## 📊 性能对比

| 操作 | 简化版 | FAISS版 | 说明 |
|------|--------|---------|------|
| 添加向量 | O(1) | O(1) | 两者相同 |
| 搜索 | O(n) | O(log n) | FAISS快100-1000倍 |
| 存储大小 | 小 | 较大 | FAISS有索引开销 |
| 依赖 | 无 | 需faiss | 简化版易部署 |

**建议**:
- < 1000条消息: 用简化版
- > 1000条消息: 用FAISS版
- 生产环境: 用FAISS + Pinecone/Milvus

## 🔄 迁移路径

### 从简单版升级

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 替换semantic_memory
```python
# 从
from simple_semantic import SimpleSemanticMemory as SemanticMemory

# 改为
from semantic_memory import SemanticMemory
```

3. 数据迁移（可选）
```python
# 加载旧数据
old_memory.load("./simple_vector_store")

# 迁移到新存储
for item in old_memory.vector_store.items:
    await new_memory.add(
        item.id,
        item.content,
        item.metadata
    )
```

## 📝 后续规划

### Phase 3: 记忆巩固（2-3周）
- [ ] 后台任务调度器
- [ ] 自动生成摘要
- [ ] 知识抽取pipeline
- [ ] 定期清理任务

### Phase 4: 性能优化（1-2周）
- [ ] Redis多级缓存
- [ ] 批量写入优化
- [ ] 连接池管理
- [ ] 性能基准测试

### Phase 5: 生产就绪（2-3周）
- [ ] PostgreSQL支持
- [ ] 分布式锁（Redis）
- [ ] Prometheus监控
- [ ] ELK日志集成
- [ ] Docker部署

## 🧪 测试

```bash
# 运行所有测试
pytest

# 测试覆盖率
pytest --cov=. --cov-report=html

# 性能测试
python benchmarks/performance_test.py
```

## 📚 相关文档

- [INDUSTRIAL_DESIGN.md](../INDUSTRIAL_DESIGN.md) - 完整设计文档
- [简单版文档](../simple_agent_harness/README.md) - 基础版本

## 🙋 常见问题

**Q: 简化版和FAISS版有什么区别？**
A: 简化版使用numpy暴力搜索，无需依赖；FAISS版使用高效索引，适合大规模数据。

**Q: 如何选择向量维度？**
A: 取决于embedding模型：
- OpenAI text-embedding-3-small: 1536
- Sentence-BERT: 384/768
- 自定义模型: 根据模型输出

**Q: 支持哪些数据库？**
A: 当前支持SQLite。PostgreSQL和MongoDB支持在规划中。

**Q: 如何处理大规模数据？**
A: 
1. 使用FAISS的IVF或HNSW索引
2. 定期压缩旧会话
3. 使用Redis缓存热数据
4. 考虑分片策略

## 📄 许可

MIT License
