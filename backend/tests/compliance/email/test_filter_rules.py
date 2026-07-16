"""Phase 15 — EMAIL-04 filter-rules tests."""
from __future__ import annotations

from types import SimpleNamespace

from app.email.models.filter_rule import GmailFilterRule
from app.email.models.message_log import GmailMessageLog
from app.email.services.classifier import resolve_route


def test_filter_rule_priority_column_exists():
    """GmailFilterRule has Integer column `priority` (open question #5; EMAIL-04)."""
    assert "priority" in GmailFilterRule.__table__.columns
    col = GmailFilterRule.__table__.columns["priority"]
    assert str(col.type).upper().startswith("INTEGER")
    assert col.nullable is False


def test_lower_priority_rule_wins_when_two_match():
    """Two rules match the same email; lower `priority` value applies."""
    rules = [
        SimpleNamespace(
            enabled=True,
            sender_pattern=r"@example\.com$",
            subject_pattern=None,
            route_to=GmailMessageLog.ROUTE_DMS_ONLY,
            priority=10,
        ),
        SimpleNamespace(
            enabled=True,
            sender_pattern=r"@example\.com$",
            subject_pattern=None,
            route_to=GmailMessageLog.ROUTE_BILL,
            priority=1,
        ),
    ]
    # Caller must pass priority ASC order (as load_enabled_rules does)
    ordered = sorted(rules, key=lambda r: (r.priority, 0))
    route = resolve_route("a@example.com", "anything", rules=ordered)
    assert route == GmailMessageLog.ROUTE_BILL
