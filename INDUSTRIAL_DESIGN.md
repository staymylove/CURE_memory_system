# 工业级 Memory System 设计方案

## 🎯 从简单到工业级的演进路径

### 当前系统（V1 - Simple）
```
✅ JSON文件存储
✅ 基础save/load
✅ 简单压缩策略
✅ 单机运行
```

### 工业级系统（V2 - Industrial）需要什么？

```
📊 分层记忆架构
🗄️ 持久化存储（数据库）
🔍 向量检索（RAG）
⚡ 性能优化
🔐 并发安全
📈 监控和可观测性
🔄 分布式支持
```

---

## 📐 架构设计

### 1. 分层记忆架构（Memory Hierarchy）

模仿人类记忆系统：

```
┌─────────────────────────────────────────────────┐
│  Working Memory (工作记忆)                       │
│  - 当前对话的最近N轮                             │
│  - 内存存储，最快                                │
│  - 容量: ~10-20条消息                            │
└─────────────────────────────────────────────────┘
                    ↓↑
┌─────────────────────────────────────────────────┐
│  Short-term Memory (短期记忆)                    │
│  - 当前会话的完整历史                            │
│  - Redis/本地缓存                                │
│  - 容量: 整个session (~1000条)                   │
└─────────────────────────────────────────────────┘
                    ↓↑
┌─────────────────────────────────────────────────┐
│  Long-term Memory (长期记忆)                     │
│  - 跨会话的知识和经验                            │
│  - PostgreSQL/MySQL                              │
│  - 容量: 无限                                    │
└─────────────────────────────────────────────────┘
                    ↓↑
┌─────────────────────────────────────────────────┐
│  Semantic Memory (语义记忆)                      │
│  - 向量化的知识库                                │
│  - Pinecone/Milvus/FAISS                        │
│  - 支持相似度检索                                │
└─────────────────────────────────────────────────┘
```

### 2. 核心组件架构

```python
# 工业级架构
MemoryManager
├── WorkingMemory          # 工作记忆（热数据）
├── ShortTermMemory        # 短期记忆（会话级）
├── LongTermMemory         # 长期记忆（持久化）
├── SemanticMemory         # 语义记忆（向量检索）
├── MemoryRetrieval        # 检索引擎
├── MemoryConsolidation    # 记忆巩固（后台任务）
└── MemoryMetrics          # 监控指标
```

---

## 🏗️ 详细设计

### 阶段1: 持久化存储层

#### 1.1 数据库Schema设计

```sql
-- 会话表
CREATE TABLE sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    metadata JSONB,
    status VARCHAR(20),  -- active, archived, deleted
    INDEX idx_user_created (user_id, created_at)
);

-- 消息表
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMP NOT NULL,
    token_count INT,
    embedding_id VARCHAR(64),  -- 关联向量
    parent_message_id BIGINT,  -- 支持分支对话
    INDEX idx_session_time (session_id, timestamp),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 记忆摘要表（压缩后的记忆）
CREATE TABLE memory_summaries (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    start_message_id BIGINT NOT NULL,
    end_message_id BIGINT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    metadata JSONB
);

-- 长期知识表（跨会话的知识）
CREATE TABLE knowledge_base (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    knowledge_type VARCHAR(50),  -- fact, preference, skill, context
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    confidence FLOAT,  -- 0-1之间
    source_sessions JSONB,  -- 来源会话
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMP,
    INDEX idx_user_type_key (user_id, knowledge_type, key)
);

-- 向量索引表
CREATE TABLE embeddings (
    id VARCHAR(64) PRIMARY KEY,
    entity_type VARCHAR(20),  -- message, summary, knowledge
    entity_id BIGINT NOT NULL,
    embedding_model VARCHAR(50),
    dimension INT,
    created_at TIMESTAMP NOT NULL
);
```

