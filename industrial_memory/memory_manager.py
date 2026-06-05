"""
Industrial Memory System - 完整的Memory Manager

整合所有组件：存储层 + 语义记忆 + 分层架构
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
from storage import StorageBackend, SQLiteBackend, Message, Session, Knowledge
from semantic_memory import SemanticMemory, EmbeddingModel


@dataclass
class MemoryConfig:
    """Memory配置"""
    # 工作记忆
    working_memory_size: int = 20

    # 短期记忆
    short_term_ttl: int = 3600  # 1小时

    # 压缩阈值
    compression_threshold: int = 100

    # 向量检索
    enable_semantic_search: bool = True
    semantic_top_k: int = 5

    # 存储
    db_path: str = "memory.db"
    vector_store_path: str = "./vector_store"


class WorkingMemory:
    """工作记忆 - 当前对话的最近N条"""

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.messages: List[Message] = []

    def add(self, message: Message):
        """添加消息"""
        self.messages.append(message)

        # 保持大小限制
        if len(self.messages) > self.max_size:
            self.messages.pop(0)

    def get_all(self) -> List[Message]:
        """获取所有消息"""
        return self.messages.copy()

    def get_recent(self, n: int) -> List[Message]:
        """获取最近N条"""
        return self.messages[-n:]

    def clear(self):
        """清空"""
        self.messages.clear()

    def size(self) -> int:
        """当前大小"""
        return len(self.messages)


class MemoryManager:
    """
    工业级记忆管理器

    分层架构：
    1. Working Memory - 工作记忆（热数据）
    2. Short-term Memory - 短期记忆（会话级）
    3. Long-term Memory - 长期记忆（持久化）
    4. Semantic Memory - 语义记忆（向量检索）
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        storage: Optional[StorageBackend] = None,
        semantic_memory: Optional[SemanticMemory] = None
    ):
        self.config = config or MemoryConfig()

        # 存储层
        self.storage = storage or SQLiteBackend(self.config.db_path)

        # 语义记忆
        self.semantic_memory = semantic_memory
        if self.config.enable_semantic_search and not semantic_memory:
            self.semantic_memory = SemanticMemory()

        # 工作记忆
        self.working_memory = WorkingMemory(self.config.working_memory_size)

        # 当前会话
        self.current_session: Optional[Session] = None

        # 统计
        self.stats = {
            'messages_added': 0,
            'semantic_searches': 0,
            'compressions': 0
        }

    async def initialize(self):
        """初始化"""
        await self.storage.initialize()

        if self.semantic_memory:
            # 尝试加载已有的向量索引
            try:
                self.semantic_memory.load(self.config.vector_store_path)
                print(f"Loaded existing vector store from {self.config.vector_store_path}")
            except:
                print("No existing vector store found, starting fresh")

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict] = None
    ) -> Session:
        """创建新会话"""
        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata=metadata or {},
            status='active'
        )

        await self.storage.save_session(session)
        self.current_session = session
        self.working_memory.clear()

        return session

    async def load_session(self, session_id: str) -> Optional[Session]:
        """加载会话"""
        session = await self.storage.get_session(session_id)
        if not session:
            return None

        self.current_session = session

        # 加载最近的消息到工作记忆
        messages = await self.storage.get_messages(
            session_id,
            limit=self.config.working_memory_size,
            order='desc'
        )

        self.working_memory.clear()
        for msg in reversed(messages):
            self.working_memory.add(msg)

        return session

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        auto_embed: bool = True
    ) -> Message:
        """
        添加消息到所有层级

        1. 保存到数据库（长期记忆）
        2. 添加到工作记忆
        3. 如果启用，添加到语义记忆
        """
        if not self.current_session:
            raise ValueError("No active session")

        # 创建消息
        message = Message(
            session_id=self.current_session.id,
            role=role,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.now().isoformat(),
            token_count=len(content) // 4  # 粗略估算
        )

        # 保存到数据库
        msg_id = await self.storage.save_message(message)
        message.id = msg_id

        # 添加到工作记忆
        self.working_memory.add(message)

        # 添加到语义记忆
        if auto_embed and self.semantic_memory and role in ['user', 'assistant']:
            await self.semantic_memory.add(
                id=f"msg_{msg_id}",
                content=content,
                metadata={
                    'session_id': self.current_session.id,
                    'role': role,
                    'timestamp': message.timestamp,
                    **metadata or {}
                }
            )

        self.stats['messages_added'] += 1

        # 检查是否需要压缩
        if self.current_session.message_count > self.config.compression_threshold:
            await self._maybe_compress()

        return message

    async def get_context(
        self,
        strategy: str = "working",
        query: Optional[str] = None,
        max_messages: int = 20
    ) -> List[Message]:
        """
        获取上下文

        strategy:
        - working: 只用工作记忆
        - recent: 最近的N条
        - semantic: 语义检索相关的
        - hybrid: 混合策略（推荐）
        """
        if strategy == "working":
            return self.working_memory.get_all()

        elif strategy == "recent":
            return await self.storage.get_messages(
                self.current_session.id,
                limit=max_messages,
                order='desc'
            )

        elif strategy == "semantic" and self.semantic_memory and query:
            # 语义检索
            results = await self.semantic_memory.search(
                query=query,
                top_k=max_messages,
                filters={'session_id': self.current_session.id}
            )

            # 根据message_id获取完整消息
            msg_ids = [int(id_.split('_')[1]) for id_, _, _ in results]
            messages = []

            for msg_id in msg_ids:
                msgs = await self.storage.get_messages(self.current_session.id)
                for msg in msgs:
                    if msg.id == msg_id:
                        messages.append(msg)
                        break

            self.stats['semantic_searches'] += 1
            return messages

        elif strategy == "hybrid" and query:
            # 混合策略：工作记忆 + 语义检索
            working = self.working_memory.get_all()

            if self.semantic_memory:
                semantic_results = await self.semantic_memory.search(
                    query=query,
                    top_k=max_messages // 2,
                    filters={'session_id': self.current_session.id}
                )

                # 获取语义检索的消息
                msg_ids = [int(id_.split('_')[1]) for id_, _, _ in semantic_results]
                all_msgs = await self.storage.get_messages(self.current_session.id)

                semantic_msgs = [msg for msg in all_msgs if msg.id in msg_ids]

                # 合并去重
                seen_ids = {msg.id for msg in working}
                for msg in semantic_msgs:
                    if msg.id not in seen_ids:
                        working.append(msg)

                # 按时间排序
                working.sort(key=lambda x: x.timestamp)

            return working

        else:
            # 默认返回工作记忆
            return self.working_memory.get_all()

    async def save_knowledge(
        self,
        user_id: str,
        knowledge_type: str,
        key: str,
        value: str,
        confidence: float = 1.0
    ) -> int:
        """保存长期知识"""
        knowledge = Knowledge(
            user_id=user_id,
            knowledge_type=knowledge_type,
            key=key,
            value=value,
            confidence=confidence,
            source_sessions=[self.current_session.id] if self.current_session else []
        )

        return await self.storage.save_knowledge(knowledge)

    async def get_knowledge(
        self,
        user_id: str,
        knowledge_type: Optional[str] = None
    ) -> List[Knowledge]:
        """获取用户知识"""
        return await self.storage.get_knowledge(user_id, knowledge_type)

    async def _maybe_compress(self):
        """可能触发压缩"""
        # 简单策略：如果消息数超过阈值，触发压缩
        # 实际可以在后台任务中执行
        print(f"[Compression] Session {self.current_session.id} needs compression")
        self.stats['compressions'] += 1

        # TODO: 实现实际的压缩逻辑
        # 1. 获取旧消息
        # 2. 用LLM生成摘要
        # 3. 保存摘要
        # 4. 归档旧消息

    async def close(self):
        """关闭连接"""
        # 保存向量索引
        if self.semantic_memory:
            self.semantic_memory.save(self.config.vector_store_path)

        await self.storage.close()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'working_memory_size': self.working_memory.size(),
            'current_session': self.current_session.id if self.current_session else None
        }


