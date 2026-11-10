# 会话 dict 的键（与 sessions/*.json 一致）：
#   session_id, created_at, display_name, nick_name, nature, messages
from datetime import datetime
import json
import os
import uuid
from pathlib import Path
from api.config import SESSIONS_DIR, DB_URL

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = Path(SESSIONS_DIR)

def _conn():
    return psycopg.connect(DB_URL)

def save_session(session: dict):
    if not session.get("messages"):
        return
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions
                  (session_id, created_at, display_name, nick_name, nature, messages)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                  messages     = EXCLUDED.messages,
                  display_name = EXCLUDED.display_name
            """, (
                session["session_id"], session["created_at"], session["display_name"],
                session["nick_name"], session["nature"],
                json.dumps(session["messages"], ensure_ascii=False),
            ))


#加载所有的会话列表信息
def resolve_created_at(session_id, path, param):
    created_at = param.get("created_at")
    if created_at:
        return created_at
    try:
        # 旧文件名就是 "%Y-%m-%d %H:%M:%S" 格式的时间戳
        return datetime.strptime(session_id, "%Y-%m-%d %H:%M:%S").isoformat()
    except ValueError:
        # 最后兜底：文件修改时间
        return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()


def generate_session_name():
    return str(uuid.uuid4())

def now_iso():
    return datetime.now().isoformat(timespec="microseconds")

def new_session_dict():
    return {
        "session_id": generate_session_name(),
        "created_at": now_iso(),
        "display_name": None,
        "nick_name": "大肥鱼",
        "nature": "傲娇可爱的台湾妹子",
        "messages": []
    }

def format_session_label(display_name, created_at, session_id):
    if display_name:
        return display_name
    raw = created_at or session_id
    try:
        return datetime.fromisoformat(raw).strftime("%m-%d %H:%M:%S")
    except ValueError:
        return raw

def load_session(session_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT session_id, created_at, display_name,
                                  nick_name, nature, messages
                           FROM sessions WHERE session_id = %s""", (session_id,))
            row = cur.fetchone()
    if row is None:
        return None
    sid, created_at, display_name, nick_name, nature, messages = row
    return {"session_id": sid, "created_at": created_at.isoformat(),
            "display_name": display_name, "nick_name": nick_name,
            "nature": nature, "messages": messages}

def load_sessions() -> list[dict]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT session_id, display_name, created_at
                           FROM sessions ORDER BY created_at DESC""")
            rows = cur.fetchall()
    return [{"session_id": r[0], "display_name": r[1],
             "created_at": r[2].isoformat()} for r in rows]

def delete_session(session_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            deleted = cur.rowcount > 0
    return deleted



