import os
import json
from datetime import datetime
from pathlib import Path

import openai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

def estimate_tokens(text:str):
    return int(len(text)/1.5) + 1

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

def trim_by_tokens(max_tokens: int= 6000):
    total = sum(estimate_tokens(msg.get("content" or "")) for msg in messages)
    print(f"裁剪前tokens:{total}")
    if total < max_tokens:
        return
    acc, start = 0, len(messages)
    for i in range(len(messages)-1,-1,-1):
        acc += estimate_tokens(messages[i].get("content" or ""))
        if acc > max_tokens:
            break
        start = i

    while start < len(messages) and messages[start]["role"] != "user":
        start += 1

    if start >= len(messages):
        for j in range(len(messages) - 1, -1, -1):
            if messages[j]["role"] == "user":
                start = j
                break
        print("预算不足，已放宽一次以保住结构")
    kept = messages[start:]
    messages[:] = kept
    new_total = sum(estimate_tokens(msg.get("content" or "")) for msg in messages)
    print(f"裁剪后tokens:{new_total}")

def is_context_overflow(err_msg: str) -> bool:
    """判断 BadRequestError 的信息是不是“上下文超限”"""
    m = err_msg.lower()
    return any(keyword in m for keyword in ("context", "length", "maximum", "too long", "tokens"))


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

MODEL = "deepseek-chat"          # 正常运行的模型名

# ===== 伪造超限自测：需要验证 except 降级分支时，取消下面两行注释 =====
# is_context_overflow = lambda _: True   # 让任何 400 都被判定为“上下文超限”
# MODEL = "no-such-model"                 # 用一个不存在的模型名，制造一次 BadRequestError


def degrade_to_recent(n: int = 4):
    """砍到最近 n 条，但必须保证首条是 user"""
    messages[:] = messages[-n:]

resp = None
while step < MAX_STEPS:
    step += 1
    trim_by_tokens(6000)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
    except openai.BadRequestError as e:
        if is_context_overflow(str(e)):
            print("[降级] 上下文超限，只保留最近 4 条，重试一次")
            degrade_to_recent(4)
            continue  # ← 回到 while 顶部重试
        else:
            print(f"[参数错误] {e}")
            break  # ← 重试无用，退出
    except openai.APIConnectionError as e:
        print(f"[网络] {e}")
        break

    msg = resp.choices[0].message

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

if resp is None:
    print(f"[未完成] {MAX_STEPS} 步内没能拿到响应，最后一次错误见上")
else:
    print("finish_reason:", resp.choices[0].finish_reason)
print(is_context_overflow("This model's maximum context length is 65536 tokens"))  # True
print(is_context_overflow("Invalid model name"))                                    # False
# print("\n===== 防御自测（不经过模型）=====")
# for name in ["aaa.md", "../../.env", "../tool_calling.py",
#              "/etc/passwd", "notes/../../.env"]:
#     print(f"{name:24} → {read_note(name)[:60]}")

#
#
# trim_by_tokens(300)
# for m in messages:
#     print(m["role"], len(m.get("content") or ""), "tool_calls" in m)