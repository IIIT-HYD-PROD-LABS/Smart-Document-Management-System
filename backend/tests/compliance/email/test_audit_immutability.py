"""Phase 15 — EMAIL-09 audit immutability tests.

RED-state stub. The Phase 9 INFRA-07 trigger + REVOKE on `audit_logs`
already enforces append-only at the DB layer. These tests assert the
trigger fires when a Phase 15 MCP_TOOL_CALL row is targeted for
UPDATE/DELETE — proving Phase 9's defense in depth carries over.
"""
from __future__ import annotations

import pytest


def test_update_mcp_tool_call_audit_row_raises():
    """UPDATE on an MCP_TOOL_CALL audit_log row raises 'append-only' (Phase 9 trigger; EMAIL-09)."""
    try:
        from app.services.audit_service import log_audit_event_strict  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — Phase 15 audit log path not yet wired")
    pytest.skip("Plan 04 — MCP_TOOL_CALL row UPDATE assertion lands then")


def test_delete_mcp_tool_call_audit_row_raises():
    """DELETE on an MCP_TOOL_CALL audit_log row raises 'append-only' (Phase 9 trigger; EMAIL-09)."""
    try:
        from app.services.audit_service import log_audit_event_strict  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — Phase 15 audit log path not yet wired")
    pytest.skip("Plan 04 — MCP_TOOL_CALL row DELETE assertion lands then")
