from pathlib import Path
import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes-server")

NOTES = Path(os.environ.get("NOTES_DIR",
            Path(__file__).resolve().parent.parent.parent / "notes")).resolve()

@mcp.tool()
def search_notes(keyword: str) -> str:
    """在 notes/ 目录里按关键词搜索，返回命中的文件名和片段"""
    kw = keyword.strip()
    if not kw:
        return "❌ keyword 不能为空"

    hits = []
    for p in sorted(NOTES.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        idx = text.find(kw)
        if idx < 0:                        # ← find 返回 -1 就是没找到
            continue

        snippet = text[max(0, idx - 40): idx + 80].replace("\n", " ")
        hits.append((text.count(kw), p.name, snippet))

    if not hits:                           # ← 必须在用 hits 之前
        return f"没有找到包含「{kw}」的笔记"

    hits.sort(reverse=True)
    body = "\n\n".join(
        f"{name}（命中 {c} 次）:: ...{s[:120]}..." for c, name, s in hits[:5]
    )
    if len(hits) > 5:
        body += f"\n\n（共 {len(hits)} 篇命中，只显示前 5 篇）"
    return body                            # ← 返回 body，不是旧拼法
if __name__ == "__main__":
    mcp.run(transport="stdio")
