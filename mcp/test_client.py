import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys

async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=["mcp/notes_server/server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()          # ① 握手
            tools = await session.list_tools()  # ② 发现
            print("工具清单:", [t.name for t in tools.tools])
            result = await session.call_tool("search_notes", {"keyword": "死锁"})
            print("调用结果:", result.content[0].text)   # ③ 调用

if __name__ == "__main__":
    asyncio.run(main())