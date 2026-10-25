import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"
TASK = "把「我今天加班到十点」改写成上海阿姨口吻，只回一句，不要解释。"

def call(messages, label):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,          # ← 关键：让差异只来自配置，不来自随机
    )
    text = resp.choices[0].message.content
    print(f"\n===== {label} =====")
    print(text)
    return text

# A：只有 system
A = [
    {"role": "system", "content": """你是上海阿姨，说话带"侬"，不解释，只回一句话"""},
    {"role": "user",   "content": TASK},
]

# B：只有 user，把身份塞进 user 里
B = [
    {"role": "user", "content": """你是一个上海阿姨，""" + TASK},
]

# C：A + 一组示例
C = [
    {"role": "system", "content": """你是上海阿姨，说话带"侬"，不解释，只回一句话"""},
    {"role": "user",      "content": "把「这个菜太咸了」改写成上海阿姨口吻，只回一句"},
    {"role": "assistant", "content": """侬这个菜啊咸死我嘞"""},
    {"role": "user",      "content": TASK},
]

for label, msgs in [("A", A), ("B", B), ("C", C)]:
    call(msgs, label)