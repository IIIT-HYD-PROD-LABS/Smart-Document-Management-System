"""Metadata extraction from document text -- dates, amounts, and vendor names."""
import re
from dateutil.parser import parse as dateutil_parse
import structlog

logger = structlog.stdlib.get_logger()


def extract_metadata(text: str) -> dict:
    """Extract date, amount, and vendor metadata from document text.

    Returns dict with keys: dates (list[str]), amounts (list[dict]), vendor (str|None).
    """
    if not text or len(text.strip()) < 10:
        return {"dates": [], "amounts": [], "vendor": None}

    if len(text) > 100_000:
        text = text[:100_000]

    metadata = {
        "dates": extract_dates(text),
        "amounts": extract_amounts(text),
        "vendor": extract_vendor(text),
    }
    logger.info(
        "metadata_extracted",
        date_count=len(metadata["dates"]),
        amount_count=len(metadata["amounts"]),
        has_vendor=metadata["vendor"] is not None,
    )
    return metadata


def extract_dates(text: str) -> list[str]:
    """Extract dates from text using regex patterns + dateutil fuzzy parsing.

    Returns ISO format date strings (YYYY-MM-DD). Deduplicates and limits to 5.
    Validates year is between 2000 and 2030 to filter false positives.
    """
    patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
    ]
    dates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                parsed = dateutil_parse(match.group(), fuzzy=True, dayfirst=True)
                if 2000 <= parsed.year <= 2030:
                    dates.append(parsed.strftime("%Y-%m-%d"))
            except (ValueError, OverflowError):
                continue
    return list(dict.fromkeys(dates))[:5]


def extract_amounts(text: str) -> list[dict]:
    """Extract currency amounts (INR and USD) from text.

    Returns list of dicts with 'amount' (float) and 'currency' (str).
    Filters amounts between 0.01 and 10,000,000 to avoid false positives.
    """
    patterns = [
        (r'(?:Rs\.?|INR|₹)\s*([\d,]{1,20}\.?\d*)', 'INR'),
        (r'\$\s*([\d,]{1,20}\.?\d*)', 'USD'),
        (r'(?:Total|Amount|Grand Total|Net Amount|Net Payable)[:\s]*(?:Rs\.?|INR|₹|\$)?\s*([\d,]{1,20}\.?\d*)', 'INR'),
    ]
    amounts = []
    seen = set()
    for pattern, currency in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value_str = match.group(1).replace(',', '')
            try:
                value = float(value_str)
                if 0.01 <= value <= 10_000_000 and value not in seen:
                    amounts.append({"amount": value, "currency": currency})
                    seen.add(value)
            except ValueError:
                continue
    return amounts[:10]


def extract_vendor(text: str) -> str | None:
    """Extract vendor/company name from document text.

    Strategy:
    1. Look for explicit vendor keywords (From:, Vendor:, Seller:, etc.)
    2. Fallback: use first substantive line as vendor heuristic

    Returns vendor name (max 100 chars) or None.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()][:15]

    # Strategy 1: Look for vendor keywords
    vendor_keywords = [
        'from:', 'vendor:', 'seller:', 'biller:', 'company:',
        'merchant:', 'paid to:', 'payee:', 'issued by:',
    ]
    for line in lines:
        lower = line.lower()
        for keyword in vendor_keywords:
            if keyword in lower:
                vendor = line[lower.index(keyword) + len(keyword):].strip()
                if vendor and len(vendor) > 2:
                    return vendor[:100]

    # Strategy 2: First non-trivial line that isn't a date or number
    for line in lines[:5]:
        if len(line) > 3 and not re.match(r'^[\d\s/.,:-]+$', line):
            if not re.match(r'^\+?\d[\d\s-]{7,}$', line):
                return line[:100]

    return None
