from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes-server")

NOTES = Path(__file__).resolve().parent.parent.parent / "notes"

@mcp.tool()
def search_notes(keyword:str)->str:
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
        if kw in text:
            idx = text.index(kw)
            if idx >= 0:
                snippet = text[max(0, idx - 40): idx + 80].replace("\n", " ")
                hits.append((text.count(kw), p.name, snippet))

    if len(hits) > 5:
        return "\n\n".join(hits[:5]) + f"\n\n（共 {len(hits)} 篇命中，只显示前 5 篇）"

    if not hits:
        return f"没有找到包含「{kw}」的笔记"

    hits.sort(reverse=True)
    return "\n\n".join(f"{name} :: ...{s[:120]}..." for _, name, s in hits[:5])

if __name__ == "__main__":
    mcp.run(transport="stdio")
