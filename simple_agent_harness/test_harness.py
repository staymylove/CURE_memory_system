"""
单元测试 - Simple Agent Harness
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import json

from memory import Message, MemorySystem
from tools import Tool, ToolRegistry, ToolCallParser
from compaction import (
    SlidingWindowCompaction,
    HybridCompaction,
    ImportanceBasedCompaction,
    default_importance_fn
)
from harness import AgentHarness


class TestMessage(unittest.TestCase):
    """测试Message类"""

    def test_create_message(self):
        msg = Message('user', 'hello')
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, 'hello')
        self.assertIsInstance(msg.metadata, dict)
        self.assertIsNotNone(msg.timestamp)

    def test_message_to_dict(self):
        msg = Message('assistant', 'hi', {'key': 'value'})
        data = msg.to_dict()
        self.assertEqual(data['role'], 'assistant')
        self.assertEqual(data['content'], 'hi')
        self.assertEqual(data['metadata']['key'], 'value')

    def test_message_from_dict(self):
        data = {
            'role': 'user',
            'content': 'test',
            'metadata': {'foo': 'bar'},
            'timestamp': '2026-01-01T00:00:00'
        }
        msg = Message.from_dict(data)
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, 'test')
        self.assertEqual(msg.metadata['foo'], 'bar')


class TestMemorySystem(unittest.TestCase):
    """测试MemorySystem"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory = MemorySystem(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_session(self):
        session_id = self.memory.create_session()
        self.assertIsNotNone(session_id)
        self.assertEqual(self.memory.current_session_id, session_id)

    def test_add_message(self):
        self.memory.create_session()
        msg = self.memory.add_message('user', 'hello')
        self.assertEqual(len(self.memory.messages), 1)
        self.assertEqual(msg.role, 'user')

    def test_get_messages(self):
        self.memory.create_session()
        self.memory.add_message('user', 'q1')
        self.memory.add_message('assistant', 'a1')
        self.memory.add_message('user', 'q2')

        all_msgs = self.memory.get_messages()
        self.assertEqual(len(all_msgs), 3)

        user_msgs = self.memory.get_messages(role='user')
        self.assertEqual(len(user_msgs), 2)

    def test_save_and_load_session(self):
        session_id = self.memory.create_session('test_session')
        self.memory.add_message('user', 'hello')
        self.memory.add_message('assistant', 'hi')

        # 保存
        self.memory.save_session()

        # 新建memory实例并加载
        memory2 = MemorySystem(self.temp_dir)
        memory2.load_session('test_session')

        self.assertEqual(len(memory2.messages), 2)
        self.assertEqual(memory2.messages[0].content, 'hello')

    def test_get_context(self):
        self.memory.create_session()
        self.memory.add_message('user', 'q1')
        self.memory.add_message('assistant', 'a1')

        context = self.memory.get_context()
        self.assertEqual(len(context), 2)
        self.assertEqual(context[0]['role'], 'user')
        self.assertEqual(context[1]['content'], 'a1')

    def test_count_tokens(self):
        self.memory.create_session()
        self.memory.add_message('user', 'hello')
        tokens = self.memory.count_tokens()
        self.assertGreater(tokens, 0)

    def test_list_sessions(self):
        self.memory.create_session('session1')
        self.memory.add_message('user', 'test')
        self.memory.save_session()

        sessions = self.memory.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['session_id'], 'session1')