# ============ 使用示例 ============

async def demo():
    """完整演示"""
    print("=== Industrial Memory System Demo ===\n")

    # 创建配置
    config = MemoryConfig(
        working_memory_size=10,
        enable_semantic_search=True,
        db_path="industrial_memory.db"
    )

    # 创建管理器
    manager = MemoryManager(config=config)
    await manager.initialize()

    # 创建会话
    print("1. Creating session...")
    session = await manager.create_session(
        session_id="demo_session_001",
        user_id="user_123",
        metadata={"source": "demo"}
    )
    print(f"   Created: {session.id}\n")

    # 添加对话
    print("2. Adding messages...")
    conversations = [
        ("user", "Hi, I'm working on a Python project"),
        ("assistant", "Great! What kind of Python project are you working on?"),
        ("user", "It's a machine learning project using PyTorch"),
        ("assistant", "Excellent choice! PyTorch is very popular for ML. What specifically are you building?"),
        ("user", "I'm building a transformer model for NLP"),
        ("assistant", "That sounds interesting! Are you using HuggingFace transformers?"),
        ("user", "Yes, I'm fine-tuning BERT for text classification"),
        ("assistant", "Perfect! BERT is great for classification tasks. How large is your dataset?"),
    ]

    for role, content in conversations:
        await manager.add_message(role, content)
        print(f"   [{role}] {content[:50]}...")

    print(f"\n   Added {len(conversations)} messages")
    print(f"   Working memory size: {manager.working_memory.size()}\n")

    # 保存知识
    print("3. Extracting knowledge...")
    await manager.save_knowledge(
        user_id="user_123",
        knowledge_type="preference",
        key="ml_framework",
        value="PyTorch",
        confidence=0.95
    )
    await manager.save_knowledge(
        user_id="user_123",
        knowledge_type="skill",
        key="domain",
        value="NLP",
        confidence=0.9
    )
    print("   Saved knowledge about user\n")

    # 语义检索
    print("4. Semantic search...")
    query = "What ML framework does the user prefer?"
    context = await manager.get_context(strategy="semantic", query=query)
    print(f"   Query: {query}")
    print(f"   Found {len(context)} relevant messages:")
    for msg in context[:3]:
        print(f"     - [{msg.role}] {msg.content[:60]}...")
    print()

    # 混合检索
    print("5. Hybrid retrieval...")
    query = "Tell me about the user's project"
    context = await manager.get_context(strategy="hybrid", query=query, max_messages=5)
    print(f"   Query: {query}")
    print(f"   Context size: {len(context)} messages")
    print(f"   Last message: {context[-1].content[:60]}...\n")

    # 查询知识
    print("6. Querying knowledge base...")
    knowledge = await manager.get_knowledge("user_123")
    print(f"   User knowledge:")
    for k in knowledge:
        print(f"     - {k.knowledge_type}: {k.key} = {k.value} (confidence: {k.confidence})")
    print()

    # 统计
    print("7. Statistics:")
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # 关闭
    await manager.close()
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demo())
