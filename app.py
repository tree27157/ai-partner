import uuid
from pathlib import Path

import streamlit as st
import os
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError, BadRequestError
from dotenv import load_dotenv
from datetime import datetime
import json

from streamlit import session_state

load_dotenv()
MAX_STEPS = 5
# MAX_RETRIES = 3
print("-------------->重新执行此文件，渲染展示页面")

# 设置页面配置
st.set_page_config(
    page_title="AI智能伴侣",
    page_icon="🤖",

    layout="wide",

    initial_sidebar_state="expanded",
    menu_items={}
)

#工具函数
def get_time():
    now = datetime.now()
    s = now.strftime("%Y-%m-%d %H:%M:%S")
    return s

def add(a, b):
    return a + b

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


# 保存会话信息函数
def save_session():
    # 1.保存当前会话
    if not st.session_state.get("messages"):
        return
    if st.session_state.current_session:
        # 构建新的会话对象
        session_data = {
            "session_id": st.session_state.current_session,
            "created_at": st.session_state.created_at,
            # 显示名默认 null：只有用户改过名才有值，展示时由 created_at 格式化
            "display_name": st.session_state.display_name,
            "nick_name": st.session_state.nick_name,
            "nature": st.session_state.nature,
            "messages": st.session_state.messages
        }

        # 如果session目录不存在，创建它
        if not os.path.exists("sessions"):
            os.mkdir("sessions")

        # 保存会话数据
        with open(f"sessions/{st.session_state.current_session}.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

#解析会话的创建时间：新文件读字段，旧文件从文件名/修改时间兜底
def resolve_created_at(session_id, path, data):
    created_at = data.get("created_at")
    if created_at:
        return created_at
    try:
        # 旧文件名就是 "%Y-%m-%d %H:%M:%S" 格式的时间戳
        return datetime.strptime(session_id, "%Y-%m-%d %H:%M:%S").isoformat()
    except ValueError:
        # 最后兜底：文件修改时间
        return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()

#会话显示文本：有 display_name 用它，没有就把 created_at 格式化（存原始数据，展示时才格式化）
def format_session_label(display_name, created_at, session_id):
    if display_name:
        return display_name
    raw = created_at or session_id  # 旧文件连 created_at 都没有时回退到文件名
    try:
        return datetime.fromisoformat(raw).strftime("%m-%d %H:%M:%S")
    except ValueError:
        return raw

#加载所有的会话列表信息
def load_sessions():
    session_list = []
    if os.path.exists("sessions"):
        for filename in os.listdir("sessions"):
            if not filename.endswith(".json"):
                continue
            session_id = filename[:-5]
            path = f"sessions/{filename}"
            # 只收集原始字段：display_name 可能为 None，排序只用 created_at
            display_name = None
            created_at = ""
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                display_name = data.get("display_name")
                created_at = resolve_created_at(session_id, path, data)
            except Exception as e:
                print(f"[load_sessions] 读取 {filename} 失败：{type(e).__name__}: {e}")
                created_at = resolve_created_at(session_id, path, {})
            session_list.append({"session_id": session_id, "display_name": display_name, "created_at": created_at})

    # ISO 8601 的字典序 = 时间顺序，直接比字符串就够，不用转成 datetime；
    # 微秒精度可以分开同一秒内创建的多个会话
    session_list.sort(key=lambda s: s["created_at"], reverse=True)
    return session_list
#加载指定会话信息函数
def load_session(session_id):
    try:
        path = f"sessions/{session_id}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
                st.session_state.messages = session_data["messages"]
                st.session_state.nick_name = session_data["nick_name"]
                st.session_state.nature = session_data["nature"]
                # st.session_state.current_session = session_data["current_session"]
                # 主键只认文件名；旧文件里的 current_session 字段是时间戳，不再依赖
                st.session_state.current_session = session_id
                # display_name 是可选字段：没重命名过就是 None，展示交给 format_session_label
                st.session_state.display_name = session_data.get("display_name")
                # 创建时间用于排序：旧文件没有该字段时从文件名/修改时间兜底
                st.session_state.created_at = resolve_created_at(session_id, path, session_data)

    except Exception as e:
        st.error(f"会话加载失败：{type(e).__name__}: {e}")

#删除指定会话信息函数
def delete_session(session_id, label):
    try:
        path = f"sessions/{session_id}.json"
        if os.path.exists(path):
            os.remove(path)
            st.success(f"会话 {label} 删除成功")
            # 如果删除的是当前会话，则清空当前会话信息
            if session_id == st.session_state.current_session:
                start_new_session()
        else:
            st.error(f"会话 {label} 不存在")
    except Exception as e:
        st.error(f"会话 {label} 删除失败：{type(e).__name__}: {e}")


##生成会话主键（uuid4：唯一、稳定、不可读也没关系）
def generate_session_name():
    return str(uuid.uuid4())

#生成当前时间的 ISO 原始值（可排序、可逆解析；微秒用来区分同一秒内建的多个会话）
def now_iso():
    return datetime.now().isoformat(timespec="microseconds")

#初始化收敛函数
def start_new_session():
    st.session_state.messages = []
    st.session_state.current_session = generate_session_name()
    st.session_state.display_name = None
    st.session_state.created_at = now_iso()


#工具列表
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

TOOL_MAP = {"get_time": get_time, "read_note": read_note, "add":add}


def estimate_tokens(text:str):
    return int(len(text)/1.5) + 1

def trim_by_tokens(max_tokens: int= 6000):
    total = sum(estimate_tokens(msg.get("content" or "")) for msg in st.session_state.messages)
    print(f"裁剪前tokens:{total}")
    if total < max_tokens:
        return
    acc, start = 0, len(st.session_state.messages)
    for i in range(len(st.session_state.messages)-1,-1,-1):
        acc += estimate_tokens(st.session_state.messages[i].get("content" or ""))
        if acc > max_tokens:
            break
        start = i

    while start < len(st.session_state.messages) and st.session_state.messages[start]["role"] != "user":
        start += 1

    if start >= len(st.session_state.messages):
        for j in range(len(st.session_state.messages) - 1, -1, -1):
            if st.session_state.messages[j]["role"] == "user":
                start = j
                break
        print("预算不足，已放宽一次以保住结构")
    kept = st.session_state.messages[start:]
    st.session_state.messages[:] = kept
    new_total = sum(estimate_tokens(msg.get("content" or "")) for msg in st.session_state.messages)
    print(f"裁剪后tokens:{new_total}")

#单条截断
def clip_tool_result(text, limit: int = 2000) -> str:
    s = str(text)
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n\n…（内容过长已截断，原长 {len(s)} 字符）"


# 大标题
st.title("AI智能伴侣")

#
# st.logo("./resource/picture1.webp")

#系统提示词
system_prompt = """
    你叫%s，现在是我的小跟班，请完全带入伴侣角色。
    规则：
        1.每次只回1条消息
        2.禁止任何场景或状态描述性文字
        3.匹配用户语言
        4.回复简短，像聊天一样
        5.称呼用户为树哥
        6.用符合跟班性格的方式对话
        7.回复的内容，要充分体现性格特征
        8. 需要获取当前时间、读取文件内容、做数字计算时，必须调用对应工具，不要自己猜测或编造结果。
    伴侣性格：
        - %s
    你必须遵守上述规则来回复用户
"""


#昵称
if "nick_name" not in st.session_state:
    st.session_state.nick_name = "大肥鱼"

#性格
if "nature" not in st.session_state:
    st.session_state.nature = "傲娇可爱的台湾妹子"

#初始化会话信息
if "current_session" not in st.session_state:
    start_new_session()


#展示聊天信息
st.text(f"会话名称：{format_session_label(session_state.display_name, session_state.created_at, session_state.current_session)}")
for message in st.session_state.messages:
    # 1. 只画 user 和 assistant（tool 消息不该显示成气泡）
    if message["role"] not in ("user", "assistant"):
        continue
    # 2. 内容为空的 assistant（只有 tool_calls 的那种）也不画
    if not message.get("content"):
        continue
    st.chat_message(message["role"]).write(message["content"])


#调用AI大模型
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")



#侧边栏

with st.sidebar:
    #会话信息
    st.subheader("AI控制面板")

    #新建会话按钮
    if st.button("新建会话", width="stretch", icon="✏️"):
        # 1.保存当前会话
        save_session()

        # 2.创建新会话：换新主键与创建时间，显示名留空（等用户重命名再填）
        start_new_session()
        st.rerun()

    #会话历史
    st.text("会话历史")
    session_list = load_sessions()
    if not session_list:
        st.text("暂无会话记录")
    for s in session_list:
        session_id = s["session_id"]
        # 展示时才格式化：display_name 为空就用 created_at 转成 "1023 18:05"
        label = format_session_label(s["display_name"], s["created_at"], session_id)
        col1, col2 = st.columns([4, 1])
        # 加载会话按钮（label 给人看，key 用 uuid 保证唯一）
        with col1:
            if st.button(label, width="stretch", icon="📃", key=f"load_{session_id}",
                         type="primary" if session_id == st.session_state.current_session else "secondary"):
                load_session(session_id)
                st.rerun()
        # 删除会话按钮
        with col2:
            if st.button("", width="stretch", icon="❌", key=f"delete_{session_id}"):
                delete_session(session_id, label)
                st.rerun()


#分隔线
    st.divider()

    st.subheader("伴侣信息")
    #昵称输入框
    nick_name = st.text_input("昵称", placeholder="请输入伴侣的昵称", value=st.session_state.nick_name)
    if nick_name:
        st.session_state.nick_name = nick_name
    #性格输入框
    nature = st.text_area("性格", placeholder="请输入伴侣的性格", value=st.session_state.nature)
    if nature:
        st.session_state.nature = nature

prompt = st.chat_input("请输入你的问题")
#裁剪对话历史，如果对话历史超过十轮，那么从对话历史里将最早的两条对话裁剪出去
# while len(st.session_state.messages) > MAX_MESSAGES:
#     st.session_state.messages.pop(0)
#     st.session_state.messages.pop(0)

def build_messages():
    return [
        {"role": "system", "content": system_prompt % (st.session_state.nick_name, st.session_state.nature)},
        *st.session_state.messages,
    ]


def check_and_fix_messages():
    """
        检查并修复 messages 的两条结构不变量，返回发现的问题。
        1. 首条必须是 user
        2. assistant 的每个 tool_call 必须有配对的 tool 回复；孤立的 tool 消息必须删掉
        用 if + 日志降级，不用 assert（python -O 会删掉 assert）
        """
    problems = []
    msgs = st.session_state.messages
    print("  [检查前]", [(m["role"], bool(m.get("tool_calls"))) for m in msgs])

    idx = 0
    while idx < len(msgs) and msgs[idx]["role"] != "user":
        problems.append(f"丢弃开头 {msgs[idx]['role']} 消息")
        idx += 1

    kept = []
    for m in msgs[idx:]:
        if m["role"] == "tool":
            tid = m.get("tool_call_id")
            has_call = any(
                k["role"] == "assistant"
                and any(tc["id"] == tid for tc in k.get("tool_calls", []))
                for k in kept
            )
            if not has_call:
                problems.append(f"丢弃孤立 tool 消息（id={tid}）")
                continue
        kept.append(m)

    answered = {m.get("tool_call_id") for m in kept if m["role"] == "tool"}
    repaired = []
    for m in list(kept):
        repaired.append(m)
        if m["role"] == "assistant":
            for tc in m.get("tool_calls", []):
                if tc["id"] not in answered:
                    problems.append(f"补占位 tool 回复（id={tc['id']}）")
                    repaired.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": "该工具调用已被系统跳过，不要重试。请基于已有信息直接回答用户。",
                    })
    kept = repaired
    msgs[:] = kept
    print("  [检查后]", [(m["role"], bool(m.get("tool_calls"))) for m in msgs])

    if problems:
        print("[结构告警]", problems)
    return problems


