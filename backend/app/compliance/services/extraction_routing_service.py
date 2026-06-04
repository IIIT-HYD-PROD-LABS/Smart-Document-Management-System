"""Confidence-based routing for the notice extraction artefact — Phase 17 D-06.

`route_or_apply(envelope)` returns a structured decision indicating whether
the envelope is confident enough to auto-apply to the notice form (action
'apply'), or whether it should be routed to the Phase 10 review queue
(action 'review_queue'). The 'failed' action is used by callers when the
extractor raised before producing an envelope (extraction_status='failed').

Per 17-CONTEXT D-06 the gate is conjunctive:
    average_confidence ≥ AVG_GATE
  AND
    fields['notice_number'].confidence ≥ CRITICAL_GATE
  AND
    fields['authority'].confidence ≥ CRITICAL_GATE

This is what the user signed off on 2026-05-22 (D-06 [REVISED]).

The validator (notice_extraction_validator) MUST run before this function
so the confidences here are post-validation (D-06 + D-33).
"""
from __future__ import annotations

from typing import Final

from app.config import settings


# Defaults; the live gates are read from settings at call time so they can be
# tuned per deployment (lower for local models that do not self-report
# confidence). See settings.EXTRACTION_AVG_GATE / EXTRACTION_CRITICAL_GATE.
AVG_GATE: Final[float] = 0.85
CRITICAL_GATE: Final[float] = 0.85
CRITICAL_FIELDS: Final[tuple[str, ...]] = ("notice_number", "authority")


def _field_confidence(envelope: dict, field_name: str) -> float:
    fields = envelope.get("fields", {}) or {}
    payload = fields.get(field_name)
    if not isinstance(payload, dict):
        return 0.0
    try:
        return float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _critical_field_map(envelope: dict) -> dict[str, float]:
    return {name: _field_confidence(envelope, name) for name in CRITICAL_FIELDS}


def route_or_apply(envelope: dict) -> dict:
    """Return a decision dict shaped per `ExtractionRouteDecision`.

    The dict is JSON-serialisable so callers can either feed it straight
    to FastAPI or wrap it in the Pydantic schema.
    """
    average = float(envelope.get("average_confidence") or 0.0)
    critical = _critical_field_map(envelope)

    avg_gate = float(settings.EXTRACTION_AVG_GATE)
    critical_gate = float(settings.EXTRACTION_CRITICAL_GATE)

    failing: list[str] = []
    if average < avg_gate:
        failing.append(f"average confidence {average:.2f} < {avg_gate}")
    for name, conf in critical.items():
        if conf < critical_gate:
            failing.append(f"{name} confidence {conf:.2f} < {critical_gate}")

    if not failing:
        return {
            "action": "apply",
            "reason": None,
            "average_confidence": round(average, 4),
            "critical_field_confidence": {k: round(v, 4) for k, v in critical.items()},
        }

    return {
        "action": "review_queue",
        "reason": "; ".join(failing),
        "average_confidence": round(average, 4),
        "critical_field_confidence": {k: round(v, 4) for k, v in critical.items()},
    }


# ─────────────────────────────────────────────────────────────────────
# Apply / persist + first-upload-wins guard
# ─────────────────────────────────────────────────────────────────────


# Statuses where re-extracting would clobber human-accepted fields (D-12).
_FROZEN_STATUSES: Final[frozenset[str]] = frozenset({"accepted", "superseded"})


def should_skip_extraction(notice) -> bool:
    """D-12: re-uploading a notice that already has accepted extraction must NOT overwrite.

    Returns True when the notice already has user-blessed extraction data
    that subsequent uploads must preserve.
    """
    status = getattr(notice, "extraction_status", None)
    return status in _FROZEN_STATUSES


