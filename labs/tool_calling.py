import os
import json
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def get_time():
    now = datetime.now()
    s = now.strftime("%Y-%m-%d %H:%M:%S")
    return s

def add(a, b):
    return a + b

def read_note(filename):
    base = Path("../notes").resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        return "错误：只能读取 notes/ 目录下的文件"
    if not target.exists():
        return f"错误：文件 {filename} 不存在"
    try:
        with open(target, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        return f"错误：读取文件失败，{e}"


tools = [
    {
    "type":"function",
    "function":{
        "name":"get_time",
        "description":"获取当前日期和时间，当用户询问现在是几点钟、今天几号、星期几的时候调用。",
        "parameters":{
            "type":"object",
            "properties":{},
            "required":[],
        }
    }
},
    {
    "type":"function",
    "function":{
        "name":"read_note",
        "description":"读取notes目录下的文件，当用户要询问文件的时候调用。",
        "parameters":{
            "type":"object",
            "properties":{
                "filename":{"type":"string"}
            },
            "required":["filename"]
        }
    }
},
    {
    "type":"function",
        "function":{
        "name":"add",
        "description":"对两个数字进行加法运算，当用户需要进行加法运算时调用。",
        "parameters":{
            "type":"object",
            "properties":{
                "a":{"type":"number"},
                "b":{"type":"number"}
            },
            "required":["a", "b"]
        }
    }
}
]

messages = [
    {"role": "user", "content": "帮我算一下文件aaa.md里这两个数的和"},
]

TOOL_MAP = {"get_time": get_time, "read_note": read_note, "add":add}
MAX_STEPS = 5
step = 0
while step < MAX_STEPS:
    resp = client.chat.completions.create(
    model = "deepseek-chat",
    messages = messages,
    tools = tools,
)

    msg = resp.choices[0].message
    step += 1

    messages.append({
        "role": "assistant",
        "content": msg.content or "",
        **({"tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in msg.tool_calls
        ]}
           if msg.tool_calls else {}),
    })

    if not msg.tool_calls:
        print(msg.content)
        break

    for call in msg.tool_calls:
        args = json.loads(call.function.arguments)
        fn = TOOL_MAP.get(call.function.name)
        if fn is None:
            result = f"错误：没有名为 {call.function.name} 的工具"
        else:
            result = fn(**args)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": str(result)
        })

for i, m in enumerate(messages):
    print(i, m["role"], str(m.get("content"))[:40], "tool_calls" in m)


# print(json.dumps(tools, ensure_ascii=False, indent=2))
# choice = response.choices[0]
# choice.finish_reason
# msg = choice.message
# msg.content
# msg.tool_calls
# tc.id
# tc.function.name
# tc.function.arguments

print("finish_reason:", resp.choices[0].finish_reason)
# print("\n===== 防御自测（不经过模型）=====")
# for name in ["aaa.md", "../../.env", "../tool_calling.py",
#              "/etc/passwd", "notes/../../.env"]:
#     print(f"{name:24} → {read_note(name)[:60]}")