if prompt:
    print("-------------->调用AI大模型，提示词", prompt)

    #保存用户输入的提示词
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)



    try:
        for step in range(1, MAX_STEPS + 1):
            trim_by_tokens()
            problems = check_and_fix_messages()  
            if problems:
                st.warning(f"对话结构已自动修复：{problems[0]}")

            print(f"--- 第 {step} 轮，共 {len(st.session_state.messages)} 条 ---")
            for i, m in enumerate(st.session_state.messages):
                print(i, m["role"], "TC" if m.get("tool_calls") else "", str(m.get("content"))[:40])

            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=build_messages(),
                tools = tools,
                stream=True,
                # reasoning_effort="high",
                # extra_body={"thinking": {"type": "enabled"}}
            )

            content_acc = ""
            tool_calls_acc = {}

            ph = None
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    content_acc += delta.content  # 攒正文
                    if ph is None:  # 第一次有内容才创建
                        bubble = st.chat_message("assistant")
                        ph = st.empty()
                    ph.write(content_acc)  # 后续每次覆盖同一个位置
                for tc in (delta.tool_calls or []):
                    slot = tool_calls_acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if tc.id: slot["id"] = tc.id
                    if tc.function and tc.function.name: slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments: slot["arguments"] += tc.function.arguments


            assistant_msg = {"role": "assistant", "content": content_acc}
            if tool_calls_acc:
                assistant_msg["tool_calls"] = [
                    {"id": s["id"], "type": "function",
                     "function": {"name": s["name"], "arguments": s["arguments"]}}
                    for s in tool_calls_acc.values()
                ]
            st.session_state.messages.append(assistant_msg)

            if not assistant_msg.get("tool_calls"):
                break

            for call in assistant_msg.get("tool_calls", []):
                args = json.loads(call["function"]["arguments"])
                fn = TOOL_MAP.get(call["function"]["name"])
                if fn is None:
                    result = f"错误：没有名为 {call['function']['name']} 的工具"
                else:
                    try:
                        result = fn(**args)
                    except Exception as e:
                        result = f"工具执行失败：{type(e).__name__}: {e}"

                st.caption(f"🔧 {call['function']['name']} → {str(result)[:40]}")

                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": clip_tool_result(result,1000),
                })
        else:
            # 循环没被 break 打断 = 5 轮都用完了
            st.warning(f"已达到最大步数 {MAX_STEPS}，任务未完成，已停止")


        print(f"打印会话长度:{len(st.session_state.messages)}")
        print(f"打印第一条对话角色：{st.session_state.messages[0]['role']}")
        print(f"打印最后一条对话角色：{st.session_state.messages[-1]['role']}")

        # 保存当前会话
        save_session()

    except AuthenticationError as e:
        # 401：重试一万次也没用，必须改 key
        print(f"[auth] type={type(e).__name__} msg={e}")
        st.error("API Key 无效或已过期，请检查 .env 里的 DEEPSEEK_API_KEY")
        # 回滚：移除刚才 append 进去的 user 消息
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")

    except BadRequestError as e:
        # 400：参数/代码写错，重试没意义
        print(f"[bad-request] type={type(e).__name__} msg={e}")
        st.error("请求参数有误（模型名或消息格式等配置问题），请检查代码")
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")

    except RateLimitError as e:
        # 429：限流或额度耗尽，等一会儿再试，别硬冲
        print(f"[rate-limit] type={type(e).__name__} msg={e}")
        st.error("请求太频繁或额度用完了，等一会儿再试")
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")

    except APITimeoutError as e:
        # 超时是 APIConnectionError 的子类，必须排在父类前面才进得来
        print(f"[timeout] type={type(e).__name__} msg={e}")
        st.error("请求超时了，稍后再试试")
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")


    except APIConnectionError as e:
        # 连不上：断网、base_url 写错等（SDK 内部已自动重试过，这里是兜底）
        print(f"[connection] type={type(e).__name__} msg={e}")
        st.error("连不上 DeepSeek，检查网络后重试")
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")

    except Exception as e:
        # 兜底：未知错误，必须放最后，否则前面的分支全成死代码
        print(f"[unknown] type={type(e).__name__} msg={e}")
        st.error(f"未知错误：{type(e).__name__}: {e}")
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
            print("回滚后条数:", len(st.session_state.messages), "末条:",
                  st.session_state.messages[-1]["role"] if st.session_state.messages else "空")
    else:
        st.rerun()