def apply_extraction_to_notice(
    db, notice, envelope: dict, decision: dict, *, fill_columns: bool = True
) -> None:
    """Persist the extraction envelope onto the notice and back-populate columns.

    Always writes the envelope, confidence, provider, timestamp (D-23 + D-11).
    When the routing decision is 'apply' (the D-06 confidence gate passed) and
    ``fill_columns`` is True, the model-owned fields are coerced and written
    onto any canonical column that is still empty (fill-don't-clobber: a
    confident extraction never overwrites a value a human already entered), and
    extraction_status becomes 'accepted' so the upload-fills-the-fields
    workflow completes without a second step. When the decision is
    'review_queue', the envelope is parked (status 'completed', label "awaiting
    acceptance") and a review-queue row is enqueued so reviewers see the notice
    in the queue (D-06 + Phase 10 reuse).

    ``fill_columns=False`` is used by the accept-extraction replay path, where
    the user's reviewed ``items`` are the sole authority on which columns get
    written — auto-filling there would resurrect fields the user discarded.
    """
    from datetime import datetime, timezone

    notice.extracted_fields = envelope
    notice.extraction_confidence = envelope.get("average_confidence")
    notice.extracted_by_provider = envelope.get("model")
    notice.extracted_at = datetime.now(timezone.utc)

    if decision.get("action") == "apply":
        if fill_columns:
            _apply_fields_to_columns(notice, envelope)
            notice.extraction_status = "accepted"
        else:
            notice.extraction_status = "completed"
    else:
        notice.extraction_status = "completed"
    db.flush()

    if decision.get("action") == "review_queue":
        _enqueue_for_review(db, notice, envelope, decision)


def _apply_fields_to_columns(notice, envelope: dict) -> None:
    """Coerce the model-owned fields onto empty canonical columns.

    Fill-don't-clobber: a column that already holds a value (e.g. the
    notice_number/authority a human entered at creation, or the default
    received_date) is left untouched. Per-field coercion failures are
    swallowed so one unparseable value never aborts the whole apply — which,
    in the Celery worker, would otherwise mark the extraction failed and
    discard every good field with it.
    """
    from app.compliance.services.extraction_coercion import (
        CoercionError,
        FIELD_COERCERS,
    )

    fields = envelope.get("fields") or {}
    for field_name, (column, coerce) in FIELD_COERCERS.items():
        if getattr(notice, column, None) is not None:
            continue
        payload = fields.get(field_name)
        if not isinstance(payload, dict):
            continue
        try:
            value = coerce(payload.get("value"))
        except CoercionError:
            continue
        if value is None:
            continue
        setattr(notice, column, value)


def _enqueue_for_review(db, notice, envelope: dict, decision: dict) -> None:
    """Adapt the Phase 17 routing decision onto Phase 10 review queue semantics.

    Phase 10's enqueue_low_confidence wants (predicted_authority,
    authority_confidence, predicted_type_id, type_confidence). Phase 17's
    extraction is shaped around notice_number + authority confidences, so
    we map:
      - predicted_authority           = extracted authority value
      - predicted_authority_confidence = post-validation authority confidence
      - predicted_type_id              = None (Phase 17 does not predict NoticeType)
      - predicted_type_confidence      = None
      - model_version                  = 'phase17_llm_extractor'

    The mapping is intentionally narrow: the review queue row carries
    enough to render in the UI; reviewers see the full envelope via the
    notice detail page's provenance disclosure.
    """
    from decimal import Decimal

    from app.compliance.services.review_queue_service import enqueue_low_confidence

    fields = envelope.get("fields") or {}
    authority_payload = fields.get("authority") if isinstance(fields.get("authority"), dict) else None
    authority_value = authority_payload.get("value") if authority_payload else None
    authority_conf = (
        Decimal(str(authority_payload.get("confidence")))
        if authority_payload and authority_payload.get("confidence") is not None
        else Decimal("0.0")
    )

    enqueue_low_confidence(
        db,
        notice=notice,
        predicted_authority=authority_value,
        predicted_authority_confidence=authority_conf,
        predicted_type_id=None,
        predicted_type_confidence=Decimal("0.0"),
        model_version="phase17_llm_extractor",
    )
