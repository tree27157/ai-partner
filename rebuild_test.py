import uuid

import streamlit as st
import os
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError, BadRequestError
from dotenv import load_dotenv
from datetime import datetime
import json

from streamlit import session_state

env_file = ".env.broken" if os.getenv("USE_BROKEN_KEY") else ".env"
load_dotenv(env_file,override=True)

MAX_MESSAGES = 20
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

# 保存会话信息函数
def save_session():
    # 1.保存当前会话
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
    # if os.path.exists("sessions"):
    #     file_list = os.listdir("sessions")
    #     for filename in file_list:
    #         if filename.endswith(".json"):
    #             session_list.append(filename[:-5])
    # session_list.sort(reverse=True)
    # return session_list
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
                st.session_state.messages = []
                st.session_state.current_session = generate_session_name()
                st.session_state.display_name = None
                st.session_state.created_at = now_iso()
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


#加载所有会话列表
# def load_session_list():
#     session_list = []
#     #加载session目录下的文件
#     if os.path.exists("sessions"):
#         file_list = os.listdir("sessions")
#         for filename in file_list:
#             if filename.endswith(".json"):
#                 session_list.append(filename[:-5])
#         session_list.sort()
#         return session_list

def trim_history():
    print(f"开始裁剪历史裁剪前条数：{len(st.session_state.messages)}")
    msgs = st.session_state.messages
    max_msgs = MAX_MESSAGES - 2
    if len(msgs) < max_msgs:
        return
    kept = msgs[-max_msgs:]
    while kept[0]["role"] != "user":
        kept.pop(0)
    st.session_state.messages = kept
    print(f"裁剪后条数为{len(kept)}")





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
    伴侣性格：
        - %s
    你必须遵守上述规则来回复用户
"""

#初始化聊天信息
if "messages" not in st.session_state:
    st.session_state.messages = []

#昵称
if "nick_name" not in st.session_state:
    st.session_state.nick_name = "大肥鱼"

#性格
if "nature" not in st.session_state:
    st.session_state.nature = "幽默毒舌的台湾妹子"

#会话标识（uuid 主键，决定文件名）
if "current_session" not in st.session_state:
    st.session_state.current_session = generate_session_name()

#会话显示名（可选：只有重命名后才有值，默认 None，展示时由 created_at 格式化）
if "display_name" not in st.session_state:
    st.session_state.display_name = None

#会话创建时间（ISO 原始值：既是排序依据，也是展示的数据来源）
if "created_at" not in st.session_state:
    st.session_state.created_at = now_iso()

#展示聊天信息
st.text(f"会话名称：{format_session_label(session_state.display_name, session_state.created_at, session_state.current_session)}")
for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])



#调用AI大模型
print("key 是否为空:", os.environ.get("DEEPSEEK_API_KEY") is None)
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
        st.session_state.messages = []
        st.session_state.current_session = generate_session_name()
        st.session_state.display_name = None
        st.session_state.created_at = now_iso()
        save_session()
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

if prompt:
    st.chat_message("user").write(prompt)
    print("-------------->调用AI大模型，提示词", prompt)

    trim_history()

    #保存用户输入的提示词
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {"role": "system", "content": system_prompt % (st.session_state.nick_name, st.session_state.nature)},
                *st.session_state.messages
            ],
            stream=True,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )

        # 非流式输出结果
        # print("<--------------大模型返回结果", response.choices[0].message.content)
        # st.chat_message("assistant").write(response.choices[0].message.content)

        # 流式输出结果

        # 创建一个空的ChatMessage组件
        response_message = st.empty()

        full_response = ""
        for chunk in response:
            if chunk and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                response_message.chat_message("assistant").write(full_response)

        # print(len(st.session_state.messages))
        # 保存大模型返回的结果
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        print(f"打印会话长度:{len(st.session_state.messages)}")
        print(f"打印第一条对话角色：{st.session_state.messages[0]['role']}")
        print(f"打印最后一条对话角色：{st.session_state.messages[-1]['role']}")

        # 保存当前会话
        save_session()

    except AuthenticationError as e:
        #401
        print(f"[auth] type={type(e).__name__} msg={e}")
        st.error("API验证出错，请重新匹配")
        if session_state.messages and session_state.messages[-1]["role"] == ["user"]:
            st.session_state.messages.pop(-1)
            print(f"回滚后条数：{len(st.session_state.messages)},末条：{st.session_state.messages[-1]["role"]}:{st.session_state.messages[-1]["content"]}")

    except ValueError as e:
        print(f"[value] type={type(e).__name__} msg={e}")
        st.error("参数错误")
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