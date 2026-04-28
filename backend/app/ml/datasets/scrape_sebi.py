"""SEBI Adjudication Orders scraper — Phase 10 training data sourcing.

Per `10-RESEARCH.md` section 4, SEBI adjudication orders (publicly available
at sebi.gov.in/enforcement/orders) are the highest-volume reliable source of
real Indian regulatory notice text — thousands of orders, structured metadata
(party, date, sections, penalty), full text in PDF form.

This module produces labeled training examples for the BERT classifier and
risk-scorer training pipelines. Each scraped order is persisted to:

    backend/datasets/sebi/{order_year}/{order_id}.json
    backend/datasets/sebi/{order_year}/{order_id}.pdf

The JSON metadata schema:

    {
        "order_id": "AO/SS/MS/2024-25/123",
        "order_date": "2024-08-15",
        "authority": "SEBI",
        "notice_type": "adjudication_order",
        "party": "Acme Securities Pvt Ltd",
        "sections_cited": ["Section 11(1)", "Regulation 4(1)"],
        "penalty_inr": 500000,
        "pdf_url": "https://www.sebi.gov.in/.../AO123.pdf",
        "pdf_path": "datasets/sebi/2024-25/AO_SS_MS_2024-25_123.pdf",
        "scraped_at": "2026-04-28T10:30:00Z",
    }

Architecture:
- `parse_listing_page(html)` — pure function, deterministic, testable
- `download_order(metadata)` — HTTP I/O, separate from parsing
- `extract_metadata_from_pdf(pdf_path)` — reuses v1.0 PDF pipeline
- `scrape_orders(start_date, end_date, output_dir, max_orders)` — orchestrator

Rate limiting: 1 request per 2 seconds (be respectful of sebi.gov.in).
Resumable: skip orders already scraped (check filename existence).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# SEBI listing pages are at sebi.gov.in/sebiweb/home/HomeAction.do — but the
# real listing UI is JavaScript-driven. The static fallback is the
# enforcement orders index page. For initial scraping, point at the
# direct PDF order index (HTML-only, no JS).
SEBI_BASE_URL = "https://www.sebi.gov.in"
SEBI_ORDERS_LISTING_PATH = "/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=2&smid=10"

# IMPORTANT: validated 2026-04-28 against live sebi.gov.in. The default
# listing URL above returns mostly JS bootstrap and the order table is
# rendered client-side via AJAX. Static HTML scraping yields 0 orders.
#
# Two paths forward when operator wants to actually run this scraper:
#  (a) Capture the AJAX endpoint(s) the page calls (browser DevTools →
#      Network tab → filter XHR while clicking "Submit"). Replace
#      fetch_listing_page with a POST to that endpoint, parsing the JSON
#      response shape.
#  (b) Use Playwright/Selenium to render JS, then feed the rendered DOM
#      into parse_listing_page. Adds heavy dep; reserve for production.
#
# The pure parser functions (parse_listing_page, extract_metadata_from_text)
# work correctly against well-formed table HTML and have unit tests.
# They're ready to consume real markup once the right endpoint is wired.

# Polite scraping: 2-second minimum between requests.
RATE_LIMIT_DELAY_SECONDS = 2.0

# Output directory (mounted via docker-compose backend/datasets volume).
DEFAULT_OUTPUT_DIR = Path("/app/datasets/sebi")


@dataclass
class SEBIOrder:
    """Structured metadata for one adjudication order."""

    order_id: str
    order_date: date
    party: str
    pdf_url: str
    sections_cited: list[str] = field(default_factory=list)
    penalty_inr: Decimal | None = None
    full_text: str | None = None  # populated after PDF extraction
    pdf_path: str | None = None
    authority: str = "SEBI"
    notice_type: str = "adjudication_order"
    scraped_at: str | None = None  # ISO 8601 string

    def to_jsonable(self) -> dict:
        """Convert to JSON-serializable dict (dates → ISO, Decimal → str)."""
        d = asdict(self)
        d["order_date"] = self.order_date.isoformat() if self.order_date else None
        d["penalty_inr"] = str(self.penalty_inr) if self.penalty_inr is not None else None
        return d


# ----------------------------------------------------------------------
# Pure parser functions (testable, no I/O)
# ----------------------------------------------------------------------

# SEBI order numbers follow patterns like "AO/SS/MS/2024-25/123" or
# "Order/AO/MM/CR/123/2024" — capture variants.
SEBI_ORDER_ID_PATTERN = re.compile(
    r"\b(?:AO|Order|WTM)[/-][A-Z0-9/-]+\d{2,4}(?:-\d{2})?[/-]?\d{1,5}\b",
    re.IGNORECASE,
)

# Indian penalty amount in SEBI orders: "Rs. 5,00,000/-", "₹ 25 lakhs", "INR 1 crore"
PENALTY_PATTERN = re.compile(
    r"(?:Rs\.?|₹|INR)\s*"
    r"(\d{1,3}(?:[,.]\d{2,3})*(?:\.\d+)?)"
    r"\s*(crore|lakh|lakhs|cr|l)?",
    re.IGNORECASE,
)

# Section / regulation references in SEBI orders.
SECTION_PATTERN = re.compile(
    r"\b(?:Section|Regulation|Rule|Reg\.?|Sec\.?)\s+(\d+(?:\([0-9a-z]+\))*)",
    re.IGNORECASE,
)

# Date patterns commonly used in SEBI: "15-Aug-2024", "August 15, 2024", "15.08.2024"
ORDER_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})[\s./-](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"[\s,./-](\d{4})\b",
    re.IGNORECASE,
)


def parse_listing_page(html: str) -> list[SEBIOrder]:
    """Parse a SEBI orders listing HTML page into SEBIOrder records.

    The listing pages typically have a table where each row links to a PDF
    order document. This parser extracts the visible metadata (party, date,
    PDF link, order number) — full text + sections + penalty are populated
    later from the PDF itself via `extract_metadata_from_pdf`.

    Args:
        html: Raw HTML of a SEBI listing page.

    Returns:
        List of SEBIOrder records with order_id, order_date, party, pdf_url.
        Other fields are populated downstream.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "beautifulsoup4 required for SEBI scraper. "
            "Run: pip install beautifulsoup4 lxml"
        ) from exc

    soup = BeautifulSoup(html, "lxml")
    orders: list[SEBIOrder] = []

    # SEBI listing layout: a single <table> with rows where each cell has
    # the order title, party, and a PDF link in column 3. Adapt to actual
    # markup once we have a real fixture.
    for row in soup.find_all("tr"):
        link = row.find("a", href=True)
        if not link:
            continue
        href = link["href"]
        if not href.lower().endswith(".pdf"):
            continue

        link_text = link.get_text(strip=True)
        # The party name typically lives in the <td> surrounding the link,
        # not inside the link text itself (which is usually just the order ID).
        context_text = (
            link.parent.get_text(" ", strip=True)
            if link.parent is not None
            else row.get_text(" ", strip=True)
        )

        order_id_match = SEBI_ORDER_ID_PATTERN.search(link_text) or \
            SEBI_ORDER_ID_PATTERN.search(context_text)
        if not order_id_match:
            continue
        order_id = order_id_match.group(0)

        order_date = _extract_order_date(context_text)
        if order_date is None:
            continue

        party = _extract_party_name(context_text)

        pdf_url = href if href.startswith("http") else f"{SEBI_BASE_URL}{href}"

        orders.append(
            SEBIOrder(
                order_id=order_id,
                order_date=order_date,
                party=party,
                pdf_url=pdf_url,
            )
        )

    return orders


