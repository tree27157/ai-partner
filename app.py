from pyexpat.errors import messages

import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import json

from streamlit import session_state

load_dotenv()
MAX_MESSAGES = 20
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
            "nick_name": st.session_state.nick_name,
            "nature": st.session_state.nature,
            "current_session": st.session_state.current_session,
            "messages": st.session_state.messages
        }

        # 如果session目录不存在，创建它
        if not os.path.exists("sessions"):
            os.mkdir("sessions")

        # 保存会话数据
        with open(f"sessions/{st.session_state.current_session}.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

#加载所有的会话列表信息
def load_sessions():
    session_list = []

    if os.path.exists("sessions"):
        file_list = os.listdir("sessions")
        for filename in file_list:
            if filename.endswith(".json"):
                session_list.append(filename[:-5])
    session_list.sort(reverse=True)
    return session_list

#加载指定会话信息函数
def load_session(session_name):
    try:
        if os.path.exists(f"sessions/{session_name}.json"):
            with open(f"sessions/{session_name}.json", "r", encoding="utf-8") as f:
                session_data = json.load(f)
                st.session_state.messages = session_data["messages"]
                st.session_state.nick_name = session_data["nick_name"]
                st.session_state.nature = session_data["nature"]
                st.session_state.current_session = session_data["current_session"]
    except Exception:
        st.error(f"会话 {session_name} 加载失败")

#删除指定会话信息函数
def delete_session(session_name):
    try:
        if os.path.exists(f"sessions/{session_name}.json"):
            os.remove(f"sessions/{session_name}.json")
            st.success(f"会话 {session_name} 删除成功")
            #如果删除的是当前会话，则清空当前会话信息
            if session_name == st.session_state.current_session:
                st.session_state.messages = []
                st.session_state.current_session = generate_session_name()
        else:
            st.error(f"会话 {session_name} 不存在")
    except Exception:
        st.error(f"会话 {session_name} 删除失败")


   #生成会话标识函数
def generate_session_name():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#加载所有会话列表
def load_session_list():
    session_list = []
    #加载session目录下的文件
    if os.path.exists("sessions"):
        file_list = os.listdir("sessions")
        for filename in file_list:
            if filename.endswith(".json"):
                session_list.append(filename[:-5])
        session_list.sort()
        return session_list

def trim_history():
    msgs = st.session_state.messages
    max_msgs = MAX_MESSAGES - 2

    if len(msgs) <= max_msgs:
        return
    kept = msgs[-max_msgs:]
    while kept and kept[0]["role"]!="user":
        kept.pop(0)
    st.session_state.messages = kept


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

#会话标识
if "current_session" not in st.session_state:
    st.session_state.current_session = generate_session_name()

#展示聊天信息
st.text(f"会话名称：{session_state.current_session}")
for message in st.session_state.messages:
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

        # 2.创建新会话
        if st.session_state.messages:
            st.session_state.messages = []
            st.session_state.current_session = generate_session_name()
            save_session()
            st.rerun()

    #会话历史
    st.text("会话历史")
    session_list = load_sessions()
    if not session_list:
        st.text("暂无会话记录")
    for session in session_list:
        # st.button(session, width="stretch", icon="📃")
        # st.button("删除", width="stretch", icon="❌")
        col1,col2 = st.columns([4,1])
        # 加载会话按钮
        with col1:
            #三元运算符
            if st.button(session, width="stretch", icon = "📃", key=f"load_{session}", type="primary" if session == st.session_state.current_session else "secondary"):
                load_session(session)
                st.rerun()
        # 删除会话按钮
        with col2:
            if st.button("", width="stretch", icon="❌", key=f"delete_{session}"):
                delete_session(session)
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
    
    #创建一个空的ChatMessage组件
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