class TestToolSystem(unittest.TestCase):
    """测试工具系统"""

    def test_tool_creation(self):
        def test_func(x: str):
            return x.upper()

        tool = Tool('test', test_func, 'Test tool')
        self.assertEqual(tool.name, 'test')
        self.assertIn('x', tool.parameters)

    def test_tool_execute(self):
        def add(a: str, b: str):
            return str(int(a) + int(b))

        tool = Tool('add', add, 'Add two numbers')
        result = tool.execute(a='1', b='2')
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], '3')

    def test_tool_execute_error(self):
        def fail():
            raise ValueError("test error")

        tool = Tool('fail', fail, 'Fail tool')
        result = tool.execute()
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_registry(self):
        registry = ToolRegistry()

        @registry.register(description="Test")
        def my_tool(x: str):
            return x

        self.assertIn('my_tool', registry.tools)
        self.assertEqual(len(registry.list_tools()), 1)

    def test_registry_execute(self):
        registry = ToolRegistry()

        @registry.register()
        def echo(text: str):
            return text

        result = registry.execute('echo', text='hello')
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 'hello')

    def test_tool_call_parser_json(self):
        parser = ToolCallParser()
        text = 'Let me call: {"tool": "calculator", "args": {"expression": "1+1"}}'
        calls = parser.parse(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tool'], 'calculator')
        self.assertEqual(calls[0]['args']['expression'], '1+1')

    def test_tool_call_parser_function(self):
        parser = ToolCallParser()
        text = 'I will use calculator(expression="2+2")'
        calls = parser.parse(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tool'], 'calculator')


class TestCompaction(unittest.TestCase):
    """测试压缩策略"""

    def setUp(self):
        self.messages = [
            Message('user', f'message {i}' * 10)
            for i in range(20)
        ]

    def test_sliding_window(self):
        strategy = SlidingWindowCompaction()
        compacted = strategy.compact(self.messages, target_tokens=100)

        self.assertLess(len(compacted), len(self.messages))
        # 应该保留最后几条
        self.assertIn(self.messages[-1], compacted)

    def test_hybrid_compaction(self):
        strategy = HybridCompaction(keep_first=2, keep_last=3)
        compacted = strategy.compact(self.messages, target_tokens=1000)

        # 应该包含首尾消息
        self.assertIn(self.messages[0], compacted)
        self.assertIn(self.messages[-1], compacted)

    def test_importance_based(self):
        # 添加一些"重要"消息
        self.messages[5].role = 'tool'  # 工具调用更重要
        self.messages[10].metadata['error'] = True  # 错误更重要

        strategy = ImportanceBasedCompaction(default_importance_fn)
        compacted = strategy.compact(self.messages, target_tokens=200)

        # 重要消息应该被保留
        self.assertIn(self.messages[5], compacted)
        self.assertIn(self.messages[10], compacted)


class TestAgentHarness(unittest.TestCase):
    """测试AgentHarness"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        # Mock模型
        def mock_model(messages):
            last = messages[-1]['content']
            if 'tool' in last.lower():
                return '{"tool": "calculator", "args": {"expression": "1+1"}}'
            return f"Response to: {last}"

        self.harness = AgentHarness(
            model_fn=mock_model,
            session_dir=self.temp_dir,
            max_tokens=1000
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_session(self):
        session_id = self.harness.create_session()
        self.assertIsNotNone(session_id)

    def test_run_simple(self):
        self.harness.create_session()
        response = self.harness.run("hello", save_after=False)
        self.assertIn("hello", response)

    def test_run_with_tool(self):
        self.harness.create_session()
        response = self.harness.run("call a tool", save_after=False)

        # 应该有工具调用
        tool_msgs = self.harness.memory.get_messages(role='tool')
        self.assertGreater(len(tool_msgs), 0)

    def test_stats(self):
        self.harness.create_session()
        self.harness.run("test", save_after=False)

        stats = self.harness.get_stats()
        self.assertEqual(stats['total_turns'], 1)
        self.assertGreater(stats['current_messages'], 0)

    def test_save_and_resume(self):
        session_id = self.harness.create_session('test_session')
        self.harness.run("first message", save_after=True)

        # 新harness加载
        harness2 = AgentHarness(
            model_fn=lambda m: "resumed",
            session_dir=self.temp_dir
        )
        harness2.resume('test_session')

        self.assertGreater(len(harness2.memory.messages), 0)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_workflow(self):
        temp_dir = tempfile.mkdtemp()

        try:
            # 创建harness
            call_count = {'count': 0}

            def counting_model(messages):
                call_count['count'] += 1
                return f"Response {call_count['count']}"

            harness = AgentHarness(
                model_fn=counting_model,
                session_dir=temp_dir
            )

            # 创建会话
            session_id = harness.create_session()

            # 多轮对话
            harness.run("message 1", save_after=False)
            harness.run("message 2", save_after=False)
            harness.run("message 3", save_after=True)

            # 检查状态
            self.assertEqual(harness.stats['total_turns'], 3)
            self.assertEqual(len(harness.memory.messages), 6)  # 3 user + 3 assistant

            # 保存并重新加载
            harness.memory.save_session()

            harness2 = AgentHarness(
                model_fn=counting_model,
                session_dir=temp_dir
            )
            harness2.resume(session_id)

            self.assertEqual(len(harness2.memory.messages), 6)

        finally:
            shutil.rmtree(temp_dir)


def run_tests():
    """运行所有测试"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
