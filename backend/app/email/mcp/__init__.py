"""Phase 15 MCP server package — FastMCP in-memory transport.

Reconciliation #1 (D-38): D-31 subprocess.Popen design abandoned in favor of
FastMCP in-memory Client(server_instance) pattern. Phase 12 agents share the
FastAPI process; subprocess + stdio adds zero security and several failure
modes (orphan child, stdio framing, double-fork on container restart, IPC
serialization overhead).

v2.1 fallback path: if external agent host materializes, swap one file
(this __init__) to spawn FastMCP via streamable-http transport.
"""
from app.email.mcp.server import mcp  # noqa: F401
