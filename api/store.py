# 会话 dict 的键（与 sessions/*.json 一致）：
#   session_id, created_at, display_name, nick_name, nature, messages
from datetime import datetime
import json
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = ROOT / "sessions"

def save_session(session: dict):
    if not session.get("messages"):
        return
    SESSIONS.mkdir(parents=True, exist_ok=True)
    if session.get("session_id"):
        with open(SESSIONS / f"{session['session_id']}.json", "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)



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

def load_sessions() -> list[dict]:
    if not SESSIONS.exists():
        return []
    session_list = []
    for p in SESSIONS.glob("*.json"):
        session_id = p.stem
        display_name = None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            display_name = data.get("display_name")
            created_at = resolve_created_at(session_id, p, data)
        except Exception as e:
            print(f"[load_sessions] 读取 {p.name} 失败：{type(e).__name__}: {e}")
            created_at = resolve_created_at(session_id, p, {})
        session_list.append({"session_id": session_id,
                             "display_name": display_name,
                             "created_at": created_at})
    session_list.sort(key=lambda s: s["created_at"], reverse=True)
    return session_list

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
    p = SESSIONS / f"{session_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def delete_session(session_id):
    p = SESSIONS / f"{session_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False



