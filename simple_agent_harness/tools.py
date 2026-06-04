"""
Tool System - 工具注册和执行
"""

import inspect
from typing import Callable, Dict, Any, List, Optional
import json


class Tool:
    """工具定义"""

    def __init__(self, name: str, func: Callable, description: str):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = self._extract_parameters()

    def _extract_parameters(self) -> Dict:
        """从函数签名提取参数信息"""
        sig = inspect.signature(self.func)
        params = {}

        for param_name, param in sig.parameters.items():
            param_info = {
                'type': 'string',  # 简化：默认都是string
                'required': param.default == inspect.Parameter.empty
            }
            params[param_name] = param_info

        return params

    def execute(self, **kwargs) -> Any:
        """执行工具"""
        try:
            result = self.func(**kwargs)
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def to_schema(self) -> Dict:
        """转换为工具schema（用于模型理解）"""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters
        }


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """注册工具的装饰器"""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or "No description"

            tool = Tool(tool_name, func, tool_desc)
            self.tools[tool_name] = tool
            return func

        return decorator

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)

    def list_tools(self) -> List[Dict]:
        """列出所有工具"""
        return [tool.to_schema() for tool in self.tools.values()]

    def execute(self, name: str, **kwargs) -> Any:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return {'success': False, 'error': f'Tool not found: {name}'}

        return tool.execute(**kwargs)


# 全局工具注册表
_global_registry = ToolRegistry()


def register_tool(name: Optional[str] = None, description: Optional[str] = None):
    """全局工具注册装饰器"""
    return _global_registry.register(name, description)


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    return _global_registry


# ============ 内置工具 ============

@register_tool(description="执行Python代码并返回结果")
def python_executor(code: str) -> str:
    """执行Python代码"""
    try:
        # 安全考虑：实际使用时应该用沙箱
        local_vars = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)

        # 返回最后一个表达式的值
        if local_vars:
            return str(local_vars)
        return "Code executed successfully"
    except Exception as e:
        return f"Error: {str(e)}"


@register_tool(description="计算数学表达式")
def calculator(expression: str) -> str:
    """计算数学表达式"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


@register_tool(description="读取文件内容")
def read_file(file_path: str) -> str:
    """读取文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@register_tool(description="写入文件")
def write_file(file_path: str, content: str) -> str:
    """写入文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File written successfully: {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@register_tool(description="搜索文件中的文本")
def search_file(file_path: str, keyword: str) -> str:
    """在文件中搜索关键词"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        matches = []
        for i, line in enumerate(lines, 1):
            if keyword in line:
                matches.append(f"Line {i}: {line.strip()}")

        if matches:
            return '\n'.join(matches)
        return f"No matches found for '{keyword}'"
    except Exception as e:
        return f"Error: {str(e)}"


class ToolCallParser:
    """解析模型输出中的工具调用"""

    @staticmethod
    def parse(text: str) -> List[Dict]:
        """
        解析工具调用，支持多种格式：
        1. JSON格式: {"tool": "calculator", "args": {"expression": "1+1"}}
        2. 函数调用格式: calculator(expression="1+1")
        """
        tool_calls = []

        # 尝试JSON格式
        try:
            if '{' in text and '}' in text:
                start = text.index('{')
                end = text.rindex('}') + 1
                json_str = text[start:end]
                data = json.loads(json_str)

                if 'tool' in data:
                    tool_calls.append({
                        'tool': data['tool'],
                        'args': data.get('args', {})
                    })
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试函数调用格式（简化版）
        if not tool_calls and '(' in text and ')' in text:
            # 简单的正则匹配
            import re
            pattern = r'(\w+)\((.*?)\)'
            matches = re.findall(pattern, text)

            for tool_name, args_str in matches:
                # 简单解析参数
                args = {}
                if args_str:
                    for arg in args_str.split(','):
                        if '=' in arg:
                            key, value = arg.split('=', 1)
                            args[key.strip()] = value.strip().strip('"\'')

                tool_calls.append({
                    'tool': tool_name,
                    'args': args
                })

        return tool_calls


if __name__ == "__main__":
    # 测试工具系统
    registry = get_tool_registry()

    print("Registered tools:")
    for tool in registry.list_tools():
        print(f"  - {tool['name']}: {tool['description']}")

    # 测试工具调用
    print("\nTesting calculator:")
    result = registry.execute('calculator', expression='2 + 2 * 3')
    print(f"  Result: {result}")

    # 测试工具调用解析
    print("\nTesting tool call parser:")
    parser = ToolCallParser()

    text1 = 'I need to calculate: {"tool": "calculator", "args": {"expression": "100/5"}}'
    calls = parser.parse(text1)
    print(f"  Parsed from JSON: {calls}")

    text2 = 'Let me use calculator(expression="10*10")'
    calls = parser.parse(text2)
    print(f"  Parsed from function call: {calls}")
