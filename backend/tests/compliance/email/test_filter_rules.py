"""Phase 15 — EMAIL-04 filter-rules tests.

RED-state stub. Plan 02 lands GmailFilterRule with a `priority` Integer
column (open question #5 from reconciliations — lower priority value
wins when multiple rules match).
"""
from __future__ import annotations

import pytest


def test_filter_rule_priority_column_exists():
    """GmailFilterRule has Integer column `priority` (open question #5; EMAIL-04)."""
    try:
        from app.email.models.filter_rule import GmailFilterRule  # noqa: F401
    except ImportError:
        pytest.skip("Plan 02 — GmailFilterRule ORM not yet implemented")
    pytest.skip("Plan 02 — priority column assertion lands then")


def test_lower_priority_rule_wins_when_two_match():
    """Two rules match the same email; lower `priority` value applies (EMAIL-04 match precedence)."""
    try:
        from app.email.models.filter_rule import GmailFilterRule  # noqa: F401
        from app.email.services.classifier import resolve_route  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — classifier.resolve_route not yet implemented")
    pytest.skip("Plan 03 — match-precedence assertion lands then")
