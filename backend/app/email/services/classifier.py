"""Rule-based compliance + filter-rule router — Phase 15 EMAIL-04/06.

v2.0: regex on sender domain + subject keywords, operator filter rules
(priority ASC wins), and bill-domain heuristics.

v2.1: replace classify() body with BERT; resolve_route() stays the single
entry point for the scanner.
"""
from __future__ import annotations

import email.utils
import re
from typing import Any, Optional, Sequence

from app.email.classifier_rules import (
    COMPLIANCE_SENDER_PATTERNS,
    COMPLIANCE_SUBJECT_KEYWORDS,
)

# Keep route constants local so unit tests can import this module without
# loading SQLAlchemy models / Settings (async engine).
ROUTE_COMPLIANCE = "compliance_notice"
ROUTE_BILL = "bill"
ROUTE_DMS_ONLY = "dms_only"
ROUTE_IGNORE = "ignore"

# Lightweight bill sender heuristics (aligned with bill_extractor categories).
# Used when no operator filter rule matches.
_BILL_SENDER_HINTS = re.compile(
    r"("
    r"tatapower|adanielectricity|reliancepower|electricity|bescom|kseb|tneb|"
    r"gail|igl|mahanagargas|"
    r"airtel|jio|vodafone|bsnl|hathway|"
    r"hdfcbank|icicibank|sbicard|axisbank|kotak|amex|americanexpress|"
    r"netflix|primevideo|hotstar|spotify|"
    r"invoice|billing|billpay|payments?"
    r")",
    re.IGNORECASE,
)
_BILL_SUBJECT_HINTS = re.compile(
    r"\b(invoice|bill|statement|amount\s+due|payment\s+due|due\s+date|"
    r"auto[- ]?pay|subscription)\b",
    re.IGNORECASE,
)


def _sender_address(sender: str) -> str:
    """Bare address from a raw From header ('Name <a@b.in>' -> 'a@b.in').

    COMPLIANCE_SENDER_PATTERNS are $-anchored on the domain, so they must match
    the bare address, not the 'Display Name <addr>' form the From header carries.
    """
    addr = email.utils.parseaddr(sender or "")[1]
    return addr or (sender or "")


def classify(sender: str, subject: str) -> tuple[bool, float]:
    """Returns (is_compliance_notice, confidence).

    Cases:
      sender + subject match  -> (True, 1.0)  -> auto-create ComplianceNotice
      sender match only       -> (False, 0.5) -> Phase 10 review queue (CLASS-04)
      subject match only      -> (False, 0.0) -> dms_only per D-33 (forwarded)
      neither match           -> (False, 0.0) -> ignored
    """
    sender_match = any(p.search(_sender_address(sender)) for p in COMPLIANCE_SENDER_PATTERNS)
    subject_match = bool(COMPLIANCE_SUBJECT_KEYWORDS.search(subject or ""))
    if sender_match and subject_match:
        return True, 1.0
    if sender_match and not subject_match:
        return False, 0.5
    return False, 0.0


def _rule_matches(rule: Any, sender: str, subject: str) -> bool:
    """A rule matches when every non-empty pattern matches.

    Empty/None patterns are wildcards. label_include / label_exclude are
    reserved for future Gmail label wiring and ignored here (always pass).
    """
    sender = sender or ""
    subject = subject or ""
    addr = _sender_address(sender)
    sender_pat = str(getattr(rule, "sender_pattern", None) or "").strip()
    subject_pat = str(getattr(rule, "subject_pattern", None) or "").strip()
    if sender_pat:
        try:
            # Match the raw From and the bare address, so a $-anchored domain
            # rule still fires on the 'Display Name <addr>' form.
            if not (
                re.search(sender_pat, sender, re.IGNORECASE)
                or re.search(sender_pat, addr, re.IGNORECASE)
            ):
                return False
        except re.error:
            # Bad operator regex — treat as non-match rather than crash the scan.
            return False
    if subject_pat:
        try:
            if not re.search(subject_pat, subject, re.IGNORECASE):
                return False
        except re.error:
            return False
    # At least one positive criterion must be present so a blank rule never
    # vacuously routes every message.
    if not sender_pat and not subject_pat:
        return False
    return True


def resolve_route(
    sender: str,
    subject: str,
    *,
    body: str = "",
    rules: Optional[Sequence[Any]] = None,
) -> str:
    """Return route_taken for a message.

    Precedence:
      1. Enabled operator filter rules ordered by priority ASC, id ASC
      2. Built-in compliance classifier (sender+subject -> compliance_notice;
         sender only -> dms_only, later upgraded to review-queue notice)
      3. Bill heuristics on sender domain / subject
      4. ignore

    ``rules`` should already be filtered to the credential and ordered.
    """
    for rule in rules or ():
        if not bool(getattr(rule, "enabled", True)):
            continue
        if _rule_matches(rule, sender, subject):
            return str(rule.route_to)

    is_compliance, confidence = classify(sender, subject)
    if is_compliance and confidence >= 0.75:
        return ROUTE_COMPLIANCE
    if confidence == 0.5:
        # Uncertain regulatory mail — keep as dms_only for the message log,
        # but process_classified_email still creates a review-queue notice.
        return ROUTE_DMS_ONLY

    haystack = f"{sender} {subject}"
    if _BILL_SENDER_HINTS.search(haystack) or _BILL_SUBJECT_HINTS.search(subject or ""):
        return ROUTE_BILL

    # Body-only amount + "due" is a weak bill signal; only use when body present.
    if body and re.search(r"(?:INR|Rs\.?|₹)\s*[\d,]+", body, re.IGNORECASE):
        if re.search(r"\bdue\b", body, re.IGNORECASE):
            return ROUTE_BILL

    return ROUTE_IGNORE


def load_enabled_rules(db, credential_id: int) -> list:
    """Load enabled filter rules for a credential, priority ASC."""
    from app.email.models.filter_rule import GmailFilterRule

    return (
        db.query(GmailFilterRule)
        .filter(
            GmailFilterRule.credential_id == credential_id,
            GmailFilterRule.enabled.is_(True),
        )
        .order_by(GmailFilterRule.priority.asc(), GmailFilterRule.id.asc())
        .all()
    )
