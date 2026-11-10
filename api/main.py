from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os

from api.chunking import split_by_head
from api.store import (new_session_dict, load_session, save_session,
                       load_sessions, delete_session)
from api.rag import retrieve, build_messages, COL, SCORE_THRESHOLD, embed
from api.messages import trim_by_tokens, check_and_fix_messages
from api.prompt import make_system_prompt
import psycopg
from api.config import DB_URL, BASE_URL, DEEPSEEK_API_KEY
PG_DSN = DB_URL

app = FastAPI(title="AI 伴侣 API")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=BASE_URL,
)

class ChatIn(BaseModel):
    question: str
    session_id: str | None = None

def _vec_str(v) -> str:
    """list[float] → '[0.1,0.2,...]'"""
    return "[" + ",".join(str(float(x)) for x in v) + "]"

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
        answer = "笔记里没有相关内容，我不知道。"
        messages.append({"role": "assistant", "content": answer})
        session["messages"] = messages
        save_session(session)
        return {
            "session_id": session["session_id"],
            "answer": answer,
            "sources": [],
            "created": created,
        }
    sys_p = make_system_prompt(session["nick_name"], session["nature"])
    msgs = build_messages(messages, sys_p, retrieved)

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=msgs,
    )
    answer = resp.choices[0].message.content

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
