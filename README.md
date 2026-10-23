# AI 智能伴侣

基于 DeepSeek API 的多轮对话聊天应用，Streamlit 界面。

## 功能

- 多轮对话，上下文自动裁剪至 20 条以内
- 流式输出，逐字显示
- 会话持久化：可新建、切换、删除历史会话
- 昵称与性格可通过侧边栏配置，实时生效

## 运行

1. 复制 `.env.example` 为 `.env`，填入你的 `DEEPSEEK_API_KEY`
2. `pip install streamlit openai python-dotenv`
3. `streamlit run app.py`

## 技术栈

Python / Streamlit / OpenAI SDK（兼容 DeepSeek API）