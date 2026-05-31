"""Coercion of extracted notice field values onto typed canonical columns.

Single source of truth for turning the loosely-typed values that come back
from the LLM extractor (or a user editing them in the review form) into the
exact Python types the ComplianceNotice columns require:

  - tax_demand / interest / penalty / total_liability -> Decimal (Numeric(18,2))
  - issued_date -> received_date, response_deadline    -> datetime.date (Date)
  - authority                                          -> one of VALID_AUTHORITIES
  - notice_number                                      -> str(<=100)

Why this exists (Phase 17 hardening):
    The accept-extraction endpoint and the async auto-apply path previously
    wrote ``item.value`` (typed ``Any``) straight onto Numeric/Date columns
    via ``setattr``. A currency-formatted amount ("₹1,45,000"), a
    comma-grouped number, a "Rs. 1.45 lakh" phrase, or a DD-MM-YYYY date —
    all routine in OCR'd Indian tax notices even though the prompt asks for
    ISO/plain values — reached psycopg2 as a raw string and raised
    StatementError / DataError, neither of which the callers caught, so the
    request 500'd or the worker marked the whole extraction failed.

    These coercers normalise the value first and raise ``CoercionError`` for
    anything that cannot be represented, so the boundary fails cleanly (HTTP
    422 on the sync path, skip-the-field on the async path) instead of
    corrupting the request with a DB-level 500.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Optional

from app.compliance.models.notice import VALID_AUTHORITIES


class CoercionError(ValueError):
    """A non-empty extracted value cannot be coerced to its column type."""


# ── amounts ──────────────────────────────────────────────────────────────

# Indian-numbering multiplier words. Notices frequently write demands as
# "Rs. 1.45 lakh" / "₹2 crore" rather than the plain integer the prompt asks
# for, so we honour the suffix instead of rejecting the value.
_AMOUNT_MULTIPLIERS: dict[str, Decimal] = {
    "crores": Decimal(10**7),
    "crore": Decimal(10**7),
    "cr": Decimal(10**7),
    "lakhs": Decimal(10**5),
    "lakh": Decimal(10**5),
    "lacs": Decimal(10**5),
    "lac": Decimal(10**5),
}
_CURRENCY_TOKENS = ("₹", "rs.", "rs", "inr", "rupees", "rupee", "/-")
# Numeric(18, 2) -> at most 16 integer digits before the decimal point.
_AMOUNT_MAX = Decimal(10) ** 16


def _parse_amount_str(raw: str) -> Decimal:
    s = raw.strip().lower()
    for tok in _CURRENCY_TOKENS:
        s = s.replace(tok, " ")
    s = s.replace(",", "")
    multiplier = Decimal(1)
    for word, m in _AMOUNT_MULTIPLIERS.items():
        if re.search(rf"\b{word}\b", s):
            multiplier = m
            s = re.sub(rf"\b{word}\b", " ", s)
            break
    match = re.search(r"-?\d+(?:\.\d+)?", s)
    if match is None:
        raise CoercionError(f"could not parse amount from {raw!r}")
    try:
        return Decimal(match.group(0)) * multiplier
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise CoercionError(f"could not parse amount from {raw!r}") from exc


def coerce_amount(raw: Any) -> Optional[Decimal]:
    """Return a 2-dp Decimal for a money column, or None when blank.

    Raises CoercionError for a non-blank value that is not a valid amount or
    that overflows Numeric(18, 2).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise CoercionError("boolean is not a valid amount")
    if isinstance(raw, Decimal):
        value = raw
    elif isinstance(raw, (int, float)):
        value = Decimal(str(raw))
    else:
        text = str(raw).strip()
        if not text:
            return None
        value = _parse_amount_str(text)
    try:
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise CoercionError(f"amount {raw!r} is out of range") from exc
    if abs(value) >= _AMOUNT_MAX:
        raise CoercionError(f"amount {raw!r} exceeds Numeric(18, 2) range")
    return value


# ── dates ────────────────────────────────────────────────────────────────

# ISO is the contract; the rest are the formats real Indian notices use.
_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%Y/%m/%d",
)


def coerce_date(raw: Any) -> Optional[date]:
    """Return a datetime.date for a Date column, or None when blank.

    Accepts ISO 8601 plus common DD-MM-YYYY / DD Mon YYYY notice formats.
    Raises CoercionError for a non-blank value that is not a parseable date.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise CoercionError(f"could not parse date from {raw!r}")


# ── strings / authority ──────────────────────────────────────────────────


def coerce_str(raw: Any, *, max_len: Optional[int] = None) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text[:max_len] if max_len else text


def coerce_notice_number(raw: Any) -> Optional[str]:
    return coerce_str(raw, max_len=100)


def coerce_authority(raw: Any) -> Optional[str]:
    """Return one of VALID_AUTHORITIES (upper-cased) or None when blank.

    Raises CoercionError for a non-blank value outside the allowed set so it
    never reaches the ck_notices_authority CHECK constraint as a 500.
    """
    text = coerce_str(raw)
    if text is None:
        return None
    upper = text.upper()
    if upper not in VALID_AUTHORITIES:
        raise CoercionError(
            f"authority {text!r} is not one of {VALID_AUTHORITIES}"
        )
    return upper


# ── field -> (column, coercer) map ───────────────────────────────────────
#
# Mirrors the FIELD_SCHEMA keys the extractor owns and the canonical columns
# they back-populate. The accept-extraction endpoint and the auto-apply path
# both drive off this single map so the two write paths can never diverge.
FIELD_COERCERS: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "notice_number": ("notice_number", coerce_notice_number),
    "authority": ("authority", coerce_authority),
    "issued_date": ("received_date", coerce_date),
    "response_deadline": ("response_deadline", coerce_date),
    "tax_demand": ("tax_demand", coerce_amount),
    "interest": ("interest", coerce_amount),
    "penalty": ("penalty", coerce_amount),
    "total_liability": ("total_liability", coerce_amount),
}
