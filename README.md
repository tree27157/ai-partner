---
title: AI Partner
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# AI 伴侣 · 笔记问答服务

基于本地笔记的检索增强问答服务（RAG）。FastAPI 提供接口，检索用 bge 嵌入做语义召回，
回答由 DeepSeek 生成并携带来源文件名，检索不到内容时明确拒答。

## 在线演示

[https://knife-till-suffered-licensed.trycloudflare.com/docs](https://knife-till-suffered-licensed.trycloudflare.com/docs)

> ⚠️ 通过 Cloudflare Tunnel 暴露本机服务：电脑关机或休眠即失效，URL 每次重启会变。

## 功能

- 上传 Markdown 笔记，自动按标题切分、向量化，双写 ChromaDB 与 Postgres(pgvector)
- 提问 → 召回 top-10 → 精排（rerank）→ 生成回答，附带来源文件名与相关度
- 检索不到相关内容时明确拒答，不编造
- 多轮会话，历史持久化，支持新建 / 切换 / 删除

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Web | FastAPI + uvicorn | 三个端点，Pydantic 校验 |
| 嵌入 | BAAI/bge-small-zh-v1.5 | 512 维，本地推理，中文句向量 |
| 精排 | BAAI/bge-reranker-base | CrossEncoder，可用 `ENABLE_RERANK=0` 关闭 |
| 向量库 | ChromaDB + Postgres/pgvector | 双写，同向量同距离（已交叉验证） |
| 生成 | DeepSeek API | `deepseek-chat` |

## 本地运行

依赖：Python 3.13；Postgres 可选（只影响 `/ingest` 的 pg 写入）。

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DEEPSEEK_API_KEY=<你的 DeepSeek Key>

# 以下均为可选，不设则用项目内默认值
# export DATABASE_URL="dbname=aipartner"
# export CHROMA_DIR=/绝对路径/chroma_db
# export SESSIONS_DIR=/绝对路径/sessions
# export ENABLE_RERANK=0

uvicorn api.main:app --reload
```

打开 <http://127.0.0.1:8000/docs>

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/ingest` | 上传 `.md`，切分后双写入库；同名文件覆盖 |
| POST | `/chat` | 提问，返回 `session_id` / `answer` / `sources` |
| GET | `/sessions` | 会话列表 |

## 检索评测

（待填：数据集规模、评测指标、命中率）