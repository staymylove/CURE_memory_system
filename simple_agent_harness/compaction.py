"""
Compaction - 消息压缩策略
"""

from typing import List, Dict, Callable
from memory import Message


class CompactionStrategy:
    """压缩策略基类"""

    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """压缩消息列表"""
        raise NotImplementedError


class SlidingWindowCompaction(CompactionStrategy):
    """滑动窗口压缩 - 只保留最近的N条消息"""

    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """保留最近的消息直到不超过token限制"""
        if not messages:
            return []

        # 从后往前累积
        result = []
        current_tokens = 0

        for msg in reversed(messages):
            msg_tokens = len(msg.content) // 2  # 简化估算
            if current_tokens + msg_tokens > target_tokens and result:
                break
            result.insert(0, msg)
            current_tokens += msg_tokens

        return result


class ImportanceBasedCompaction(CompactionStrategy):
    """基于重要性的压缩 - 保留重要消息"""

    def __init__(self, importance_fn: Callable[[Message], float]):
        """
        importance_fn: 计算消息重要性的函数，返回0-1之间的分数
        """
        self.importance_fn = importance_fn

    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """按重要性保留消息"""
        if not messages:
            return []

        # 计算每条消息的重要性
        scored = [(msg, self.importance_fn(msg)) for msg in messages]
        scored.sort(key=lambda x: x[1], reverse=True)  # 按重要性降序

        # 贪心选择直到达到token限制
        result = []
        current_tokens = 0

        for msg, score in scored:
            msg_tokens = len(msg.content) // 2
            if current_tokens + msg_tokens <= target_tokens:
                result.append(msg)
                current_tokens += msg_tokens

        # 恢复时间顺序
        result.sort(key=lambda x: x.timestamp)
        return result


class HybridCompaction(CompactionStrategy):
    """混合压缩 - 保留首尾 + 关键消息"""

    def __init__(self, keep_first: int = 2, keep_last: int = 10):
        self.keep_first = keep_first
        self.keep_last = keep_last

    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """保留开头、结尾和中间的关键消息"""
        if not messages:
            return []

        if len(messages) <= self.keep_first + self.keep_last:
            return messages

        # 保留首尾
        first_msgs = messages[:self.keep_first]
        last_msgs = messages[-self.keep_last:]
        middle_msgs = messages[self.keep_first:-self.keep_last]

        # 计算中间部分还能保留多少
        used_tokens = sum(len(msg.content) // 2 for msg in first_msgs + last_msgs)
        remaining_tokens = target_tokens - used_tokens

        if remaining_tokens <= 0:
            return first_msgs + last_msgs

        # 从中间选择重要消息（工具调用、错误等）
        important_middle = []
        for msg in middle_msgs:
            if msg.role == 'tool' or 'error' in msg.metadata:
                msg_tokens = len(msg.content) // 2
                if remaining_tokens >= msg_tokens:
                    important_middle.append(msg)
                    remaining_tokens -= msg_tokens

        # 合并并保持顺序
        result = first_msgs + important_middle + last_msgs
        result.sort(key=lambda x: x.timestamp)
        return result


class SummarizationCompaction(CompactionStrategy):
    """总结式压缩 - 将中间部分总结成一条消息"""

    def __init__(self, summarize_fn: Callable[[List[Message]], str]):
        """
        summarize_fn: 总结函数，接收消息列表，返回总结文本
        """
        self.summarize_fn = summarize_fn

    def compact(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """保留最近消息，将旧消息总结"""
        if not messages:
            return []

        # 保留最近的消息
        keep_count = min(10, len(messages))
        recent = messages[-keep_count:]
        old = messages[:-keep_count]

        if not old:
            return recent

        # 总结旧消息
        summary_text = self.summarize_fn(old)
        summary_msg = Message(
            role='system',
            content=f"[Previous conversation summary]\n{summary_text}",
            metadata={'type': 'summary', 'original_count': len(old)}
        )

        return [summary_msg] + recent


def default_importance_fn(msg: Message) -> float:
    """默认的重要性评分函数"""
    score = 0.5  # 基础分

    # 工具调用和结果更重要
    if msg.role == 'tool':
        score += 0.3

    # 包含错误信息更重要
    if 'error' in msg.metadata or 'error' in msg.content.lower():
        score += 0.2

    # system消息更重要
    if msg.role == 'system':
        score += 0.1

    # 短消息可能是重要的指令
    if len(msg.content) < 50:
        score += 0.1

    return min(score, 1.0)


def simple_summarize_fn(messages: List[Message]) -> str:
    """简单的总结函数（不调用模型）"""
    user_msgs = [m for m in messages if m.role == 'user']
    assistant_msgs = [m for m in messages if m.role == 'assistant']

    summary = f"User asked {len(user_msgs)} questions, assistant provided {len(assistant_msgs)} responses."

    # 提取关键词（简化版）
    all_text = ' '.join(m.content for m in messages)
    words = all_text.split()
    if len(words) > 20:
        summary += f" Topics discussed: {' '.join(words[:20])}..."

    return summary


if __name__ == "__main__":
    from memory import MemorySystem

    # 测试
    memory = MemorySystem()
    memory.create_session()

    # 添加测试消息
    for i in range(20):
        memory.add_message("user", f"问题 {i}")
        memory.add_message("assistant", f"回答 {i}" * 10)

    print(f"Original: {len(memory.messages)} messages, ~{memory.count_tokens()} tokens")

    # 测试滑动窗口
    strategy = SlidingWindowCompaction()
    compacted = strategy.compact(memory.messages, target_tokens=500)
    print(f"Sliding window: {len(compacted)} messages")

    # 测试混合压缩
    strategy = HybridCompaction(keep_first=2, keep_last=5)
    compacted = strategy.compact(memory.messages, target_tokens=500)
    print(f"Hybrid: {len(compacted)} messages")

    # 测试基于重要性
    strategy = ImportanceBasedCompaction(default_importance_fn)
    compacted = strategy.compact(memory.messages, target_tokens=500)
    print(f"Importance-based: {len(compacted)} messages")
