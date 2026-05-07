"""Compliance sender domains + subject keywords (D-16 v2.0 rule-based detector).

v2.1 swap path: replace this file's data with a call to a BERT classifier;
schema, status workflow, and review queue routing all stay unchanged.

Per reconciliation #2 (research): D-17's spaCy NER reuse is broken
(ner.py:49 raises NotImplementedError). Body extraction uses the existing
regex_patterns.py (GSTIN/PAN/CIN/section refs) + the v1.0 LLM service for
narrative fields — NOT ner.py.
"""
from __future__ import annotations

import re

# Reconciliation #4: RBI's correct domain is rbi.org.in (NOT gov.in).
# Curated 2026-05-07 from web.guidelines.gov.in/2-2-government-domains and
# ministry portals. Operator-tunable via gmail_filter_rules; this is seed only.
COMPLIANCE_SENDER_PATTERNS: list[re.Pattern] = [
    re.compile(r"@([a-z]+\.)?gov\.in$", re.IGNORECASE),
    re.compile(r"@([a-z]+\.)?nic\.in$", re.IGNORECASE),
    re.compile(r"@cbic-gst\.gov\.in$", re.IGNORECASE),
    re.compile(r"@incometax\.gov\.in$", re.IGNORECASE),
    re.compile(r"@incometaxindiaefiling\.gov\.in$", re.IGNORECASE),
    re.compile(r"@mca\.gov\.in$", re.IGNORECASE),
    re.compile(r"@sebi\.gov\.in$", re.IGNORECASE),
    re.compile(r"@rbi\.org\.in$", re.IGNORECASE),
    re.compile(r"@epfindia\.gov\.in$", re.IGNORECASE),
    re.compile(r"@esic\.in$", re.IGNORECASE),
]

COMPLIANCE_SUBJECT_KEYWORDS: re.Pattern = re.compile(
    r"\b(notice|intimation|demand|scrutiny|show.cause|adjudication|"
    r"assessment\s*order|penalty|hearing|summons|inquiry)\b",
    re.IGNORECASE,
)


# D-39: minimum body length to justify persisting an email body as a
# Document for v1.0 ML classification. Below this, the body is unlikely
# to carry enough signal for the TF-IDF classifier (which itself requires
# >=50 chars in classify_document) and risks polluting the listing with
# auto-replies, signatures, and unsubscribe footers.
MIN_BODY_LENGTH_FOR_CLASSIFICATION: int = 200


# Sender-domain → ComplianceNotice.authority mapping. authority CHECK
# constraint requires one of GST|IT|MCA|RBI|SEBI; default to GST when
# only matches the broad gov.in / nic.in pattern.
AUTHORITY_BY_DOMAIN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"cbic-gst\.gov\.in", re.IGNORECASE), "GST"),
    (re.compile(r"gst\.gov\.in", re.IGNORECASE), "GST"),
    (re.compile(r"incometax\.gov\.in", re.IGNORECASE), "IT"),
    (re.compile(r"incometaxindiaefiling\.gov\.in", re.IGNORECASE), "IT"),
    (re.compile(r"mca\.gov\.in", re.IGNORECASE), "MCA"),
    (re.compile(r"sebi\.gov\.in", re.IGNORECASE), "SEBI"),
    (re.compile(r"rbi\.org\.in", re.IGNORECASE), "RBI"),
]


def authority_from_sender(sender: str) -> str:
    """Map a sender email/domain to a valid ComplianceNotice.authority value.

    Returns 'GST' as the default when only the broad gov.in/nic.in pattern
    matches — concrete domains are preferred. Caller guarantees the sender
    matched COMPLIANCE_SENDER_PATTERNS first.
    """
    for pattern, authority in AUTHORITY_BY_DOMAIN:
        if pattern.search(sender):
            return authority
    return "GST"
