import os
import json
from pathlib import Path

import openai
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(


    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def add(a, b):
    return (a + b)


def read_note(filename):
    base = (Path(__file__).parent / "notes").resolve()
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
            "name":"add",
            "description":"计算两个数的和，当用户需要进行两个数相加的时候调用",
            "parameters": {
                "type": "object",
                "properties":{
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],


            },
        }
    },
    {
        "type":"function",
        "function":{
            "name":"read_note",
            "description":"读取notes目录下的文件的内容，当用户询问文件内容的时候调用",
            "parameters":{
                "type":"object",
                "properties":{
                    "filename":{"type":"string"}
                },
                "required":["filename"]
            }

        }
    }
]
TOOL_MAPS = {"add":add, "read_note":read_note}
MAX_STEPS = 5
MODEL = "deepseek-chat"

messages = [{"role":"user", "content":"帮我算一下aaa.md里两个数的总和"}]

step = 0

while step < MAX_STEPS:
    step += 1

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
    )

    choice = resp.choices[0]
    msg = choice.message


    messages.append({
        "role": "assistant",
        "content": msg.content or "",
        **({"tool_calls": [{
            "id": tc.id,
            "type":"function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments
            }
        }
            for tc in msg.tool_calls
        ]} if msg.tool_calls else {})
    }
    )

    if not msg.tool_calls:
        print(msg.content)
        break

    for c in msg.tool_calls:
        args = json.loads(c.function.arguments)
        fn = TOOL_MAPS.get(c.function.name)

        if fn is None:
            result = f"错误：没有名为 {c.function.name} 的工具"
        else:
            result = fn(**args)
        messages.append({
            "role": "tool",
            "tool_call_id": c.id,
            "content": str(result)
        })


for i, m in enumerate(messages):
    print(i, m["role"], str(m.get("content"))[:40], "tool_calls" in m)


if resp is None:
    print(f"[未完成] {MAX_STEPS} 步内没能拿到响应，最后一次错误见上")
else:
    print("finish_reason:", resp.choices[0].finish_reason)




