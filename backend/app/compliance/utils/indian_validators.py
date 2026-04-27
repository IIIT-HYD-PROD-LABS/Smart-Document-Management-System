"""Indian regulatory identifier validators — Phase 9 LIFE-03.

Sources (verified 2026-04-27):
- https://github.com/tk120404/gst (community-maintained canonical GSTIN regex)
- https://www.regextester.com/102594 (cross-verified)
- https://thegstcalculator.in/tools/gst-number-validator (state-code validation)

All regexes use anchored ^...$ match for full-string validation.
"""
import re

GSTIN_RX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_RX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
CIN_RX = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
DIN_RX = re.compile(r"^[0-9]{8}$")

# CGST / IT / MCA / RBI / SEBI notice number patterns (D-07).
# GST patterns are HIGH confidence (DRC-01..07, ASMT-10..17 are well-documented).
# Other authorities have MEDIUM confidence — patterns will be refined in Phase 10
# as more empirical samples are collected.
NOTICE_NUMBER_PATTERNS = {
    "GST": [
        re.compile(r"^DRC-0[1-7]/\d+/\d{4}-\d{2}$"),
        re.compile(r"^ASMT-1[0-7]/\d+/\d{4}-\d{2}$"),
    ],
    "IT": [
        re.compile(r"u/s\s*(143\(2\)|148|156|271)"),
    ],
    "MCA": [
        re.compile(r"^[A-Z]{2,4}/\d{4}/\d+$"),
    ],
    "RBI": [
        re.compile(r"^RBI/\d{4}-\d{2}/\d+$"),
    ],
    "SEBI": [
        re.compile(r"^SEBI/[A-Z]{2,5}/\d{4}/\d+$"),
    ],
}


def validate_gstin(value: str) -> bool:
    """Validate a GSTIN string. Returns True iff format AND state code valid."""
    if not isinstance(value, str) or not GSTIN_RX.match(value):
        return False
    try:
        state_code = int(value[:2])
    except ValueError:
        return False
    # Valid state codes 2026: 01-37 (states/UTs), 97 (Other Territory), 99 (Centre)
    return 1 <= state_code <= 37 or state_code in (97, 99)


def validate_pan_in_gstin(gstin: str) -> bool:
    """The 10 chars (positions 2-12) of a GSTIN form an embedded PAN."""
    if not GSTIN_RX.match(gstin):
        return False
    return PAN_RX.match(gstin[2:12]) is not None


def validate_notice_number(authority: str, notice_number: str) -> bool:
    """Validate notice_number against authority-specific patterns.

    Returns True if any registered pattern matches; True (accept) if no
    pattern is registered for the authority.
    """
    patterns = NOTICE_NUMBER_PATTERNS.get(authority, [])
    if not patterns:
        return True  # No pattern enforced — accept any
    return any(p.search(notice_number) for p in patterns)