def extract_metadata_from_text(full_text: str) -> dict:
    """Extract sections cited + penalty amount from the full PDF text.

    Pure function — tests can pass arbitrary text strings.

    Returns:
        dict with keys: sections_cited (list[str]), penalty_inr (Decimal | None)
    """
    sections = list({m.group(0) for m in SECTION_PATTERN.finditer(full_text)})

    penalty_inr: Decimal | None = None
    best_match_value: Decimal = Decimal("0")
    for match in PENALTY_PATTERN.finditer(full_text):
        amount_str = match.group(1).replace(",", "")
        unit = (match.group(2) or "").lower()
        try:
            base_value = Decimal(amount_str)
        except (ValueError, ArithmeticError):
            continue
        # Indian unit conversions.
        if unit in ("crore", "cr"):
            base_value *= Decimal("10000000")
        elif unit in ("lakh", "lakhs", "l"):
            base_value *= Decimal("100000")
        # Take the largest mentioned amount as the headline penalty.
        if base_value > best_match_value:
            best_match_value = base_value
            penalty_inr = base_value

    return {
        "sections_cited": sorted(sections),
        "penalty_inr": penalty_inr,
    }


def _extract_order_date(text: str) -> date | None:
    match = ORDER_DATE_PATTERN.search(text)
    if not match:
        return None
    day, month_abbr, year = match.groups()
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month = month_map.get(month_abbr[:3].lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _extract_party_name(title_text: str) -> str:
    """Heuristic party-name extractor from a listing row's title.

    SEBI titles typically look like:
        "Adjudication order in the matter of Acme Securities Pvt Ltd dated ..."

    Strip prefix boilerplate; keep up to the first 'dated' / 'AO' / pattern.
    """
    cleaned = re.sub(
        r"^(adjudication order|order)\s+in\s+the\s+matter\s+of\s+",
        "",
        title_text,
        flags=re.IGNORECASE,
    )
    cleaned = re.split(r"\s+(?:dated|AO|\(|order)", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip(" -|")[:200]


# ----------------------------------------------------------------------
# I/O orchestration (network + filesystem; covered by integration tests)
# ----------------------------------------------------------------------


def fetch_listing_page(client, page: int = 1) -> str:
    """Fetch one SEBI orders listing page. Caller provides an httpx.Client.

    Args:
        client: An httpx.Client with timeout configured.
        page: 1-indexed page number for pagination.

    Returns:
        Raw HTML of the listing page.
    """
    url = f"{SEBI_BASE_URL}{SEBI_ORDERS_LISTING_PATH}&pg={page}"
    logger.info("Fetching SEBI listing page %d: %s", page, url)
    response = client.get(url)
    response.raise_for_status()
    return response.text


def download_order_pdf(client, order: SEBIOrder, output_dir: Path) -> Path:
    """Download the PDF for an order to disk. Returns the local path."""
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", order.order_id)
    year_dir = output_dir / str(order.order_date.year if order.order_date else "unknown")
    year_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = year_dir / f"{safe_id}.pdf"
    if pdf_path.exists():
        logger.debug("Already downloaded: %s", pdf_path)
        return pdf_path

    logger.info("Downloading %s -> %s", order.pdf_url, pdf_path)
    response = client.get(order.pdf_url)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    return pdf_path


def write_order_metadata(order: SEBIOrder, output_dir: Path) -> Path:
    """Persist a SEBIOrder record as a JSON sidecar next to the PDF."""
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", order.order_id)
    year_dir = output_dir / str(order.order_date.year if order.order_date else "unknown")
    year_dir.mkdir(parents=True, exist_ok=True)
    json_path = year_dir / f"{safe_id}.json"
    json_path.write_text(json.dumps(order.to_jsonable(), indent=2, ensure_ascii=False))
    return json_path


def scrape_orders(
    *,
    start_page: int = 1,
    end_page: int | None = None,
    max_orders: int = 100,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    rate_limit_seconds: float = RATE_LIMIT_DELAY_SECONDS,
) -> Iterable[SEBIOrder]:
    """Top-level orchestrator. Yields successfully scraped SEBIOrder records.

    Args:
        start_page: 1-indexed starting page.
        end_page: Inclusive end page; None = scrape until empty.
        max_orders: Hard cap on total orders scraped (safety).
        output_dir: Where to write PDFs + JSON metadata.
        rate_limit_seconds: Minimum delay between HTTP requests.

    Yields:
        SEBIOrder records with `pdf_path` populated.

    NOTE: Untested against live sebi.gov.in HTML in this session. Run with
    a small max_orders=5 first to validate the parser handles real markup.
    Adjust `parse_listing_page` selectors based on actual layout.
    """
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover
        raise ImportError("httpx required for SEBI scraper") from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "smart-docs-iiit-research/1.0 (+IIIT Hyderabad Product Labs)",
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    page = start_page
    scraped_count = 0
    last_request_at = 0.0

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        while True:
            if end_page is not None and page > end_page:
                break
            if scraped_count >= max_orders:
                break

            # Rate limit.
            elapsed = time.monotonic() - last_request_at
            if elapsed < rate_limit_seconds:
                time.sleep(rate_limit_seconds - elapsed)
            last_request_at = time.monotonic()

            html = fetch_listing_page(client, page=page)
            orders = parse_listing_page(html)
            if not orders:
                logger.info("Empty page %d, stopping", page)
                break

            for order in orders:
                if scraped_count >= max_orders:
                    break

                # Download PDF.
                elapsed = time.monotonic() - last_request_at
                if elapsed < rate_limit_seconds:
                    time.sleep(rate_limit_seconds - elapsed)
                last_request_at = time.monotonic()

                try:
                    pdf_path = download_order_pdf(client, order, output_dir)
                except Exception:
                    logger.exception("Failed to download %s, skipping", order.order_id)
                    continue

                order.pdf_path = str(pdf_path.relative_to(output_dir))
                order.scraped_at = datetime.now(timezone.utc).isoformat()

                write_order_metadata(order, output_dir)
                yield order
                scraped_count += 1

            page += 1

    logger.info("SEBI scrape complete: %d orders saved to %s", scraped_count, output_dir)
