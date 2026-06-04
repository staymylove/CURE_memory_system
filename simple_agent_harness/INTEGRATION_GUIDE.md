"""
快速集成指南 - 如何在你的项目中使用这个框架

## 场景1: 接入OpenAI/Claude等API

```python
from harness import AgentHarness
import openai

# OpenAI
def openai_model(messages):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    return response.choices[0].message.content

harness = AgentHarness(model_fn=openai_model)
harness.create_session()
harness.run("帮我写一个快速排序")
```

## 场景2: 接入本地模型（vLLM）

```python
import requests

def vllm_model(messages):
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "your-model",
            "messages": messages,
            "max_tokens": 2000
        }
    )
    return response.json()['choices'][0]['message']['content']

harness = AgentHarness(model_fn=vllm_model)
```

## 场景3: 接入HuggingFace模型

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("your-model")
tokenizer = AutoTokenizer.from_pretrained("your-model")

def hf_model(messages):
    # 转换为prompt
    prompt = tokenizer.apply_chat_template(
        messages, 
        tokenize=False,
        add_generation_prompt=True
    )
    
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=512)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # 提取assistant部分
    return response.split("assistant\n")[-1]

harness = AgentHarness(model_fn=hf_model)
```

## 场景4: 添加自定义工具

```python
from tools import register_tool
import requests

@register_tool(description="查询数据库")
def query_db(sql: str) -> str:
    # 你的数据库逻辑
    result = execute_sql(sql)
    return str(result)

@register_tool(description="发送邮件")
def send_email(to: str, subject: str, body: str) -> str:
    # 邮件逻辑
    send_mail(to, subject, body)
    return "Email sent"

@register_tool(description="调用内部API")
def call_api(endpoint: str, params: str) -> str:
    response = requests.post(endpoint, json=eval(params))
    return response.text
```

## 场景5: 自定义压缩策略

```python
from compaction import CompactionStrategy
from memory import Message
from typing import List

class SmartCompaction(CompactionStrategy):
    def __init__(self, llm_summarize_fn):
        self.llm_summarize_fn = llm_summarize_fn
    
    def compact(self, messages: List[Message], target_tokens: int):
        # 保留最近10条
        recent = messages[-10:]
        old = messages[:-10]
        
        if not old:
            return recent
        
        # 用LLM总结旧消息
        old_text = "\n".join([f"{m.role}: {m.content}" for m in old])
        summary = self.llm_summarize_fn(old_text)
        
        summary_msg = Message('system', f"[Summary]\n{summary}")
        return [summary_msg] + recent

# 使用
def summarizer(text):
    # 调用小模型总结
    return your_summarize_api(text)

strategy = SmartCompaction(summarizer)
harness = AgentHarness(
    model_fn=your_model,
    compaction_strategy=strategy
)
```

## 场景6: 多轮复杂任务

```python
harness = AgentHarness(model_fn=your_model)
session_id = harness.create_session()

# 第一轮：理解需求
harness.run("我想分析一下我的日志文件，找出所有错误")

# 第二轮：具体操作
harness.run("日志在 /var/log/app.log")

# 第三轮：后续处理
harness.run("帮我把这些错误分类统计")

# 保存会话供以后继续
harness.memory.save_session()

# 下次继续
harness.resume(session_id)
harness.run("继续刚才的分析")
```

## 场景7: 批量处理

```python
tasks = [
    "帮我分析文件A",
    "计算数据B的统计信息",
    "生成报告C"
]

harness = AgentHarness(model_fn=your_model)

for task in tasks:
    session_id = harness.create_session()
    result = harness.run(task)
    
    # 保存结果
    with open(f"result_{session_id}.txt", "w") as f:
        f.write(result)
```

## 场景8: 流式输出

```python
class StreamingModel:
    def __init__(self, api_client):
        self.client = api_client
    
    def __call__(self, messages):
        full_response = ""
        for chunk in self.client.stream(messages):
            content = chunk['choices'][0]['delta'].get('content', '')
            print(content, end='', flush=True)
            full_response += content
        print()  # 换行
        return full_response

harness = AgentHarness(model_fn=StreamingModel(your_client))
harness.run("写一个长故事", stream=True)
```

## 场景9: 错误处理和重试

```python
def robust_model(messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            return your_api_call(messages)
        except Exception as e:
            if attempt == max_retries - 1:
                return f"Error after {max_retries} attempts: {e}"
            time.sleep(2 ** attempt)  # 指数退避

harness = AgentHarness(model_fn=robust_model)
```

## 场景10: 集成到Web服务

```python
from flask import Flask, request, jsonify
from harness import AgentHarness

app = Flask(__name__)

# 每个用户一个harness实例（简化示例）
user_harnesses = {}

@app.route('/chat', methods=['POST'])
def chat():
    user_id = request.json['user_id']
    message = request.json['message']
    
    # 获取或创建harness
    if user_id not in user_harnesses:
        harness = AgentHarness(model_fn=your_model)
        harness.create_session()
        user_harnesses[user_id] = harness
    
    harness = user_harnesses[user_id]
    response = harness.run(message)
    
    return jsonify({
        'response': response,
        'stats': harness.get_stats()
    })

@app.route('/sessions', methods=['GET'])
def list_sessions():
    user_id = request.args.get('user_id')
    harness = user_harnesses.get(user_id)
    
    if not harness:
        return jsonify([])
    
    sessions = harness.memory.list_sessions()
    return jsonify(sessions)
```

## 常见配置

### 小模型配置（7B以下）
```python
harness = AgentHarness(
    model_fn=your_model,
    max_tokens=4000,      # 较小上下文
    max_iterations=5,     # 减少迭代次数
    compaction_strategy=SlidingWindowCompaction()  # 简单策略
)
```

### 大模型配置（70B以上）
```python
harness = AgentHarness(
    model_fn=your_model,
    max_tokens=32000,     # 大上下文
    max_iterations=20,    # 更多迭代
    compaction_strategy=HybridCompaction(keep_first=5, keep_last=15)
)
```

### 生产环境配置
```python
# 自定义工具注册表（白名单）
safe_registry = ToolRegistry()
safe_registry.register(name="calculator")(calculator)
safe_registry.register(name="read_file")(safe_read_file)  # 带路径限制的版本

harness = AgentHarness(
    model_fn=your_model,
    session_dir="/data/sessions",  # 持久化目录
    tool_registry=safe_registry,   # 安全的工具集
    compaction_strategy=HybridCompaction()
)
```

## 调试技巧

### 1. 打印上下文
```python
context = harness.memory.get_context()
print(f"Context size: {len(context)} messages")
for msg in context:
    print(f"[{msg['role']}] {msg['content'][:50]}...")
```

### 2. 查看工具调用
```python
tool_msgs = harness.memory.get_messages(role='tool')
for msg in tool_msgs:
    print(f"Tool: {msg.metadata.get('tool_name')}")
    print(f"Result: {msg.content}")
```

### 3. 检查压缩
```python
print(f"Token count: {harness.memory.count_tokens()}")
print(f"Compaction count: {harness.stats['compaction_count']}")
```
