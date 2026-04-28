"""Phase 10 — regex_patterns unit tests.

Verifies extractors for Indian compliance identifiers (GSTIN, PAN, CIN, DIN,
section references). Patterns must achieve 100% precision on well-formed
inputs per CLASS-06.
"""

from app.ml.compliance.regex_patterns import (
    extract_cins,
    extract_gstins,
    extract_pans,
    extract_section_references,
)


# ---- GSTIN ----------------------------------------------------------


def test_extract_single_gstin():
    text = "Notice issued to GSTIN 27AAAAA0000A1Z5 dated 30-04-2026."
    assert extract_gstins(text) == ["27AAAAA0000A1Z5"]


def test_extract_multiple_gstins_dedup():
    text = "GSTINs 27AAAAA0000A1Z5 and 09AAAAA0000A1Z5 plus 27AAAAA0000A1Z5 again."
    result = extract_gstins(text)
    assert sorted(result) == ["09AAAAA0000A1Z5", "27AAAAA0000A1Z5"]


def test_invalid_gstin_state_code_rejected():
    # State code 38 is not valid (max 37).
    text = "GSTIN 38AAAAA0000A1Z5"
    assert extract_gstins(text) == []


def test_invalid_gstin_state_code_zero_rejected():
    # State code 00 is not valid.
    text = "GSTIN 00AAAAA0000A1Z5"
    assert extract_gstins(text) == []


def test_lowercase_gstin_normalized_to_upper():
    text = "Notice issued to gstin 27aaaaa0000a1z5 dated."
    assert extract_gstins(text) == ["27AAAAA0000A1Z5"]


# ---- PAN ------------------------------------------------------------


def test_extract_single_pan():
    text = "PAN: AAAAA0000A is registered."
    assert extract_pans(text) == ["AAAAA0000A"]


def test_pan_dedup():
    text = "AAAAA0000A is the same as AAAAA0000A."
    assert extract_pans(text) == ["AAAAA0000A"]


def test_pan_lowercase_normalized():
    text = "pan: aaaaa0000a"
    assert extract_pans(text) == ["AAAAA0000A"]


# ---- CIN ------------------------------------------------------------


def test_extract_single_cin():
    text = "Company CIN: U72200KA2010PTC056789 incorporated in Karnataka."
    assert extract_cins(text) == ["U72200KA2010PTC056789"]


def test_cin_listed_company_l_prefix():
    text = "CIN L72200KA2010PLC056789 (listed)."
    assert extract_cins(text) == ["L72200KA2010PLC056789"]


def test_invalid_cin_too_short_rejected():
    text = "CIN U72200KA2010PT56789 (missing one char)"
    assert extract_cins(text) == []


# ---- Section references ---------------------------------------------


def test_extract_section_reference_us_format():
    text = "Notice issued u/s 143(2) of the Income Tax Act."
    refs = extract_section_references(text)
    assert any("143" in r for r in refs)


def test_extract_section_reference_word_section():
    text = "Penalty levied under Section 271(1)(c)."
    refs = extract_section_references(text)
    assert any("271" in r for r in refs)


def test_extract_section_reference_rule_format():
    text = "Per Rule 96(10) of CGST Rules."
    refs = extract_section_references(text)
    assert any("96" in r for r in refs)


def test_extract_multiple_section_references_dedup():
    text = "u/s 143(2) and Section 271(1)(c) per s. 132."
    refs = extract_section_references(text)
    assert len(refs) == 3


# ---- Realistic compliance text -------------------------------------


def test_realistic_drc01_extraction():
    text = """
    GSTIN: 27AAAAA0000A1Z5
    Notice No. DRC-01/2026/A1 dated 15-04-2026
    Penalty u/s 73(9) of the CGST Act, 2017
    Tax Demand: Rs. 5,00,000/-
    Response Deadline: 30 days from receipt
    """
    gstins = extract_gstins(text)
    refs = extract_section_references(text)
    assert "27AAAAA0000A1Z5" in gstins
    assert any("73" in r for r in refs)


def test_realistic_it_notice_extraction():
    text = """
    PAN: AAAAA0000A
    Notice u/s 143(2) of the IT Act for AY 2024-25.
    """
    pans = extract_pans(text)
    refs = extract_section_references(text)
    assert pans == ["AAAAA0000A"]
    assert any("143" in r for r in refs)
