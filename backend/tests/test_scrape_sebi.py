"""Phase 10 — SEBI scraper unit tests for the pure parser functions.

Tests cover the deterministic parsing logic (HTML → SEBIOrder, full text →
sections + penalty). Network / filesystem orchestration is integration-tested
separately when run against live sebi.gov.in.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.ml.datasets.scrape_sebi import (
    PENALTY_PATTERN,
    SECTION_PATTERN,
    SEBI_ORDER_ID_PATTERN,
    SEBIOrder,
    extract_metadata_from_text,
    parse_listing_page,
)


# ---- Penalty extraction ---------------------------------------------


def test_penalty_lakh_indian_format():
    """₹ 5 lakh → 500000."""
    text = "A penalty of Rs. 5 lakh is hereby levied."
    result = extract_metadata_from_text(text)
    assert result["penalty_inr"] == Decimal("500000")


def test_penalty_crore_indian_format():
    """₹ 2 crore → 20000000."""
    text = "Penalty of INR 2 crore imposed under Regulation 4(1)."
    result = extract_metadata_from_text(text)
    assert result["penalty_inr"] == Decimal("20000000")


def test_penalty_with_commas():
    """Rs. 5,00,000/- → 500000 (Indian comma format)."""
    text = "Adjudicating Officer hereby imposes a penalty of Rs. 5,00,000/- on the Noticee."
    result = extract_metadata_from_text(text)
    assert result["penalty_inr"] == Decimal("500000")


def test_penalty_picks_largest():
    """Multiple amounts: pick the largest (the headline penalty)."""
    text = (
        "Initial demand of Rs. 50,000 was issued. "
        "Final penalty of Rs. 25,00,000/- imposed."
    )
    result = extract_metadata_from_text(text)
    assert result["penalty_inr"] == Decimal("2500000")


def test_no_penalty_returns_none():
    text = "This order is hereby disposed of with a warning."
    result = extract_metadata_from_text(text)
    assert result["penalty_inr"] is None


# ---- Section extraction ---------------------------------------------


def test_extract_sections_with_subsections():
    text = "Violation of Section 11(1) and Regulation 4(1)(c) noted."
    result = extract_metadata_from_text(text)
    sections = result["sections_cited"]
    assert any("11(1)" in s for s in sections)
    assert any("4(1)" in s for s in sections)


def test_extract_sections_dedup():
    text = "Section 11 mentioned. Section 11 cited again. Reg. 4 also cited."
    result = extract_metadata_from_text(text)
    # Each unique section reference appears once.
    section_strs = [s.lower() for s in result["sections_cited"]]
    section_11_count = sum(1 for s in section_strs if "11" in s and "section" in s)
    assert section_11_count == 1


def test_no_sections_returns_empty():
    text = "Order disposed of without further comment."
    result = extract_metadata_from_text(text)
    assert result["sections_cited"] == []


# ---- Order ID pattern -----------------------------------------------


def test_order_id_ao_format():
    text = "AO/SS/MS/2024-25/123 dated 15-Aug-2024."
    match = SEBI_ORDER_ID_PATTERN.search(text)
    assert match is not None
    assert "2024" in match.group(0)


def test_order_id_wtm_format():
    text = "WTM/MM/CR/2024-25/45 vs Acme Securities."
    match = SEBI_ORDER_ID_PATTERN.search(text)
    assert match is not None


# ---- HTML listing parser --------------------------------------------


SAMPLE_LISTING_HTML = """
<html><body>
<table>
<tr>
  <td>1</td>
  <td>Adjudication order in the matter of Acme Securities Pvt Ltd dated 15-Aug-2024
      <a href="/cms/sebi_data/orders/AO_SS_MS_2024-25_123.pdf">AO/SS/MS/2024-25/123</a></td>
</tr>
<tr>
  <td>2</td>
  <td>Order in the matter of Beta Trading Co dated 20-Sep-2024
      <a href="https://www.sebi.gov.in/cms/sebi_data/orders/AO_AB_2024_456.pdf">AO/AB/2024/456</a></td>
</tr>
<tr>
  <td>3</td>
  <td>Press release without any PDF link</td>
</tr>
</table>
</body></html>
"""


def test_parse_listing_extracts_two_orders():
    pytest.importorskip("bs4")
    orders = parse_listing_page(SAMPLE_LISTING_HTML)
    assert len(orders) == 2


def test_parse_listing_relative_urls_resolved():
    pytest.importorskip("bs4")
    orders = parse_listing_page(SAMPLE_LISTING_HTML)
    first = next(o for o in orders if "123" in o.order_id)
    assert first.pdf_url.startswith("https://www.sebi.gov.in/")


def test_parse_listing_extracts_party_name():
    pytest.importorskip("bs4")
    orders = parse_listing_page(SAMPLE_LISTING_HTML)
    parties = [o.party for o in orders]
    assert any("Acme Securities" in p for p in parties)


def test_parse_listing_extracts_dates():
    pytest.importorskip("bs4")
    orders = parse_listing_page(SAMPLE_LISTING_HTML)
    for order in orders:
        assert order.order_date is not None
        assert order.order_date.year == 2024


def test_parse_listing_skips_rows_without_pdf_link():
    pytest.importorskip("bs4")
    orders = parse_listing_page(SAMPLE_LISTING_HTML)
    assert len(orders) == 2  # Press release row excluded.


# ---- SEBIOrder dataclass --------------------------------------------


def test_sebi_order_to_jsonable_serializes_dates():
    order = SEBIOrder(
        order_id="AO/X/2024-25/1",
        order_date=date(2024, 8, 15),
        party="Acme",
        pdf_url="https://example.com/a.pdf",
        penalty_inr=Decimal("500000"),
    )
    j = order.to_jsonable()
    assert j["order_date"] == "2024-08-15"
    assert j["penalty_inr"] == "500000"
    assert j["authority"] == "SEBI"


def test_sebi_order_to_jsonable_handles_none_penalty():
    order = SEBIOrder(
        order_id="AO/X/2024-25/2",
        order_date=date(2024, 8, 15),
        party="Beta",
        pdf_url="https://example.com/b.pdf",
    )
    j = order.to_jsonable()
    assert j["penalty_inr"] is None
