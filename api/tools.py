# api/tools.py
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "notes"

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


TOOL_MAP = {"get_time": get_time, "read_note": read_note}