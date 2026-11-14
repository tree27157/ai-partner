# api/tools.py
import json
from datetime import datetime
from pathlib import Path
from api.config import DB_URL
import psycopg

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"

MAX_LIMIT = 20

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "读取 notes/ 目录下的一篇 Markdown 笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名，如 14_IP协议、子网划分与CIDR.md"}
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_chunks",
            "description": "按文件名或内容关键词查询数据库里已切分好的块，返回每个块的预览。适合回答‘某篇切成了几块’‘哪些块提到某词’这类精确条件查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "文件名，如 14_IP协议、子网划分与CIDR.md"},
                    "content_like": {"type": "string", "description": "内容包含的关键词，如 饥饿"},
                    "limit":{"type": "integer", "description": "返回条数，默认 10，上限 20"},
                },
            },
        },
    },
]

def _err(code: str, msg: str, **extra) -> str:
    return json.dumps({"ok": False, "code": code, "error": msg, **extra}, ensure_ascii=False)

def get_time():
    now = datetime.now()
    s = now.strftime("%Y-%m-%d %H:%M:%S")
    return s

def read_note(filename):
    if not isinstance(filename, str):
        return _err("BAD_TYPE", f"filename 必须是字符串", got=type(filename).__name__)

    base = NOTES.resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        return _err("PATH_DENIED", "只能读取 notes/ 目录下的文件", requested=filename)
    if not target.exists():
        available = sorted(p.name for p in base.glob("*.md"))
        return _err("FILE_NOT_FOUND", f"没有 {filename} 这篇笔记",
                    requested=filename, available=available)
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as e:
        return _err("READ_FAILED", f"读取失败: {e}", requested=filename)

    return json.dumps({"ok": True, "filename": filename, "content": content},
                      ensure_ascii=False)

def query_chunks(file: str | None = None, content_like: str | None = None, limit: int = 10):
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return _err("BAD_TYPE", "limit 必须是正整数", got=type(limit).__name__)
    limit = min(limit, MAX_LIMIT)

    file = file.strip() if isinstance(file, str) else None
    content_like = content_like.strip() if isinstance(content_like, str) else None

    if not file and not content_like:
        return _err("BAD_ARGS", "file 和 content_like 至少给一个")

    where, params = [], []
    if file is not None:
        where.append("file = %s")
        params.append(file)
    if content_like is not None:
        esc = content_like.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("content LIKE %s ESCAPE '\\'")
        params.append(f"%{esc}%")

    sql = f"SELECT file, left(content, 120) FROM chunks WHERE {' AND '.join(where)} LIMIT %s"
    params.append(limit)

    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as e:
        return _err("DB_ERROR", f"{type(e).__name__}: {e}")

    return json.dumps({"ok": True, "count": len(rows),
                       "rows": [{"file": r[0], "preview": r[1]} for r in rows]},
                      ensure_ascii=False)


def run_tool(call) -> str:
    name = call.function.name
    raw = call.function.arguments or "{}"

    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "error": "参数不是合法 JSON", "raw": raw},
                          ensure_ascii=False)

    fn = TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"ok": False, "error": f"未知工具 {name}"}, ensure_ascii=False)
    try:
        return str(fn(**args))
    except TypeError as e:  # 参数名/个数不对
        return json.dumps({"ok": False, "error": f"参数错误：{e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"},
                          ensure_ascii=False)

TOOL_MAP = {"get_time": get_time, "read_note": read_note, "query_chunks": query_chunks}
