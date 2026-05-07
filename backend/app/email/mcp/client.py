"""In-memory MCP client wrapper — reconciliation #1 (D-38).

Phase 12 agents call:
    from app.email.mcp.client import call_gmail_tool
    result = await call_gmail_tool("gmail_search", {
        "user_id": 1, "client_id": 1, "query": "from:cbic-gst.gov.in"
    })
"""
from __future__ import annotations

from fastmcp import Client

from app.email.mcp.server import mcp


async def call_gmail_tool(tool_name: str, args: dict) -> dict:
    """Invoke a Gmail MCP tool via in-memory transport.

    Reconciliation #1: in-process transport — no child-process spawn, no
    stdio framing; native Python exception propagation; zero IPC overhead.
    """
    async with Client(mcp) as client:
        result = await client.call_tool(tool_name, args)
        return result.data
