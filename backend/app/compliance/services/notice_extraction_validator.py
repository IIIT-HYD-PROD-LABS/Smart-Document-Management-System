"""Structural validation for the notice extraction envelope — Phase 17 D-33 / D-34.

`validate_and_score(envelope)` takes the parsed LLM envelope and returns a
new envelope where each field that fails its structural rule has its
confidence multiplied by 0.5 (D-33). The original model-reported
confidence is preserved on the field as `original_confidence` so the UI
can render "structurally suspect" badges distinct from "model uncertain"
ones (D-34).

The function is pure: it does not mutate the input envelope.

Rules implemented:
    gstin              15-char GSTIN regex + state code in [01..37, 97, 99]
    pan                10-char PAN regex
    cin                21-char CIN regex
    issued_date        ISO 8601 YYYY-MM-DD parse
    response_deadline  ISO 8601 + later than issued_date (when both present)
    tax_demand         non-negative number
    interest           non-negative number
    penalty            non-negative number
    total_liability    non-negative AND ≈ tax + interest + penalty within 1 INR
    authority          one of GST, IT, MCA, RBI, SEBI

Fields without a rule pass through unchanged.
"""
from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

from app.compliance.utils.indian_validators import (
    CIN_RX,
    PAN_RX,
    validate_gstin,
)


_PENALTY_MULTIPLIER = 0.5
_ALLOWED_AUTHORITIES = {"GST", "IT", "MCA", "RBI", "SEBI"}
_LIABILITY_TOLERANCE_INR = 1.0


def _parse_iso_date(value: Any) -> date | None:
    """Parse an ISO 8601 YYYY-MM-DD string. Returns None on any failure."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _check_gstin(value: Any) -> str | None:
    if not isinstance(value, str):
        return "value must be a string"
    if not validate_gstin(value):
        return "does not match the GSTIN 15-character format or has an invalid state code"
    return None


def _check_pan(value: Any) -> str | None:
    if not isinstance(value, str) or not PAN_RX.match(value):
        return "does not match the PAN 10-character format"
    return None


def _check_cin(value: Any) -> str | None:
    if not isinstance(value, str) or not CIN_RX.match(value):
        return "does not match the CIN 21-character format"
    return None


def _check_iso_date(value: Any) -> str | None:
    if _parse_iso_date(value) is None:
        return "is not a valid ISO 8601 date (expected YYYY-MM-DD)"
    return None


def _check_authority(value: Any) -> str | None:
    if value not in _ALLOWED_AUTHORITIES:
        return f"is not one of {sorted(_ALLOWED_AUTHORITIES)}"
    return None


def _check_non_negative_number(value: Any) -> str | None:
    if isinstance(value, bool):
        return "is a boolean, not a number"
    if not isinstance(value, (int, float)):
        return "is not a number"
    if value < 0:
        return "is negative"
    return None


_SINGLE_FIELD_CHECKS = {
    "gstin": _check_gstin,
    "pan": _check_pan,
    "cin": _check_cin,
    "issued_date": _check_iso_date,
    "response_deadline": _check_iso_date,
    "authority": _check_authority,
    "tax_demand": _check_non_negative_number,
    "interest": _check_non_negative_number,
    "penalty": _check_non_negative_number,
    "total_liability": _check_non_negative_number,
}


def _apply_single_field_rules(fields: dict) -> dict:
    """Apply per-field rules; mark failures, halve confidence, keep original."""
    out: dict[str, dict] = {}
    for name, payload in fields.items():
        if not isinstance(payload, dict):
            # Defensive: malformed entries pass through as-is. The
            # extractor service already rejects shape failures before
            # calling the validator.
            out[name] = payload
            continue
        check = _SINGLE_FIELD_CHECKS.get(name)
        failure = check(payload.get("value")) if check else None
        out[name] = _annotate(payload, failure)
    return out


def _annotate(payload: dict, failure: str | None) -> dict:
    """Return a new payload with failure recorded and confidence halved on failure."""
    new = copy.deepcopy(payload)
    raw_confidence = float(new.get("confidence") or 0.0)
    if failure:
        new["original_confidence"] = raw_confidence
        new["confidence"] = round(raw_confidence * _PENALTY_MULTIPLIER, 4)
        new["validation_failure"] = failure
    else:
        new.setdefault("validation_failure", None)
    return new


def _apply_cross_field_rules(fields: dict) -> dict:
    """Rules that involve two or more fields (D-33)."""
    out = dict(fields)

    issued = _parse_iso_date(
        out.get("issued_date", {}).get("value") if isinstance(out.get("issued_date"), dict) else None
    )
    deadline = _parse_iso_date(
        out.get("response_deadline", {}).get("value") if isinstance(out.get("response_deadline"), dict) else None
    )
    if issued and deadline and deadline <= issued and not _already_failed(out.get("response_deadline")):
        out["response_deadline"] = _annotate(
            out["response_deadline"],
            "is on or before the issued date",
        )

    if all(name in out and isinstance(out[name], dict) for name in ("tax_demand", "interest", "penalty", "total_liability")):
        try:
            tax = float(out["tax_demand"]["value"])
            interest = float(out["interest"]["value"])
            penalty = float(out["penalty"]["value"])
            total = float(out["total_liability"]["value"])
        except (TypeError, ValueError):
            tax = interest = penalty = total = None  # type: ignore[assignment]
        # Skip when total_liability already carries a single-field failure: a
        # second _annotate would re-halve the already-halved confidence (0.25x),
        # double-penalising one field for what the spec caps at a single 0.5x.
        if (
            tax is not None
            and abs((tax + interest + penalty) - total) > _LIABILITY_TOLERANCE_INR
            and not _already_failed(out.get("total_liability"))
        ):
            out["total_liability"] = _annotate(
                out["total_liability"],
                "does not equal tax_demand + interest + penalty within 1 INR",
            )

    return out


def _already_failed(payload: Any) -> bool:
    """True when a field already carries a single-field validation failure."""
    return isinstance(payload, dict) and payload.get("validation_failure") is not None


def _recompute_average(fields: dict) -> float:
    """D-07: average over returned fields, using POST-validation confidence."""
    if not fields:
        return 0.0
    confidences = [
        float(payload.get("confidence") or 0.0)
        for payload in fields.values()
        if isinstance(payload, dict)
    ]
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def validate_and_score(envelope: dict) -> dict:
    """Return a new envelope with post-validation confidences applied.

    Pure function: does not mutate `envelope`.
    """
    new_envelope = copy.deepcopy(envelope)
    fields = new_envelope.get("fields", {}) or {}
    fields = _apply_single_field_rules(fields)
    fields = _apply_cross_field_rules(fields)
    new_envelope["fields"] = fields
    new_envelope["average_confidence"] = _recompute_average(fields)
    return new_envelope
