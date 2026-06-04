"""
使用示例 - 展示如何使用Agent Harness
"""

from harness import AgentHarness, SimpleModelWrapper
from tools import register_tool, get_tool_registry
from compaction import HybridCompaction
from typing import List, Dict
import os


# ============ 注册自定义工具 ============

@register_tool(description="获取天气信息")
def get_weather(city: str) -> str:
    """获取城市天气（模拟）"""
    weather_data = {
        '北京': '晴天，15-25度',
        '上海': '多云，18-28度',
        '深圳': '雨天，20-30度'
    }
    return weather_data.get(city, f"抱歉，没有{city}的天气信息")


@register_tool(description="搜索网页")
def web_search(query: str) -> str:
    """搜索网页（模拟）"""
    return f"搜索结果：关于'{query}'的网页有1234个结果..."


@register_tool(description="执行Shell命令")
def shell_command(command: str) -> str:
    """执行shell命令"""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error: {str(e)}"


# ============ 模型封装示例 ============

class MockLLM:
    """模拟的LLM - 用于测试"""

    def __call__(self, messages: List[Dict]) -> str:
        last_msg = messages[-1]['content']

        # 简单的规则匹配
        if '天气' in last_msg:
            # 提取城市
            for city in ['北京', '上海', '深圳']:
                if city in last_msg:
                    return f'让我查一下天气: {{"tool": "get_weather", "args": {{"city": "{city}"}}}}'
            return "请告诉我你想查询哪个城市的天气？"

        elif '搜索' in last_msg:
            # 提取搜索词
            query = last_msg.replace('搜索', '').strip()
            return f'正在搜索: {{"tool": "web_search", "args": {{"query": "{query}"}}}}'

        elif '计算' in last_msg:
            # 提取表达式
            import re
            match = re.search(r'[\d+\-*/().\s]+', last_msg)
            if match:
                expr = match.group().strip()
                return f'计算中: {{"tool": "calculator", "args": {{"expression": "{expr}"}}}}'

        elif 'ls' in last_msg or '列出' in last_msg:
            return f'执行命令: {{"tool": "shell_command", "args": {{"command": "ls -la"}}}}'

        else:
            return f"我理解了。你说的是: {last_msg}\n\n我可以帮你:\n1. 查天气\n2. 搜索网页\n3. 计算数学表达式\n4. 执行shell命令"


class OpenAIWrapper:
    """OpenAI API封装示例"""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model

    def __call__(self, messages: List[Dict]) -> str:
        try:
            import openai
            openai.api_key = self.api_key

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )

            return response.choices[0].message.content
        except ImportError:
            return "Error: openai package not installed"
        except Exception as e:
            return f"Error: {str(e)}"


# ============ 使用示例 ============

def example_basic():
    """基础使用示例"""
    print("\n" + "="*60)
    print("Example 1: Basic Usage")
    print("="*60)

    # 创建harness
    harness = AgentHarness(
        model_fn=MockLLM(),
        session_dir="./example_sessions",
        max_tokens=4000
    )

    # 创建新会话
    session_id = harness.create_session()
    print(f"Created session: {session_id}")

    # 运行对话
    harness.run("你好，请介绍一下自己")
    harness.run("帮我查一下北京的天气")
    harness.run("计算 123 * 456")

    # 查看统计
    print("\nStats:", harness.get_stats())


def example_resume():
    """会话恢复示例"""
    print("\n" + "="*60)
    print("Example 2: Session Resume")
    print("="*60)

    harness = AgentHarness(
        model_fn=MockLLM(),
        session_dir="./example_sessions"
    )

    # 列出所有会话
    sessions = harness.memory.list_sessions()
    print(f"\nFound {len(sessions)} sessions:")
    for session in sessions:
        print(f"  - {session['session_id']}: {session['message_count']} messages")

    # 恢复最近的会话
    if sessions:
        latest = sessions[0]
        harness.resume(latest['session_id'])
        harness.run("继续刚才的对话")


def example_custom_compaction():
    """自定义压缩策略示例"""
    print("\n" + "="*60)
    print("Example 3: Custom Compaction")
    print("="*60)

    # 使用混合压缩策略
    compaction = HybridCompaction(keep_first=3, keep_last=5)

    harness = AgentHarness(
        model_fn=MockLLM(),
        session_dir="./example_sessions",
        max_tokens=500,  # 设置小一点触发压缩
        compaction_strategy=compaction
    )

    harness.create_session()

    # 生成很多消息触发压缩
    for i in range(15):
        harness.run(f"这是第{i}条消息，内容很长" * 10, save_after=False)

    harness.memory.save_session()
    print(f"\nFinal message count: {len(harness.memory.messages)}")
    print(f"Compaction triggered: {harness.stats['compaction_count']} times")


def example_interactive():
    """交互式模式示例"""
    print("\n" + "="*60)
    print("Example 4: Interactive Chat")
    print("="*60)

    harness = AgentHarness(
        model_fn=MockLLM(),
        session_dir="./example_sessions"
    )

    # 进入交互模式
    harness.chat()


def example_with_real_model():
    """使用真实模型的示例"""
    print("\n" + "="*60)
    print("Example 5: With Real Model (需要配置API)")
    print("="*60)

    # 方式1: 使用OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        model = OpenAIWrapper(api_key)
        harness = AgentHarness(model_fn=model)
        harness.create_session()
        harness.run("你好，帮我解释一下什么是agent")
    else:
        print("需要设置 OPENAI_API_KEY 环境变量")

    # 方式2: 使用其他API（自定义）
    def custom_api_call(messages: List[Dict]) -> str:
        """
        这里可以调用任何模型API:
        - Claude API
        - Local model (vLLM, llama.cpp等)
        - 其他云服务
        """
        # 示例：调用本地vLLM服务
        # import requests
        # response = requests.post(
        #     "http://localhost:8000/v1/chat/completions",
        #     json={"messages": messages}
        # )
        # return response.json()['choices'][0]['message']['content']

        return "这里需要实现你的模型调用逻辑"

    # harness = AgentHarness(model_fn=custom_api_call)


def show_tools():
    """显示所有可用工具"""
    print("\n" + "="*60)
    print("Available Tools")
    print("="*60)

    registry = get_tool_registry()
    tools = registry.list_tools()

    for tool in tools:
        print(f"\n{tool['name']}:")
        print(f"  Description: {tool['description']}")
        print(f"  Parameters: {tool['parameters']}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]

        if example == "basic":
            example_basic()
        elif example == "resume":
            example_resume()
        elif example == "compaction":
            example_custom_compaction()
        elif example == "chat":
            example_interactive()
        elif example == "real":
            example_with_real_model()
        elif example == "tools":
            show_tools()
        else:
            print(f"Unknown example: {example}")
            print("Available: basic, resume, compaction, chat, real, tools")
    else:
        print("Usage: python example.py [basic|resume|compaction|chat|real|tools]")
        print("\nRunning basic example by default...\n")
        example_basic()

        print("\n\nTo try interactive mode, run:")
        print("  python example.py chat")
