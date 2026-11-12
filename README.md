# AI 伴侣 · 笔记问答服务

基于本地笔记的检索增强问答服务（RAG）。FastAPI 提供接口，bge 嵌入做语义召回，
DeepSeek 生成回答并标注来源文件名；检索不到相关内容时明确拒答，不编造。

## 在线演示

- Swagger 文档：<http://120.55.193.78/docs>
- 部署：阿里云 ECS（Debian 13 / 2核2G）
- 入口：Caddy 反向代理 `:80` → `127.0.0.1:8000`，uvicorn 只绑回环，不直接对公网暴露
- 常驻：`aipartner.service` + `caddy.service`，均已 `enabled` 开机自启
- 安全组只放行 22（SSH）与 80，其余端口不对外

## HTTPS 还差什么

不是证书，是**备案**。

| 步骤 | 耗时 | 说明 |
|---|---|---|
| 购买域名 | 即时 | 约 50 元/年，需实名认证 |
| ICP 备案 | **1–3 周** | 大陆服务器用 80/443 对公网提供网站必须先备案 |
| 配置 Caddy HTTPS | **5 分钟** | Caddyfile 里把 `:80` 换成域名，证书自动申请并续期 |

当前用 `IP:80` 直连 http，可正常工作——备案拦截的是未备案域名，不是 IP。
一旦要 https 就必须有域名，而域名解析到大陆 IP 又绕不开备案。**瓶颈在行政流程，不在技术。**

替代路线：换非大陆主机（香港 / 新加坡）可免备案、立即上 HTTPS。

## 功能

- 上传 Markdown，按标题切分、向量化，双写 ChromaDB 与 Postgres(pgvector)
- 提问 → 语义召回 → 生成回答，返回来源文件名与相关度分数
- 检索不到内容时**代码层硬拒答**（不调用模型），不产生幻觉
- 多轮会话，历史持久化在 Postgres（JSONB），重启不丢
- 删除文档时 pg 与 chroma 双写删除，不留孤儿向量

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Web | FastAPI + uvicorn | 4 个端点，Pydantic 校验 |
| 嵌入 | BAAI/bge-small-zh-v1.5 | 512 维，本地 CPU 推理 |
| 精排 | BAAI/bge-reranker-base | CrossEncoder，**默认关闭**（评测为负收益，见下文） |
| 向量库 | ChromaDB + Postgres/pgvector | 双写，同向量同距离（已交叉验证） |
| 存储 | Postgres 17 | `chunks` 存分块，`sessions` 存会话（JSONB） |
| 生成 | DeepSeek API | `deepseek-chat` |

## 本地运行

需要 Python 3.13 与 Postgres（含 pgvector）。

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DEEPSEEK_API_KEY=*** DeepSeek Key>

# 以下可选，不设则用默认值
# export DATABASE_URL="dbname=aipartner"
# export CHROMA_DIR=/绝对路径/chroma_db
# export ENABLE_RERANK=1      # 默认 0，即关闭精排

uvicorn api.main:app --reload
```

首次需建表：

```sql
CREATE EXTENSION vector;

CREATE TABLE chunks (
  id bigserial PRIMARY KEY,
  file text NOT NULL,
  content text NOT NULL,
  embedding vector(512)
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE sessions (
  session_id text PRIMARY KEY,
  created_at timestamptz NOT NULL,
  display_name text,
  nick_name text NOT NULL,
  nature text NOT NULL,
  messages jsonb NOT NULL DEFAULT '[]'::jsonb
);
```

打开 <http://127.0.0.1:8000/docs>

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/ingest` | 上传 `.md`，切分后双写入库；同名文件覆盖 |
| POST | `/chat` | 提问，返回 `session_id` / `answer` / `sources`；`session_id` 不存在返回 404 |
| GET | `/sessions` | 会话列表 |
| DELETE | `/documents/{filename}` | 删除文档（pg + chroma 双写）；成功 204，不存在 404 |

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

**拒答阈值**：取 `0.45`。依据是两组实测分布——20 道命中题的最低相似度 0.563，
语料外问题（天气 / React / 明朝）的最高相似度 0.374，阈值落在两者之间，
对 20 题零误伤。

**结论**：

- 切分方式影响最大——同一份语料，整篇入库 3/5，按标题切分后 5/5（5 题早期评测）
- rerank 在 20 题集上为负收益：cross-encoder 对口语化转述的鲁棒性不如预期，
  且会把正确答案从前 3 挤出。5 题小样本时它看起来有效（gap 0.007→0.112），
  扩到 20 题后翻盘——**小样本评测会给出虚假信心**

## 已知限制

- 语料仅 20 篇 / 约 2 万字。此规模下全量投喂也可行，本项目用 RAG 是为了练架构与评测能力
- 无 HTTPS；`IP:8000` 直连
- 检索未覆盖跨文档的复合问题（如「虚拟内存和分页」同时涉及 06/07）