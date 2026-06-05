"""
完整的Memory Manager - 使用简化版语义记忆

这个版本不需要faiss依赖，可以直接运行
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
from storage import StorageBackend, SQLiteBackend, Message, Session, Knowledge
from simple_semantic import SimpleSemanticMemory


@dataclass
class MemoryConfig:
    """Memory配置"""
    working_memory_size: int = 20
    short_term_ttl: int = 3600
    compression_threshold: int = 100
    enable_semantic_search: bool = True
    semantic_top_k: int = 5
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
    """工业级记忆管理器"""

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        storage: Optional[StorageBackend] = None,
        semantic_memory: Optional[SimpleSemanticMemory] = None
    ):
        self.config = config or MemoryConfig()
        self.storage = storage or SQLiteBackend(self.config.db_path)
        self.semantic_memory = semantic_memory

        if self.config.enable_semantic_search and not semantic_memory:
            self.semantic_memory = SimpleSemanticMemory()

        self.working_memory = WorkingMemory(self.config.working_memory_size)
        self.current_session: Optional[Session] = None

        self.stats = {
            'messages_added': 0,
            'semantic_searches': 0,
            'compressions': 0
        }

    async def initialize(self):
        """初始化"""
        await self.storage.initialize()

        if self.semantic_memory:
            try:
                self.semantic_memory.load(self.config.vector_store_path)
                print(f"✓ Loaded vector store from {self.config.vector_store_path}")
            except:
                print("○ Starting with fresh vector store")

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
        """添加消息"""
        if not self.current_session:
            raise ValueError("No active session")

        message = Message(
            session_id=self.current_session.id,
            role=role,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.now().isoformat(),
            token_count=len(content) // 4
        )

        msg_id = await self.storage.save_message(message)
        message.id = msg_id

        self.working_memory.add(message)

        if auto_embed and self.semantic_memory and role in ['user', 'assistant']:
            meta = {
                'session_id': self.current_session.id,
                'role': role,
                'timestamp': message.timestamp,
            }
            if metadata:
                meta.update(metadata)

            await self.semantic_memory.add(
                id=f"msg_{msg_id}",
                content=content,
                metadata=meta
            )

        self.stats['messages_added'] += 1

        if self.current_session.message_count > self.config.compression_threshold:
            await self._maybe_compress()

        return message

    async def get_context(
        self,
        strategy: str = "working",
        query: Optional[str] = None,
        max_messages: int = 20
    ) -> List[Message]:
        """获取上下文"""
        if strategy == "working":
            return self.working_memory.get_all()

        elif strategy == "recent":
            return await self.storage.get_messages(
                self.current_session.id,
                limit=max_messages,
                order='desc'
            )

        elif strategy == "semantic" and self.semantic_memory and query:
            results = await self.semantic_memory.search(
                query=query,
                top_k=max_messages,
                filters={'session_id': self.current_session.id}
            )

            msg_ids = [int(id_.split('_')[1]) for id_, _, _ in results]
            messages = []
            all_msgs = await self.storage.get_messages(self.current_session.id)

            for msg_id in msg_ids:
                for msg in all_msgs:
                    if msg.id == msg_id:
                        messages.append(msg)
                        break

            self.stats['semantic_searches'] += 1
            return messages

        elif strategy == "hybrid" and query:
            working = self.working_memory.get_all()

            if self.semantic_memory:
                semantic_results = await self.semantic_memory.search(
                    query=query,
                    top_k=max_messages // 2,
                    filters={'session_id': self.current_session.id}
                )

                msg_ids = [int(id_.split('_')[1]) for id_, _, _ in semantic_results]
                all_msgs = await self.storage.get_messages(self.current_session.id)

                semantic_msgs = [msg for msg in all_msgs if msg.id in msg_ids]

                seen_ids = {msg.id for msg in working}
                for msg in semantic_msgs:
                    if msg.id not in seen_ids:
                        working.append(msg)

                working.sort(key=lambda x: x.timestamp)

            return working

        else:
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
        print(f"[Compression] Session {self.current_session.id} needs compression")
        self.stats['compressions'] += 1

    async def close(self):
        """关闭连接"""
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


async def demo():
    """完整演示"""
    print("=" * 70)
    print("Industrial Memory System - Complete Demo")
    print("=" * 70)
    print()

    config = MemoryConfig(
        working_memory_size=10,
        enable_semantic_search=True,
        db_path="demo_memory.db"
    )

    manager = MemoryManager(config=config)
    await manager.initialize()

    print("📝 1. Creating session...")
    session = await manager.create_session(
        session_id="demo_session_001",
        user_id="user_123",
        metadata={"source": "demo", "language": "en"}
    )
    print(f"   ✓ Session: {session.id}\n")

    print("💬 2. Simulating conversation...")
    conversations = [
        ("user", "Hi, I'm working on a Python machine learning project"),
        ("assistant", "Great! What kind of ML project are you working on?"),
        ("user", "I'm building a chatbot using transformers and PyTorch"),
        ("assistant", "Excellent! Are you using HuggingFace transformers?"),
        ("user", "Yes, I'm fine-tuning BERT for intent classification"),
        ("assistant", "That's a solid approach. How large is your training dataset?"),
        ("user", "About 10,000 labeled examples across 20 intent classes"),
        ("assistant", "That should be sufficient for BERT fine-tuning. What's your accuracy so far?"),
    ]

    for role, content in conversations:
        await manager.add_message(role, content)
        print(f"   [{role:9s}] {content[:60]}...")

    print(f"\n   ✓ Added {len(conversations)} messages")
    print(f"   ✓ Working memory: {manager.working_memory.size()} messages\n")

    print("🧠 3. Extracting user knowledge...")
    knowledge_items = [
        ("preference", "programming_language", "Python", 0.95),
        ("preference", "ml_framework", "PyTorch", 0.90),
        ("skill", "domain", "NLP", 0.85),
        ("context", "current_project", "Chatbot with BERT", 0.90),
    ]

    for ktype, key, value, conf in knowledge_items:
        await manager.save_knowledge("user_123", ktype, key, value, conf)
        print(f"   ✓ {ktype}: {key} = {value}")

    print()

    print("🔍 4. Semantic search test...")
    queries = [
        "What ML framework does the user prefer?",
        "What is the user working on?",
        "How much data does the user have?",
    ]

    for query in queries:
        context = await manager.get_context(strategy="semantic", query=query, max_messages=3)
        print(f"\n   Query: {query}")
        print(f"   Found {len(context)} relevant messages:")
        for msg in context[:2]:
            print(f"     • [{msg.role}] {msg.content[:55]}...")

    print()

    print("\n🎯 5. Hybrid retrieval test...")
    query = "Tell me about the user's chatbot project details"
    context = await manager.get_context(strategy="hybrid", query=query, max_messages=6)
    print(f"   Query: {query}")
    print(f"   Retrieved {len(context)} messages (working + semantic)")
    print(f"   Mix of: recent context + semantically relevant history\n")

    print("📚 6. Knowledge base query...")
    knowledge = await manager.get_knowledge("user_123")
    print(f"   User knowledge ({len(knowledge)} items):")
    for k in knowledge:
        print(f"     • {k.knowledge_type:12s} | {k.key:20s} = {k.value:20s} (conf: {k.confidence:.2f})")

    print()

    print("📊 7. System statistics...")
    stats = manager.get_stats()
    print(f"   Messages added:     {stats['messages_added']}")
    print(f"   Semantic searches:  {stats['semantic_searches']}")
    print(f"   Working memory:     {stats['working_memory_size']} messages")
    print(f"   Current session:    {stats['current_session']}")

    print()

    await manager.close()
    print("=" * 70)
    print("✓ Demo completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
