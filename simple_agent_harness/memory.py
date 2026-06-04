"""
Memory System - 负责会话的存储、加载和管理
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class Message:
    """单条消息"""
    def __init__(self, role: str, content: str, metadata: Optional[Dict] = None):
        self.role = role  # 'user', 'assistant', 'system', 'tool'
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            'role': self.role,
            'content': self.content,
            'metadata': self.metadata,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict):
        msg = cls(data['role'], data['content'], data.get('metadata', {}))
        msg.timestamp = data.get('timestamp', msg.timestamp)
        return msg


class MemorySystem:
    """内存系统 - 管理会话存储"""

    def __init__(self, session_dir: str = "./sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.current_session_id: Optional[str] = None
        self.messages: List[Message] = []

    def create_session(self, session_id: Optional[str] = None) -> str:
        """创建新会话"""
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.current_session_id = session_id
        self.messages = []
        return session_id

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加消息到当前会话"""
        msg = Message(role, content, metadata)
        self.messages.append(msg)
        return msg

    def get_messages(self, role: Optional[str] = None) -> List[Message]:
        """获取消息，可按角色过滤"""
        if role is None:
            return self.messages
        return [msg for msg in self.messages if msg.role == role]

    def save_session(self, session_id: Optional[str] = None):
        """保存会话到磁盘"""
        session_id = session_id or self.current_session_id
        if not session_id:
            raise ValueError("No active session to save")

        session_file = self.session_dir / f"{session_id}.json"

        data = {
            'session_id': session_id,
            'created_at': self.messages[0].timestamp if self.messages else datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'message_count': len(self.messages),
            'messages': [msg.to_dict() for msg in self.messages]
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Session saved: {session_file}")
        return session_file

    def load_session(self, session_id: str):
        """从磁盘加载会话"""
        session_file = self.session_dir / f"{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.current_session_id = session_id
        self.messages = [Message.from_dict(msg_data) for msg_data in data['messages']]

        print(f"Session loaded: {session_id} ({len(self.messages)} messages)")
        return self.messages

    def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        sessions = []
        for session_file in self.session_dir.glob("session_*.json"):
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions.append({
                    'session_id': data['session_id'],
                    'created_at': data['created_at'],
                    'updated_at': data['updated_at'],
                    'message_count': data['message_count']
                })

        # 按更新时间排序
        sessions.sort(key=lambda x: x['updated_at'], reverse=True)
        return sessions

    def get_context(self, max_messages: Optional[int] = None) -> List[Dict]:
        """获取对话上下文（用于发送给模型）"""
        messages = self.messages[-max_messages:] if max_messages else self.messages
        return [{'role': msg.role, 'content': msg.content} for msg in messages]

    def clear(self):
        """清空当前会话"""
        self.messages = []

    def count_tokens(self) -> int:
        """粗略估算token数（简单按字符数/2）"""
        total_chars = sum(len(msg.content) for msg in self.messages)
        return total_chars // 2  # 简化估算


if __name__ == "__main__":
    # 测试代码
    memory = MemorySystem("./test_sessions")

    # 创建新会话
    session_id = memory.create_session()
    print(f"Created session: {session_id}")

    # 添加消息
    memory.add_message("user", "你好")
    memory.add_message("assistant", "你好！有什么我可以帮助你的吗？")
    memory.add_message("user", "帮我写个快速排序")

    # 保存
    memory.save_session()

    # 列出会话
    print("\nAll sessions:")
    for session in memory.list_sessions():
        print(f"  {session['session_id']}: {session['message_count']} messages")

    # 加载会话
    memory2 = MemorySystem("./test_sessions")
    memory2.load_session(session_id)
    print(f"\nLoaded {len(memory2.messages)} messages")
