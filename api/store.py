# 会话 dict 的键（与 sessions/*.json 一致）：
#   session_id, created_at, display_name, nick_name, nature, messages
from datetime import datetime
import json
import uuid
from api.config import DB_URL

import psycopg


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



