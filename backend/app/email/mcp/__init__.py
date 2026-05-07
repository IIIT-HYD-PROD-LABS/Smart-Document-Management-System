"""Phase 15 MCP server package — FastMCP in-memory transport.

Reconciliation #1 (D-38): the originally specified D-31 child-process spawn
design is abandoned in favor of FastMCP in-memory Client(server_instance)
pattern. Phase 12 agents share the FastAPI process; the in-process path
adds zero security cost and removes several failure modes (orphan child,
stdio framing, double-fork on container restart, IPC serialization).

v2.1 fallback path: if external agent host materializes, swap one file
(this __init__) to spawn FastMCP via streamable-http transport.
"""
from app.email.mcp.server import mcp  # noqa: F401
