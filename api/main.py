from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from openai import OpenAI
import os
import json

from api.chunking import split_by_head
from api.store import (new_session_dict, load_session, save_session,
                       load_sessions, delete_session)
from api.rag import retrieve, build_messages, COL, SCORE_THRESHOLD, embed
from api.messages import trim_by_tokens, check_and_fix_messages
from api.prompt import make_system_prompt
import psycopg
from api.config import DB_URL, BASE_URL, DEEPSEEK_API_KEY
from api.tools import TOOLS, run_tool

PG_DSN = DB_URL

app = FastAPI(title="AI 伴侣 API")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=BASE_URL,
)

MAX_STEPS = 5

class ChatIn(BaseModel):
    question: str
    session_id: str | None = None

def _vec_str(v) -> str:
    """list[float] → '[0.1,0.2,...]'"""
    return "[" + ",".join(str(float(x)) for x in v) + "]"

def _digest(raw: str) -> str:
    """把 tool 返回的 JSON 压成一句人话，失败或非 JSON 就截断"""
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw[:60].replace("\n", " ")

    if not isinstance(d, dict):
        return raw[:60]

    if d.get("ok") is False:
        return f"失败：{d.get('error') or d.get('code')}"

    if "content" in d:                              # read_note
        body = str(d["content"]).replace("\n", " ").strip()
        return f"《{d.get('filename', '')}》{body[:60]}"

    if "count" in d:                                # query_chunks
        files = {r.get("file") for r in d.get("rows", [])}
        return f"查到 {d['count']} 块（涉及 {len(files)} 篇）"

    return raw[:60]
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    raw = await file.read()
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="只接受 .md 文件")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是 UTF-8 编码")
    chunks = split_by_head(text)

    vecs = embed(chunks)

    with psycopg.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE file = %s", (file.filename,))
            cur.executemany(
                "INSERT INTO chunks (file, content, embedding) VALUES (%s, %s, %s::vector)",
                [(file.filename, c, _vec_str(v)) for c, v in zip(chunks, vecs)],
            )

        COL.delete(where={"file": file.filename})
        COL.add(documents=chunks, embeddings=vecs,
                ids=[f"{file.filename}::{i}" for i in range(len(chunks))],
                metadatas=[{"file": file.filename} for _ in chunks])

    return {"filename": file.filename, "chunks": len(chunks)}


@app.post("/chat")
def chat(body: ChatIn):
    session_id = body.session_id
    if body.session_id is None:
        session, created = new_session_dict(), True
    else:
        session = load_session(body.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        created = False

    messages = session["messages"]
    messages.append({"role": "user", "content": body.question})
    messages = trim_by_tokens(messages)
    messages = check_and_fix_messages(messages)

    # 取最近一条 user 消息（不含当前这条）
    prev = None
    for m in reversed(messages[:-1]):
        if m["role"] == "user":
            prev = m["content"]
            break

    query = f"{prev} {body.question}" if prev else body.question
    retrieved = retrieve(query)
    hits = [r for r in retrieved if r[1] >= SCORE_THRESHOLD]
    if not hits:
        retrieved = []
    sys_p = make_system_prompt(session["nick_name"], session["nature"])

    answer = None
    for step in range(1, MAX_STEPS + 1):
        msgs = build_messages(messages, sys_p, retrieved)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=msgs,
            tools=TOOLS,
        )
        msg = resp.choices[0].message
        reason = resp.choices[0].finish_reason

        if reason == "stop":
            answer = msg.content or ""
            break

        elif reason == "length":
            # 被 max_tokens 截断：内容不完整
            answer = (msg.content or "") + "\n\n（回答被截断，可以让我接着说）"
            break

        elif reason == "tool_calls":
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [c.model_dump() for c in msg.tool_calls],
            })

            for call in msg.tool_calls:
                result = run_tool(call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

            session["messages"] = messages
            save_session(session)

        else:
            answer = f"模型返回了异常的结束原因：{reason}"
            break

    if answer is None:
        done = [
            _digest(m["content"])
            for m in messages
            if m.get("role") == "tool" and m.get("content")
        ]
        answer = "这个任务我试了 %d 步还没搞定。" % MAX_STEPS
        if done:
            answer += "\n\n已经查到的有：\n" + "\n".join(f"- {d}" for d in done[-3:])
        answer += "\n\n要不要把问题拆小一点？"

    messages.append({"role": "assistant", "content": answer})
    session["messages"] = messages
    save_session(session)

    best: dict[str, float] = {}
    for f, s, _ in retrieved:
        if s < SCORE_THRESHOLD:
            continue
        if f not in best or s > best[f]:
            best[f] = round(s, 3)
    sources = [{"file": f, "score": s} for f, s in best.items()]

    return {
        "session_id": session["session_id"],
        "answer": answer,
        "sources": sources,
        "created":created,
    }


@app.get("/sessions")
def list_sessions():
    return load_sessions()

@app.delete("/documents/{filename}", status_code=204)
def delete_document(filename:str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400,detail="非法文件名")

    in_chroma = bool(COL.get(where={"file":filename})["ids"])

    with psycopg.connect(DB_URL) as corn:
        with corn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks WHERE file = %s", (filename,))
            in_pg = cur.fetchone()[0] > 0
        if not in_chroma and not in_pg:
            raise HTTPException(status_code=404, detail="文档不存在")

    COL.delete(where={"file": filename})

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE file = %s", (filename,))

    return None

