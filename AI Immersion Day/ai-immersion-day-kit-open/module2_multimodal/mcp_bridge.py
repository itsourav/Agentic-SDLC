"""Connects our agent to ANY MCP server: discovers its tools and wraps them as llm.Tool objects.
This is exactly what Continue, Open WebUI (via mcpo) or any MCP client does under the hood when you add an MCP server."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from common import llm

SERVER = Path(__file__).resolve().parent / "mcp_server" / "catalogue_server.py"
PARAMS = StdioServerParameters(command=sys.executable, args=[str(SERVER)])


async def _with_session(fn):
    async with stdio_client(PARAMS) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def list_tools() -> list[dict]:
    async def go(s):
        res = await s.list_tools()
        return [{"name": t.name, "description": t.description, "input_schema": t.inputSchema} for t in res.tools]

    return asyncio.run(_with_session(go))


def call_tool(name: str, args: dict):
    async def go(s):
        res = await s.call_tool(name, args)
        if getattr(res, "structuredContent", None):
            sc = res.structuredContent
            return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
        txt = "".join(getattr(c, "text", "") for c in res.content)
        try:
            return json.loads(txt)
        except Exception:
            return txt

    return asyncio.run(_with_session(go))


def as_agent_tools(mock_triggers: dict | None = None) -> list[llm.Tool]:
    """Turn every MCP tool into an agent tool - no hand-written glue per tool."""
    mock_triggers = mock_triggers or {}
    tools = []
    for t in list_tools():
        tools.append(llm.Tool(
            name=t["name"], description=t["description"] or t["name"], parameters=t["input_schema"],
            fn=(lambda _n: (lambda **kw: call_tool(_n, kw)))(t["name"]),
            mock_trigger=mock_triggers.get(t["name"]),
        ))
    return tools


if __name__ == "__main__":
    for t in list_tools():
        print(f"- {t['name']}: {t['description'].splitlines()[0]}")
    print(call_tool("lookup_paint_code", {"colour_description": "bright red"}))
