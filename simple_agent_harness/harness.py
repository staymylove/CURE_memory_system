"""
Agent Harness - 主运行框架
"""

from typing import Optional, Dict, List, Callable, Any
from memory import MemorySystem, Message
from tools import ToolRegistry, ToolCallParser, get_tool_registry
from compaction import CompactionStrategy, SlidingWindowCompaction
import json


class AgentHarness:
    """Agent运行框架"""

    def __init__(
        self,
        model_fn: Callable[[List[Dict]], str],  # 模型推理函数
        session_dir: str = "./sessions",
        max_tokens: int = 8000,  # 最大上下文token
        max_iterations: int = 10,  # 最大工具调用轮次
        compaction_strategy: Optional[CompactionStrategy] = None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """
        初始化Agent Harness

        Args:
            model_fn: 模型推理函数，接收消息列表，返回生成的文本
            session_dir: 会话存储目录
            max_tokens: 最大上下文token数
            max_iterations: 单轮对话最大迭代次数
            compaction_strategy: 压缩策略
            tool_registry: 工具注册表
        """
        self.model_fn = model_fn
        self.memory = MemorySystem(session_dir)
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations

        self.compaction_strategy = compaction_strategy or SlidingWindowCompaction()
        self.tool_registry = tool_registry or get_tool_registry()
        self.tool_parser = ToolCallParser()

        # 统计信息
        self.stats = {
            'total_turns': 0,
            'tool_calls': 0,
            'compaction_count': 0
        }

    def create_session(self, session_id: Optional[str] = None) -> str:
        """创建新会话"""
        return self.memory.create_session(session_id)

    def resume(self, session_id: str):
        """恢复之前的会话"""
        self.memory.load_session(session_id)
        print(f"Resumed session: {session_id}")
        print(f"Message count: {len(self.memory.messages)}")

        # 显示最近几条消息
        recent = self.memory.messages[-3:]
        for msg in recent:
            print(f"  [{msg.role}] {msg.content[:50]}...")

    def _check_and_compact(self):
        """检查并压缩上下文"""
        current_tokens = self.memory.count_tokens()

        if current_tokens > self.max_tokens:
            print(f"\n[Compaction] Current tokens: {current_tokens}, compacting...")

            self.memory.messages = self.compaction_strategy.compact(
                self.memory.messages,
                target_tokens=int(self.max_tokens * 0.8)  # 压缩到80%
            )

            new_tokens = self.memory.count_tokens()
            print(f"[Compaction] After: {new_tokens} tokens ({len(self.memory.messages)} messages)")

            self.stats['compaction_count'] += 1

    def _execute_tool_calls(self, text: str) -> List[Dict]:
        """执行文本中的工具调用"""
        tool_calls = self.tool_parser.parse(text)
        results = []

        for call in tool_calls:
            tool_name = call['tool']
            args = call['args']

            print(f"\n[Tool Call] {tool_name}({args})")

            result = self.tool_registry.execute(tool_name, **args)
            results.append({
                'tool': tool_name,
                'args': args,
                'result': result
            })

            # 添加工具结果到memory
            self.memory.add_message(
                'tool',
                json.dumps(result, ensure_ascii=False),
                metadata={'tool_name': tool_name, 'args': args}
            )

            self.stats['tool_calls'] += 1

            print(f"[Tool Result] {result}")

        return results

    def run(
        self,
        user_input: str,
        stream: bool = False,
        save_after: bool = True
    ) -> str:
        """
        运行一轮对话

        Args:
            user_input: 用户输入
            stream: 是否流式输出
            save_after: 完成后是否保存会话

        Returns:
            最终的assistant回复
        """
        # 添加用户消息
        self.memory.add_message('user', user_input)

        # 检查是否需要压缩
        self._check_and_compact()

        iteration = 0
        final_response = ""

        while iteration < self.max_iterations:
            iteration += 1

            # 获取上下文
            context = self.memory.get_context()

            # 调用模型
            print(f"\n[Iteration {iteration}] Calling model...")
            try:
                response = self.model_fn(context)
            except Exception as e:
                error_msg = f"Model error: {str(e)}"
                print(f"[Error] {error_msg}")
                self.memory.add_message('system', error_msg, metadata={'error': True})
                break

            # 流式输出
            if stream:
                print(f"\n[Assistant] ", end="")
                for char in response:
                    print(char, end="", flush=True)
                print()
            else:
                print(f"\n[Assistant] {response}")

            # 添加assistant消息
            self.memory.add_message('assistant', response)
            final_response = response

            # 解析工具调用
            tool_calls = self.tool_parser.parse(response)

            if not tool_calls:
                # 没有工具调用，结束
                break

            # 执行工具
            tool_results = self._execute_tool_calls(response)

            # 如果所有工具都成功了，继续下一轮
            all_success = all(r['result'].get('success', False) for r in tool_results)
            if not all_success:
                print("[Warning] Some tool calls failed")

        # 保存会话
        if save_after:
            self.memory.save_session()

        self.stats['total_turns'] += 1
        return final_response

    def chat(self):
        """交互式对话模式"""
        print("=" * 60)
        print("Agent Harness - Interactive Mode")
        print("Commands: /exit, /save, /stats, /clear, /sessions")
        print("=" * 60)

        # 创建或选择会话
        sessions = self.memory.list_sessions()
        if sessions:
            print("\nExisting sessions:")
            for i, session in enumerate(sessions[:5], 1):
                print(f"  {i}. {session['session_id']} ({session['message_count']} msgs)")

            choice = input("\nResume session (number) or create new (n): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(sessions):
                session_id = sessions[int(choice) - 1]['session_id']
                self.resume(session_id)
            else:
                self.create_session()
        else:
            self.create_session()

        # 对话循环
        while True:
            try:
                user_input = input("\n[You] ").strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.startswith('/'):
                    if user_input == '/exit':
                        self.memory.save_session()
                        print("Goodbye!")
                        break
                    elif user_input == '/save':
                        self.memory.save_session()
                        continue
                    elif user_input == '/stats':
                        print(f"\nStats: {self.stats}")
                        continue
                    elif user_input == '/clear':
                        self.memory.clear()
                        print("Memory cleared")
                        continue
                    elif user_input == '/sessions':
                        for session in self.memory.list_sessions():
                            print(f"  {session['session_id']}: {session['message_count']} msgs")
                        continue
                    else:
                        print(f"Unknown command: {user_input}")
                        continue

                # 运行对话
                self.run(user_input, stream=True, save_after=False)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Saving...")
                self.memory.save_session()
                break
            except Exception as e:
                print(f"\n[Error] {e}")
                import traceback
                traceback.print_exc()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'current_messages': len(self.memory.messages),
            'current_tokens': self.memory.count_tokens(),
            'available_tools': len(self.tool_registry.tools)
        }


class SimpleModelWrapper:
    """简单的模型封装示例"""

    def __init__(self, api_call_fn: Callable):
        """
        api_call_fn: 实际的API调用函数
        例如: lambda messages: openai.ChatCompletion.create(messages=messages)
        """
        self.api_call_fn = api_call_fn

    def __call__(self, messages: List[Dict]) -> str:
        """调用模型并返回文本"""
        try:
            response = self.api_call_fn(messages)

            # 根据不同的API格式提取文本
            if isinstance(response, dict):
                # OpenAI格式
                if 'choices' in response:
                    return response['choices'][0]['message']['content']
                # 其他格式
                elif 'content' in response:
                    return response['content']
            elif isinstance(response, str):
                return response

            return str(response)
        except Exception as e:
            raise RuntimeError(f"Model call failed: {e}")


if __name__ == "__main__":
    # 测试用的mock模型
    def mock_model(messages: List[Dict]) -> str:
        """模拟模型响应"""
        last_msg = messages[-1]['content']

        if '计算' in last_msg or '算' in last_msg:
            return '让我计算一下: {"tool": "calculator", "args": {"expression": "2+2"}}'
        else:
            return f"收到你的消息: {last_msg}"

    # 创建harness
    harness = AgentHarness(
        model_fn=mock_model,
        session_dir="./test_sessions"
    )

    # 测试
    harness.create_session("test_session")
    harness.run("你好")
    harness.run("帮我计算 10 + 20")

    print("\n" + "="*60)
    print("Stats:", harness.get_stats())