#### 1.2 存储层接口

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class StorageBackend(ABC):
    """存储后端抽象接口"""
    
    @abstractmethod
    async def save_message(self, message: Message) -> str:
        """保存单条消息"""
        pass
    
    @abstractmethod
    async def get_messages(
        self, 
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """获取消息"""
        pass
    
    @abstractmethod
    async def save_session(self, session: Session) -> None:
        """保存会话元信息"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        pass

class PostgresBackend(StorageBackend):
    """PostgreSQL实现"""
    pass

class SQLiteBackend(StorageBackend):
    """SQLite实现（开发/小规模）"""
    pass

class MongoBackend(StorageBackend):
    """MongoDB实现（文档型）"""
    pass
```

### 阶段2: 向量检索层（RAG）

#### 2.1 语义记忆系统

```python
from typing import List, Tuple
import numpy as np

class SemanticMemory:
    """语义记忆 - 支持向量检索"""
    
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        vector_store: VectorStore = None
    ):
        self.embedding_model = embedding_model
        self.vector_store = vector_store or FAISSVectorStore()
    
    async def add_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        embedding: Optional[np.ndarray] = None
    ) -> str:
        """添加记忆到向量库"""
        if embedding is None:
            embedding = await self.encode(content)
        
        memory_id = self.vector_store.add(
            vector=embedding,
            content=content,
            metadata=metadata
        )
        return memory_id
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """语义搜索"""
        query_embedding = await self.encode(query)
        
        results = self.vector_store.search(
            vector=query_embedding,
            top_k=top_k,
            filters=filters
        )
        return results
    
    async def encode(self, text: str) -> np.ndarray:
        """文本编码为向量"""
        # 调用embedding API
        pass

class VectorStore(ABC):
    """向量存储抽象"""
    
    @abstractmethod
    def add(self, vector: np.ndarray, content: str, metadata: Dict) -> str:
        pass
    
    @abstractmethod
    def search(
        self, 
        vector: np.ndarray, 
        top_k: int,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        pass

class FAISSVectorStore(VectorStore):
    """FAISS实现（本地）"""
    pass

class PineconeVectorStore(VectorStore):
    """Pinecone实现（云端）"""
    pass

class MilvusVectorStore(VectorStore):
    """Milvus实现（企业级）"""
    pass
```

#### 2.2 智能检索策略

```python
class MemoryRetrieval:
    """智能记忆检索"""
    
    def __init__(
        self,
        working_memory: WorkingMemory,
        semantic_memory: SemanticMemory,
        long_term_memory: LongTermMemory
    ):
        self.working = working_memory
        self.semantic = semantic_memory
        self.long_term = long_term_memory
    
    async def retrieve_context(
        self,
        query: str,
        session_id: str,
        strategy: str = "hybrid"
    ) -> List[Message]:
        """混合检索策略"""
        
        contexts = []
        
        # 1. 工作记忆（必须包含）
        working_ctx = self.working.get_recent(limit=10)
        contexts.extend(working_ctx)
        
        if strategy in ["semantic", "hybrid"]:
            # 2. 语义检索（相关记忆）
            semantic_results = await self.semantic.search(
                query=query,
                top_k=5,
                filters={"session_id": session_id}
            )
            contexts.extend(self._convert_to_messages(semantic_results))
        
        if strategy in ["temporal", "hybrid"]:
            # 3. 时间检索（最近的相关对话）
            temporal_results = await self.long_term.get_recent_by_topic(
                session_id=session_id,
                topic=self._extract_topic(query),
                limit=3
            )
            contexts.extend(temporal_results)
        
        # 4. 去重和排序
        contexts = self._deduplicate_and_rank(contexts)
        
        return contexts
```

### 阶段3: 记忆巩固（Memory Consolidation）

#### 3.1 后台任务系统

```python
import asyncio
from datetime import datetime, timedelta

class MemoryConsolidation:
    """记忆巩固 - 后台任务"""
    
    def __init__(self, memory_manager):
        self.manager = memory_manager
        self.running = False
    
    async def start(self):
        """启动后台任务"""
        self.running = True
        
        # 启动多个后台任务
        await asyncio.gather(
            self._consolidate_sessions(),
            self._extract_knowledge(),
            self._cleanup_old_data(),
            self._update_embeddings()
        )
    
    async def _consolidate_sessions(self):
        """会话巩固 - 总结和压缩"""
        while self.running:
            # 找到活跃会话
            active_sessions = await self.manager.get_active_sessions()
            
            for session in active_sessions:
                # 如果会话消息数>100，进行压缩
                if session.message_count > 100:
                    await self._compress_session(session)
            
            await asyncio.sleep(300)  # 5分钟检查一次
    
    async def _compress_session(self, session: Session):
        """压缩会话"""
        # 1. 获取旧消息（除了最近20条）
        old_messages = await self.manager.get_messages(
            session.id,
            offset=20
        )
        
        # 2. 用LLM生成摘要
        summary = await self._generate_summary(old_messages)
        
        # 3. 保存摘要
        await self.manager.save_summary(
            session_id=session.id,
            summary=summary,
            original_count=len(old_messages)
        )
        
        # 4. 归档旧消息
        await self.manager.archive_messages(
            [msg.id for msg in old_messages]
        )
    
    async def _extract_knowledge(self):
        """知识抽取 - 从对话中提取长期知识"""
        while self.running:
            # 找到需要处理的会话
            sessions = await self.manager.get_unprocessed_sessions()
            
            for session in sessions:
                # 抽取知识
                knowledge = await self._extract_facts(session)
                
                # 保存到知识库
                for fact in knowledge:
                    await self.manager.save_knowledge(fact)
            
            await asyncio.sleep(600)  # 10分钟
    
    async def _extract_facts(self, session: Session) -> List[Knowledge]:
        """从会话中抽取事实性知识"""
        messages = await self.manager.get_messages(session.id)
        
        # 用LLM提取
        prompt = f"""
        从以下对话中提取用户的关键信息：
        1. 事实性信息（名字、地点、日期等）
        2. 偏好和喜好
        3. 技能和专长
        4. 背景信息
        
        对话历史：
        {self._format_messages(messages)}
        
        输出JSON格式的知识条目。
        """
        
        # 调用LLM...
        pass
```

### 阶段4: 缓存和性能优化

#### 4.1 多级缓存

```python
from functools import lru_cache
import redis
from typing import Optional

class MemoryCache:
    """多级缓存系统"""
    
    def __init__(self):
        # L1: 进程内缓存（最快）
        self.l1_cache = {}
        self.l1_max_size = 1000
        
        # L2: Redis缓存（快）
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        
        # L3: 数据库（慢）
        self.db = None
    
    async def get(self, key: str) -> Optional[Any]:
        """三级缓存获取"""
        # L1
        if key in self.l1_cache:
            return self.l1_cache[key]
        
        # L2
        value = self.redis.get(key)
        if value:
            self.l1_cache[key] = value
            return value
        
        # L3
        value = await self.db.get(key)
        if value:
            self.redis.setex(key, 3600, value)  # 1小时
            self.l1_cache[key] = value
        
        return value
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """写入缓存"""
        # 写穿策略：同时写入所有层
        self.l1_cache[key] = value
        self.redis.setex(key, ttl, value)
        await self.db.set(key, value)
```

#### 4.2 批量操作

```python
class BatchedMemoryManager:
    """批量操作优化"""
    
    def __init__(self):
        self.write_buffer = []
        self.buffer_size = 100
        self.flush_interval = 5  # 秒
    
    async def add_message(self, message: Message):
        """异步添加消息"""
        self.write_buffer.append(message)
        
        if len(self.write_buffer) >= self.buffer_size:
            await self.flush()
    
    async def flush(self):
        """批量写入数据库"""
        if not self.write_buffer:
            return
        
        # 批量插入
        await self.db.bulk_insert(self.write_buffer)
        self.write_buffer.clear()
    
    async def start_auto_flush(self):
        """自动刷新"""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush()
```

### 阶段5: 并发安全

#### 5.1 分布式锁

```python
import asyncio
from contextlib import asynccontextmanager

class DistributedLock:
    """分布式锁（基于Redis）"""
    
    def __init__(self, redis_client, key: str, timeout: int = 10):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.identifier = str(uuid.uuid4())
    
    async def acquire(self) -> bool:
        """获取锁"""
        return await self.redis.set(
            self.key,
            self.identifier,
            ex=self.timeout,
            nx=True  # 只在不存在时设置
        )
    
    async def release(self):
        """释放锁"""
        # 使用Lua脚本保证原子性
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(lua_script, 1, self.key, self.identifier)
    
    @asynccontextmanager
    async def __call__(self):
        """上下文管理器"""
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError("Could not acquire lock")
        
        try:
            yield
        finally:
            await self.release()

# 使用
async with DistributedLock(redis_client, f"session:{session_id}"):
    # 操作会话
    pass
```

### 阶段6: 监控和可观测性

#### 6.1 指标收集

```python
from dataclasses import dataclass
from datetime import datetime
import prometheus_client as prom

@dataclass
class MemoryMetrics:
    """记忆系统指标"""
    
    # 容量指标
    total_sessions: int
    total_messages: int
    total_knowledge: int
    
    # 性能指标
    avg_retrieval_time: float
    cache_hit_rate: float
    
    # 使用指标
    active_sessions: int
    messages_per_second: float
    
    # 存储指标
    storage_size_bytes: int
    vector_count: int

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        # Prometheus指标
        self.message_counter = prom.Counter(
            'memory_messages_total',
            'Total messages stored'
        )
        
        self.retrieval_duration = prom.Histogram(
            'memory_retrieval_duration_seconds',
            'Memory retrieval duration'
        )
        
        self.cache_hits = prom.Counter(
            'memory_cache_hits_total',
            'Cache hits',
            ['level']  # l1, l2, l3
        )
    
    def record_message(self):
        self.message_counter.inc()
    
    def record_retrieval(self, duration: float):
        self.retrieval_duration.observe(duration)
    
    def record_cache_hit(self, level: str):
        self.cache_hits.labels(level=level).inc()
```

---

## 📝 实施建议

### 渐进式升级路径

#### Phase 1: 基础持久化（1-2周）
- [ ] 设计数据库schema
- [ ] 实现PostgreSQL/SQLite backend
- [ ] 迁移现有JSON存储
- [ ] 添加基本的查询接口

#### Phase 2: 向量检索（2-3周）
- [ ] 集成embedding模型
- [ ] 实现FAISS向量存储
- [ ] 添加语义搜索接口
- [ ] 实现混合检索策略

#### Phase 3: 记忆巩固（2-3周）
- [ ] 实现后台任务系统
- [ ] 添加自动摘要功能
- [ ] 实现知识抽取
- [ ] 添加清理任务

#### Phase 4: 性能优化（1-2周）
- [ ] 实现多级缓存
- [ ] 添加批量操作
- [ ] 实现连接池
- [ ] 性能测试和调优

#### Phase 5: 生产就绪（2-3周）
- [ ] 添加分布式锁
- [ ] 实现监控指标
- [ ] 添加日志系统
- [ ] 编写运维文档

### 技术栈推荐

**开发阶段：**
- 数据库: SQLite（简单）
- 向量: FAISS（本地）
- 缓存: 内存

**生产阶段：**
- 数据库: PostgreSQL + pgvector
- 向量: Pinecone / Milvus
- 缓存: Redis Cluster
- 监控: Prometheus + Grafana
- 日志: ELK Stack

### 成本考虑

**小规模（<1000用户）：**
- 数据库: $20-50/月
- 向量存储: $70-100/月
- 服务器: $50-100/月
- **总计: ~$200/月**

**中规模（1000-10000用户）：**
- 数据库: $100-200/月
- 向量存储: $200-500/月
- 服务器: $200-500/月
- **总计: ~$800/月**

**大规模（>10000用户）：**
- 数据库集群: $500+/月
- 向量存储集群: $1000+/月
- 服务器集群: $1000+/月
- **总计: $3000+/月**

---

## 🎯 下一步行动

我建议按以下顺序推进：

1. **立即开始**: Phase 1（基础持久化）
   - 先设计好schema
   - 实现SQLite版本（快速验证）
   - 保持向后兼容

2. **短期目标**: Phase 2（向量检索）
   - 这是最有价值的功能
   - 可以显著提升agent能力

3. **中期目标**: Phase 3-4（巩固+优化）
   - 当数据量增长后再考虑

4. **长期目标**: Phase 5（生产就绪）
   - 准备上线时再实施

需要我帮你：
- 设计具体的数据库schema？
- 实现Phase 1的代码？
- 搭建向量检索系统？
