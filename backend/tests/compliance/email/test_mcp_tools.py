"""Phase 15 — EMAIL-02 / EMAIL-09 MCP tools tests.

RED-state stub. Plan 04 lands the FastMCP server module
`app.email.mcp.server` exposing 6 tools per D-02:
  gmail_search, gmail_read_message, gmail_list_attachments,
  gmail_get_attachment, gmail_list_labels, gmail_modify_labels.

In-memory transport pattern (per researcher reconciliation #1, supersedes
D-30 stdio + D-31 subprocess via D-38):

    from fastmcp import Client
    from app.email.mcp.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool("gmail_search", {"query": "..."})
        assert result.data["message_ids"] == [...]

The in-memory `Client(server_instance)` transport eliminates IPC/subprocess
overhead, propagates Python exceptions natively, and matches the v2.0
deployment model where Phase 12 agents share the FastAPI process.
"""
from __future__ import annotations

import pytest


def test_six_tools_registered():
    """Plan 04 ships 6 tools per D-02 — verify registry (EMAIL-02)."""
    try:
        from app.email.mcp.server import mcp  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — FastMCP server not yet implemented")
    pytest.skip("Plan 04 — 6-tool registration assertion lands then")


async def test_in_memory_client_invokes_gmail_search():
    """FastMCP in-memory Client(mcp) invokes gmail_search and returns Pydantic schema data (EMAIL-02)."""
    try:
        from fastmcp import Client  # noqa: F401
        from app.email.mcp.server import mcp  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — fastmcp + app.email.mcp.server not yet importable")
    pytest.skip("Plan 04 — in-memory Client(mcp) invocation assertion lands then")


def test_audit_log_row_written_per_tool_call():
    """Every MCP tool call writes one audit_log row with action=MCP_TOOL_CALL (EMAIL-09 / D-04)."""
    try:
        from app.email.mcp.tools import gmail_search_impl  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — gmail_search_impl not yet implemented")
    pytest.skip("Plan 04 — MCP_TOOL_CALL audit row assertion lands then")
