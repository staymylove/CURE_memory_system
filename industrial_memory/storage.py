"""
Industrial Memory System - Phase 1: 数据库持久化层

这是从简单版本到工业级的第一步升级
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import sqlite3
import asyncio
from contextlib import asynccontextmanager


# ============ 数据模型 ============

@dataclass
class Message:
    """消息数据模型"""
    id: Optional[int] = None
    session_id: str = ""
    role: str = ""  # user, assistant, system, tool
    content: str = ""
    metadata: Dict[str, Any] = None
    timestamp: str = ""
    token_count: int = 0
    parent_message_id: Optional[int] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Session:
    """会话数据模型"""
    id: str
    user_id: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = None
    status: str = "active"  # active, archived, deleted
    message_count: int = 0

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MemorySummary:
    """记忆摘要"""
    id: Optional[int] = None
    session_id: str = ""
    start_message_id: int = 0
    end_message_id: int = 0
    summary: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class Knowledge:
    """长期知识"""
    id: Optional[int] = None
    user_id: str = ""
    knowledge_type: str = ""  # fact, preference, skill, context
    key: str = ""
    value: str = ""
    confidence: float = 1.0
    source_sessions: List[str] = None
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    last_accessed_at: Optional[str] = None

    def __post_init__(self):
        if self.source_sessions is None:
            self.source_sessions = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


# ============ 存储后端抽象 ============

class StorageBackend(ABC):
    """存储后端抽象接口"""

    @abstractmethod
    async def initialize(self):
        """初始化存储"""
        pass

    @abstractmethod
    async def save_message(self, message: Message) -> int:
        """保存消息，返回消息ID"""
        pass

    @abstractmethod
    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc"
    ) -> List[Message]:
        """获取消息列表"""
        pass

    @abstractmethod
    async def save_session(self, session: Session) -> None:
        """保存会话"""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        pass

    @abstractmethod
    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Session]:
        """列出会话"""
        pass

    @abstractmethod
    async def save_summary(self, summary: MemorySummary) -> int:
        """保存摘要"""
        pass

    @abstractmethod
    async def get_summaries(self, session_id: str) -> List[MemorySummary]:
        """获取会话摘要"""
        pass

    @abstractmethod
    async def save_knowledge(self, knowledge: Knowledge) -> int:
        """保存知识"""
        pass

    @abstractmethod
    async def get_knowledge(
        self,
        user_id: str,
        knowledge_type: Optional[str] = None,
        key: Optional[str] = None
    ) -> List[Knowledge]:
        """查询知识"""
        pass

    @abstractmethod
    async def close(self):
        """关闭连接"""
        pass


# ============ SQLite 实现 ============

class SQLiteBackend(StorageBackend):
    """SQLite实现 - 适合开发和小规模部署"""

    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self.conn = None

    async def initialize(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # 创建表
        await self._create_tables()

    async def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()

        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT,
                status TEXT DEFAULT 'active',
                message_count INTEGER DEFAULT 0
            )
        """)

        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                token_count INTEGER DEFAULT 0,
                parent_message_id INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # 摘要表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                start_message_id INTEGER NOT NULL,
                end_message_id INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # 知识表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                knowledge_type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source_sessions TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed_at TEXT
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_user_type
            ON knowledge_base(user_id, knowledge_type, key)
        """)

        self.conn.commit()

    async def save_message(self, message: Message) -> int:
        """保存消息"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO messages (
                session_id, role, content, metadata, timestamp,
                token_count, parent_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message.session_id,
            message.role,
            message.content,
            json.dumps(message.metadata),
            message.timestamp,
            message.token_count,
            message.parent_message_id
        ))

        message_id = cursor.lastrowid

        # 更新会话的message_count
        cursor.execute("""
            UPDATE sessions
            SET message_count = message_count + 1,
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), message.session_id))

        self.conn.commit()
        return message_id

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        order: str = "asc"
    ) -> List[Message]:
        """获取消息"""
        cursor = self.conn.cursor()

        order_sql = "ASC" if order == "asc" else "DESC"
        cursor.execute(f"""
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY timestamp {order_sql}
            LIMIT ? OFFSET ?
        """, (session_id, limit, offset))

        rows = cursor.fetchall()
        messages = []

        for row in rows:
            messages.append(Message(
                id=row['id'],
                session_id=row['session_id'],
                role=row['role'],
                content=row['content'],
                metadata=json.loads(row['metadata']),
                timestamp=row['timestamp'],
                token_count=row['token_count'],
                parent_message_id=row['parent_message_id']
            ))

        return messages

    async def save_session(self, session: Session) -> None:
        """保存会话"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO sessions (
                id, user_id, created_at, updated_at, metadata, status, message_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id,
            session.user_id,
            session.created_at,
            session.updated_at,
            json.dumps(session.metadata),
            session.status,
            session.message_count
        ))

        self.conn.commit()

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return Session(
            id=row['id'],
            user_id=row['user_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            metadata=json.loads(row['metadata']),
            status=row['status'],
            message_count=row['message_count']
        )

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Session]:
        """列出会话"""
        cursor = self.conn.cursor()

        query = "SELECT * FROM sessions WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        sessions = []
        for row in rows:
            sessions.append(Session(
                id=row['id'],
                user_id=row['user_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                metadata=json.loads(row['metadata']),
                status=row['status'],
                message_count=row['message_count']
            ))

        return sessions

    async def save_summary(self, summary: MemorySummary) -> int:
        """保存摘要"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO memory_summaries (
                session_id, start_message_id, end_message_id,
                summary, created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            summary.session_id,
            summary.start_message_id,
            summary.end_message_id,
            summary.summary,
            summary.created_at,
            json.dumps(summary.metadata)
        ))

        self.conn.commit()
        return cursor.lastrowid

    async def get_summaries(self, session_id: str) -> List[MemorySummary]:
        """获取摘要"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory_summaries
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))

        rows = cursor.fetchall()
        summaries = []

        for row in rows:
            summaries.append(MemorySummary(
                id=row['id'],
                session_id=row['session_id'],
                start_message_id=row['start_message_id'],
                end_message_id=row['end_message_id'],
                summary=row['summary'],
                created_at=row['created_at'],
                metadata=json.loads(row['metadata'])
            ))

        return summaries

    async def save_knowledge(self, knowledge: Knowledge) -> int:
        """保存知识"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO knowledge_base (
                user_id, knowledge_type, key, value, confidence,
                source_sessions, created_at, updated_at,
                access_count, last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            knowledge.user_id,
            knowledge.knowledge_type,
            knowledge.key,
            knowledge.value,
            knowledge.confidence,
            json.dumps(knowledge.source_sessions),
            knowledge.created_at,
            knowledge.updated_at,
            knowledge.access_count,
            knowledge.last_accessed_at
        ))

        self.conn.commit()
        return cursor.lastrowid

    async def get_knowledge(
        self,
        user_id: str,
        knowledge_type: Optional[str] = None,
        key: Optional[str] = None
    ) -> List[Knowledge]:
        """查询知识"""
        cursor = self.conn.cursor()

        query = "SELECT * FROM knowledge_base WHERE user_id = ?"
        params = [user_id]

        if knowledge_type:
            query += " AND knowledge_type = ?"
            params.append(knowledge_type)

        if key:
            query += " AND key = ?"
            params.append(key)

        query += " ORDER BY updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        knowledge_list = []
        for row in rows:
            knowledge_list.append(Knowledge(
                id=row['id'],
                user_id=row['user_id'],
                knowledge_type=row['knowledge_type'],
                key=row['key'],
                value=row['value'],
                confidence=row['confidence'],
                source_sessions=json.loads(row['source_sessions']),
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                access_count=row['access_count'],
                last_accessed_at=row['last_accessed_at']
            ))

        return knowledge_list

    async def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()


# ============ 使用示例 ============

async def demo():
    """演示使用"""
    # 初始化存储
    storage = SQLiteBackend("industrial_memory.db")
    await storage.initialize()

    # 创建会话
    session = Session(
        id="session_001",
        user_id="user_123",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        metadata={"source": "web_app"}
    )
    await storage.save_session(session)
    print(f"Created session: {session.id}")

    # 添加消息
    msg1 = Message(
        session_id="session_001",
        role="user",
        content="Hello, how are you?",
        token_count=5
    )
    msg_id = await storage.save_message(msg1)
    print(f"Saved message: {msg_id}")

    msg2 = Message(
        session_id="session_001",
        role="assistant",
        content="I'm doing great, thank you!",
        token_count=6
    )
    await storage.save_message(msg2)

    # 查询消息
    messages = await storage.get_messages("session_001")
    print(f"\nMessages in session:")
    for msg in messages:
        print(f"  [{msg.role}] {msg.content}")

    # 保存知识
    knowledge = Knowledge(
        user_id="user_123",
        knowledge_type="preference",
        key="language",
        value="Python",
        confidence=0.9,
        source_sessions=["session_001"]
    )
    await storage.save_knowledge(knowledge)
    print(f"\nSaved knowledge: {knowledge.key} = {knowledge.value}")

    # 查询知识
    user_knowledge = await storage.get_knowledge("user_123")
    print(f"\nUser knowledge:")
    for k in user_knowledge:
        print(f"  {k.knowledge_type}: {k.key} = {k.value}")

    # 关闭
    await storage.close()


if __name__ == "__main__":
    asyncio.run(demo())
