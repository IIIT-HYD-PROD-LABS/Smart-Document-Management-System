"""Phase 10 Plan 02 — escalation module unit tests.

Pure-Python tests using MagicMock — no DB / no Celery. End-to-end
integration of the wired-up Celery hook is exercised by
test_classify_and_score_task.py.

Covers:
  - should_escalate() returns False for non-critical tiers
  - should_escalate() returns True for critical with no prior escalation
  - should_escalate() returns False during cooldown window
  - should_escalate() returns True after cooldown window
  - escalate() writes activity + audit + reassigns assigned_user_id
  - escalate() handles missing compliance_head (NULL-assigned)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.ml.compliance.escalation import (
    ACTIVITY_SOURCE,
    ESCALATION_COOLDOWN,
    escalate,
    last_escalation_at,
    should_escalate,
)


def _make_assessment(tier: str = "critical", score: float = 92.5):
    """Build a stand-in RiskAssessment for tests."""
    a = MagicMock()
    a.tier = tier
    a.score = score
    a.model_version = "rules-v1.0"
    a.top_factors = [
        MagicMock(feature="authority_severity", contribution=22.5,
                  natural_language="RBI regulator severity contributes +22.5 points"),
    ]
    return a


def test_should_escalate_returns_false_when_not_critical():
    db = MagicMock()
    notice = MagicMock(id=1)
    assert should_escalate(db, notice=notice, risk_tier="high") is False
    assert should_escalate(db, notice=notice, risk_tier="medium") is False
    assert should_escalate(db, notice=notice, risk_tier="low") is False


def test_should_escalate_true_when_no_prior_escalation():
    db = MagicMock()
    notice = MagicMock(id=1)
    with patch(
        "app.ml.compliance.escalation.last_escalation_at", return_value=None
    ):
        assert should_escalate(db, notice=notice, risk_tier="critical") is True


def test_should_escalate_false_within_cooldown():
    db = MagicMock()
    notice = MagicMock(id=1)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    just_now = now - timedelta(hours=1)
    with patch(
        "app.ml.compliance.escalation.last_escalation_at", return_value=just_now
    ):
        assert should_escalate(
            db, notice=notice, risk_tier="critical", now=now
        ) is False


def test_should_escalate_true_after_cooldown():
    db = MagicMock()
    notice = MagicMock(id=1)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    long_ago = now - ESCALATION_COOLDOWN - timedelta(seconds=1)
    with patch(
        "app.ml.compliance.escalation.last_escalation_at", return_value=long_ago
    ):
        assert should_escalate(
            db, notice=notice, risk_tier="critical", now=now
        ) is True


def test_should_escalate_true_at_exact_cooldown_boundary():
    db = MagicMock()
    notice = MagicMock(id=1)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    exact = now - ESCALATION_COOLDOWN
    with patch(
        "app.ml.compliance.escalation.last_escalation_at", return_value=exact
    ):
        # ">=" — exact boundary triggers escalation
        assert should_escalate(
            db, notice=notice, risk_tier="critical", now=now
        ) is True


def test_escalate_assigns_compliance_head_and_writes_activity_and_audit():
    db = MagicMock()
    notice = MagicMock(id=42, client_id=7, assigned_user_id=None)
    assessment = _make_assessment()

    with (
        patch(
            "app.ml.compliance.escalation.find_compliance_head_user_id",
            return_value=99,
        ),
        patch(
            "app.compliance.services.activity_service.log_activity"
        ) as mock_log_activity,
        patch(
            "app.services.audit_service.log_audit_event"
        ) as mock_log_audit,
    ):
        result = escalate(
            db, notice=notice, assessment=assessment, actor_user_id=None
        )

    assert result == 99
    assert notice.assigned_user_id == 99
    assert mock_log_activity.called
    args, kwargs = mock_log_activity.call_args
    # Activity row should be tagged with the canonical source
    assert kwargs["details"]["source"] == ACTIVITY_SOURCE
    assert kwargs["details"]["risk_tier"] == "critical"
    assert kwargs["details"]["before_assigned_user_id"] is None
    assert kwargs["details"]["after_assigned_user_id"] == 99
    assert kwargs["type"] == "assigned"

    assert mock_log_audit.called
    audit_kwargs = mock_log_audit.call_args.kwargs
    assert audit_kwargs["action"] == "notice_escalated"
    assert audit_kwargs["resource_type"] == "ComplianceNotice"
    assert audit_kwargs["resource_id"] == 42


def test_escalate_logs_warning_when_no_compliance_head():
    """When the client has no compliance_head, escalation still records the
    activity + audit row but with assigned_user_id=None."""
    db = MagicMock()
    notice = MagicMock(id=42, client_id=7, assigned_user_id=10)
    assessment = _make_assessment()

    with (
        patch(
            "app.ml.compliance.escalation.find_compliance_head_user_id",
            return_value=None,
        ),
        patch(
            "app.compliance.services.activity_service.log_activity"
        ) as mock_log_activity,
        patch(
            "app.services.audit_service.log_audit_event"
        ) as mock_log_audit,
    ):
        result = escalate(
            db, notice=notice, assessment=assessment, actor_user_id=None
        )

    assert result is None
    # assigned_user_id stays at the prior value (10) — no head to override
    assert notice.assigned_user_id == 10
    # Activity still recorded so the dashboard surfaces "needs assignment"
    assert mock_log_activity.called
    activity_kwargs = mock_log_activity.call_args.kwargs
    assert activity_kwargs["details"]["after_assigned_user_id"] is None
    assert mock_log_audit.called


def test_last_escalation_at_returns_none_when_no_activity():
    """Hardening (#17) — JSON filter pushed to PG, single-row query."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    assert last_escalation_at(db, 1) is None


def test_last_escalation_at_finds_critical_escalation_source():
    """Hardening (#17) — filter pushed to PG via details->>'source';
    the query returns at most one row (the most-recent escalation)
    instead of all-`assigned`-rows-then-Python-filter."""
    recent_critical = MagicMock(
        created_at=datetime(2026, 5, 4, 12, tzinfo=timezone.utc),
        details={"source": ACTIVITY_SOURCE},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = recent_critical
    result = last_escalation_at(db, 1)
    assert result == datetime(2026, 5, 4, 12, tzinfo=timezone.utc)
