"""Regex fallback notice-field extraction when AI is unavailable.

Used by extract-preview and auto-extract so uploading a GST/IT PDF still
pre-fills whatever structural fields we can recover (GSTIN, PAN, notice
number patterns, section refs, amounts) without a BYOK / server LLM key.
"""
from __future__ import annotations

import re
from typing import Any


# Common Indian notice number shapes: DRC-01/2026/12345, SCN/IT/2024/88, etc.
_NOTICE_NUMBER_RE = re.compile(
    r"\b("
    r"DRC-?0?1[/\-][A-Za-z0-9/\-]{4,40}"
    r"|SCN[/\-][A-Za-z0-9/\-]{4,40}"
    r"|ITBA[/\-][A-Za-z0-9/\-]{4,40}"
    r"|F\.?\s*No\.?\s*[A-Za-z0-9/\-]{6,40}"
    r")\b",
    re.IGNORECASE,
)

_AMOUNT_RE = re.compile(
    r"(?:tax\s*demand|demand\s*of\s*tax|total\s*demand|amount\s*demanded)"
    r"[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_PENALTY_RE = re.compile(
    r"(?:penalty)[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_INTEREST_RE = re.compile(
    r"(?:interest)[:\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{1,2}\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b",
    re.IGNORECASE,
)

_AUTHORITY_HINTS = [
    (re.compile(r"\bGST|CGST|SGST|IGST|DRC-?0?1\b", re.I), "GST"),
    (re.compile(r"\bIncome\s*Tax|ITBA|u/?s\s*143|u/?s\s*148\b", re.I), "IT"),
    (re.compile(r"\bMCA|Companies\s*Act|ROC\b", re.I), "MCA"),
    (re.compile(r"\bSEBI\b", re.I), "SEBI"),
    (re.compile(r"\bRBI\b", re.I), "RBI"),
]


def _field(value: Any, confidence: float = 0.7) -> dict:
    return {"value": value, "confidence": confidence}


def extract_notice_fields_regex(text: str) -> dict:
    """Return an extraction envelope shaped like the AI path.

    Never raises. Empty text yields an empty fields dict with avg 0.0.
    """
    text = text or ""
    fields: dict[str, dict] = {}

    try:
        from app.ml.compliance import regex_patterns

        gstins = regex_patterns.extract_gstins(text)
        if gstins:
            fields["gstin"] = _field(gstins[0], 0.85)
        pans = regex_patterns.extract_pans(text)
        if pans:
            fields["pan"] = _field(pans[0], 0.85)
        sections = regex_patterns.extract_section_references(text)
        if sections:
            fields["legal_sections"] = _field(sections[:8], 0.7)
    except Exception:
        pass

    m = _NOTICE_NUMBER_RE.search(text)
    if m:
        fields["notice_number"] = _field(m.group(1).strip(), 0.75)

    for pattern, authority in _AUTHORITY_HINTS:
        if pattern.search(text):
            fields["authority"] = _field(authority, 0.7)
            break

    for key, rx in (
        ("tax_demand", _AMOUNT_RE),
        ("penalty", _PENALTY_RE),
        ("interest", _INTEREST_RE),
    ):
        am = rx.search(text)
        if am:
            raw = am.group(1).replace(",", "")
            try:
                fields[key] = _field(f"{float(raw):.2f}", 0.65)
            except ValueError:
                pass

    dates = _DATE_RE.findall(text)
    if dates:
        # First date often issued_date; second may be deadline — best-effort.
        fields.setdefault("issued_date", _field(dates[0], 0.55))
        if len(dates) > 1:
            fields.setdefault("response_deadline", _field(dates[1], 0.5))

    confidences = [float(p["confidence"]) for p in fields.values()]
    avg = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    return {
        "fields": fields,
        "average_confidence": avg,
        "model": "regex_fallback",
        "provider": "local",
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
    }
