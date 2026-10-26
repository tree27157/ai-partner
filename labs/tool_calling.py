import os
import json
from datetime import datetime

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

tools = [{
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
}]

messages = [
    {"role": "user", "content": "今天是星期几？"},
]


response = client.chat.completions.create(
    model = "deepseek-chat",
    messages = messages,
    tools = tools,
)

# print(json.dumps(tools, ensure_ascii=False, indent=2))

choice = response.choices[0]
# choice.finish_reason
msg = choice.message
# msg.content
# msg.tool_calls
# tc.id
# tc.function.name
# tc.function.arguments
if choice.finish_reason != "tool_calls":
    print(msg.content)
else:
    tc = msg.tool_calls[0]
    messages.append(
        {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]
        }
    )

    result = json.loads(tc.function.arguments)
    content_str = get_time()

    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": content_str
    })
    print("原始 arguments:", repr(tc.function.arguments))  # 用 repr 才看得出它是字符串

for i, m in enumerate(messages):
    print(i, m["role"], str(m.get("content"))[:40], "tool_calls" in m)

second_resp = client.chat.completions.create(
    model="deepseek-chat",
    messages = messages,
    tools = tools,
)
print(second_resp.choices[0].message.content)
print("finish_reason:", choice.finish_reason)
