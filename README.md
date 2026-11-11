---
title: AI Partner
emoji: 🤖
colorFrom: blue
colorTo: green
---

# AI 伴侣 · 笔记问答服务

基于本地笔记的检索增强问答服务（RAG）。FastAPI 提供接口，检索用 bge 嵌入做语义召回，
回答由 DeepSeek 生成并携带来源文件名，检索不到内容时明确拒答。

## 在线演示

- Swagger 文档：<http://120.55.193.78:8000/docs>
- 部署方式：阿里云 ECS（Debian 13 / 2核2G），systemd 常驻 + 开机自启
- 无 HTTPS：当前用 `IP:8000` 直连，下一步计划加 Caddy 反向代理 + 域名

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

评测集 20 题，覆盖 6 个主题（进程并发 / 内存管理 / 存储与 IO / 网络底层 / 网络层 / 传输与应用层），
每题指定唯一最佳答案文件；其中 16 题用口语化表述（如「内存不够用时系统会怎么办」），
以模拟真实提问而非教材式关键词。

| 配置 | top1 命中 | recall@3 | 结论 |
|---|---|---|---|
| head 切分 + bge 向量召回 | **17/20** | **20/20** | 基线 |
| ＋ bge-reranker-base 精排 | 17/20 | **19/20** | **无提升且损伤召回，线上默认关闭** |

**未命中 3 题**（答案均落在前 3，属排序问题而非召回问题）：

| 提问 | 期望 | 实际 top1 |
|---|---|---|
| 内存不够用时系统会怎么办 | 07_虚拟内存与页面置换算法 | 06_内存管理基础、分页分段 |
| 为什么要在内存里先攒一块缓冲 | 09_IO设备管理、缓冲与中断 | 08_文件系统与 inode |
| 同一根线发数据怎么知道撞上了 | 12_物理层与数据链路层 CSMA-CD | 17_TCP协议、三次握手四次挥手 |

**稳定性**：17 个命中里有 8 题 margin < 0.01（首名与次名几乎并列），
即「稳定命中」实际只有 9/20。

**结论**：

- 切分方式影响最大——同一份语料，整篇入库 3/5，按标题切分后 5/5（5 题早期评测）
- rerank 在 20 题集上为负收益：cross-encoder 对口语化转述的鲁棒性不如预期，
  且会把正确答案从前 3 挤出。故线上通过 `ENABLE_RERANK=0` 默认关闭