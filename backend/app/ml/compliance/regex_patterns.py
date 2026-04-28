"""Indian compliance regex patterns (deterministic, regex-first per CLASS-06).

These patterns have 100% precision on well-formed inputs and run before spaCy NER.
On conflict between regex and NER, regex wins.

Patterns implemented per Phase 10 CONTEXT D-09:
- GSTIN: 15-char with state code + PAN check
- PAN: 10-char alphanumeric (5 letters + 4 digits + 1 letter)
- CIN: 21-char company identifier
- DIN: 8-digit director identifier
- Section reference: u/s 143(2), Section 271, Rule 96(10), etc.
"""

import re

# State code (01-37) + PAN (10) + Entity (1) + Z + Checksum (1) = 15 chars
GSTIN_PATTERN = re.compile(
    r"\b(0[1-9]|[1-2][0-9]|3[0-7])"          # state code
    r"([A-Z]{5}[0-9]{4}[A-Z])"                # embedded PAN
    r"([1-9A-Z])"                              # entity number
    r"Z"                                       # constant Z
    r"([0-9A-Z])\b",                          # checksum
    re.IGNORECASE,
)

# 5 uppercase letters + 4 digits + 1 uppercase letter
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)

# L/U + 5-digit industry code + state code + year + entity type + 6-digit registration
CIN_PATTERN = re.compile(
    r"\b[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b",
    re.IGNORECASE,
)

DIN_PATTERN = re.compile(r"\b[0-9]{8}\b")

# u/s 143(2), Section 271(1)(c), Rule 96(10)(b), s. 132
SECTION_REFERENCE_PATTERN = re.compile(
    r"\b(?:u/s|Section|Sec\.?|s\.|Rule)\s*"
    r"(\d+(?:\([0-9a-z]+\))*)",
    re.IGNORECASE,
)

# Notice numbers per authority
GST_NOTICE_NUMBER_PATTERN = re.compile(
    r"\b(?:DRC|ASMT|REG|RFD|CMP|GSTR)[-/]?\s*\d{2}[-/]?\s*\d{4}\b",
    re.IGNORECASE,
)

IT_NOTICE_NUMBER_PATTERN = re.compile(
    r"\bu/s\s*(143|142|156|245|271|144|148)\b",
    re.IGNORECASE,
)


def extract_gstins(text: str) -> list[str]:
    """Return all GSTINs found in text, normalized to uppercase, deduplicated."""
    return list({m.group(0).upper() for m in GSTIN_PATTERN.finditer(text)})


def extract_pans(text: str) -> list[str]:
    """Return all PANs found in text, normalized to uppercase, deduplicated.

    Note: GSTIN contains an embedded PAN. Callers should extract GSTINs first
    and exclude their PAN substring to avoid double-counting.
    """
    return list({m.group(0).upper() for m in PAN_PATTERN.finditer(text)})


def extract_cins(text: str) -> list[str]:
    """Return all CINs found in text, normalized to uppercase, deduplicated."""
    return list({m.group(0).upper() for m in CIN_PATTERN.finditer(text)})


def extract_section_references(text: str) -> list[str]:
    """Return all legal section references found in text, deduplicated."""
    return list({m.group(0) for m in SECTION_REFERENCE_PATTERN.finditer(text)})
