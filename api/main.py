from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI
import os

from api.chunking import split_by_head
from api.store import (new_session_dict, load_session, save_session,
                       load_sessions, delete_session)
from api.rag import retrieve, build_messages, COL, SCORE_THRESHOLD
from api.messages import trim_by_tokens, check_and_fix_messages
from api.prompt import make_system_prompt
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")   # 明确指向项目根
app = FastAPI(title="AI 伴侣 API")

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com")

class ChatIn(BaseModel):
    question: str
    session_id: str | None = None


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    raw = await file.read()
    text = raw.decode("utf-8")
    chunks = split_by_head(text)

    COL.delete(where={"file": file.filename})

    ids = [f"{file.filename}::{i}" for i in range(len(chunks))]
    metadatas = [{"file": file.filename} for _ in chunks]
    COL.add(documents=chunks, ids=ids, metadatas=metadatas)

    return {"filename": file.filename, "chunks": len(chunks)}


@app.post("/chat")
def chat(body: ChatIn):
    session_id = body.session_id
    if not session_id:
        session = new_session_dict()
    else:
        session = load_session(session_id) or new_session_dict()

    messages = session["messages"]
    messages.append({"role": "user", "content": body.question})
    messages = trim_by_tokens(messages)
    messages = check_and_fix_messages(messages)

    retrieved = retrieve(body.question)
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

    return {
        "session_id": session["session_id"],
        "answer": answer,
        "sources": [{"file": f, "score": round(s, 3)}
                    for f, s, _ in retrieved if s >= SCORE_THRESHOLD],
    }


@app.get("/sessions")
def list_sessions():
    return load_sessions()
