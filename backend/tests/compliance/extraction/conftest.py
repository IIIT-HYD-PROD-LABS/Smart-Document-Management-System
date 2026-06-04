"""Phase 17 extraction test fixtures.

Wave 0 RED state. Plans 02 to 05 will start importing the production
modules these fixtures shim; the fixtures themselves are intentionally
provider-agnostic and do not touch the network.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


# D-04 field schema (mirror in test space so contract drift is visible)
EXTRACTION_FIELDS = (
    "notice_number",
    "authority",
    "notice_type",
    "issued_date",
    "response_deadline",
    "tax_demand",
    "interest",
    "penalty",
    "total_liability",
    "taxpayer_name",
    "gstin",
    "pan",
    "cin",
    "legal_sections",
)


def _envelope(fields: dict, average: float, model: str = "claude-sonnet-stub") -> dict:
    """Build an extraction envelope shaped per D-03."""
    return {
        "fields": fields,
        "average_confidence": average,
        "model": model,
        "tokens_in": 1834,
        "tokens_out": 412,
        "latency_ms": 4210,
    }


@pytest.fixture()
def extraction_envelope_fixture() -> dict:
    """High-confidence envelope that should auto-apply per D-06."""
    fields = {
        "notice_number": {"value": "DRC-01/2026/4456", "confidence": 0.96, "source_span": "Notice No. DRC-01/2026/4456"},
        "authority": {"value": "GST", "confidence": 0.99, "source_span": "Goods and Services Tax"},
        "notice_type": {"value": "Show Cause Notice u/s 73", "confidence": 0.93, "source_span": "Show Cause Notice"},
        "issued_date": {"value": "2026-05-12", "confidence": 0.95, "source_span": "Dated 12-May-2026"},
        "response_deadline": {"value": "2026-06-11", "confidence": 0.94, "source_span": "within 30 days"},
        "tax_demand": {"value": 145000.0, "confidence": 0.92, "source_span": "Tax demanded Rs. 1,45,000"},
        "interest": {"value": 12000.0, "confidence": 0.88, "source_span": "Interest Rs. 12,000"},
        "penalty": {"value": 14500.0, "confidence": 0.90, "source_span": "Penalty Rs. 14,500"},
        "total_liability": {"value": 171500.0, "confidence": 0.91, "source_span": "Total Rs. 1,71,500"},
        "gstin": {"value": "29AABCS1429B1Z2", "confidence": 0.97, "source_span": "GSTIN 29AABCS1429B1Z2"},
        "legal_sections": {"value": ["Section 73 of the CGST Act, 2017"], "confidence": 0.93, "source_span": "Section 73"},
    }
    return _envelope(fields, average=0.93)


@pytest.fixture()
def low_confidence_envelope_fixture() -> dict:
    """Below the D-06 conjunctive gate; routing should send to review queue."""
    fields = {
        "notice_number": {"value": "DRC-01/2026/?", "confidence": 0.62, "source_span": "DRC-01"},
        "authority": {"value": "GST", "confidence": 0.91, "source_span": "GST"},
        "issued_date": {"value": "2026-05-12", "confidence": 0.83, "source_span": "12 May 2026"},
    }
    return _envelope(fields, average=0.79)


@pytest.fixture()
def critical_field_low_envelope_fixture() -> dict:
    """Average clears 0.85 but `notice_number` does not (D-06 critical-field rule)."""
    fields = {
        "notice_number": {"value": "DRC-01/2026/?", "confidence": 0.70, "source_span": "DRC-01"},
        "authority": {"value": "GST", "confidence": 0.99, "source_span": "GST"},
        "issued_date": {"value": "2026-05-12", "confidence": 0.95, "source_span": "12-May-2026"},
        "response_deadline": {"value": "2026-06-11", "confidence": 0.92, "source_span": "30 days"},
    }
    return _envelope(fields, average=0.89)


@pytest.fixture()
def structurally_invalid_envelope_fixture() -> dict:
    """GSTIN fails the 15-char rule; D-33 should halve its confidence."""
    fields = {
        "notice_number": {"value": "DRC-01/2026/4456", "confidence": 0.96, "source_span": "DRC-01/2026/4456"},
        "authority": {"value": "GST", "confidence": 0.99, "source_span": "GST"},
        "gstin": {"value": "29AABCS1429B", "confidence": 0.90, "source_span": "GSTIN 29AABCS1429B"},
        "issued_date": {"value": "2026-05-12", "confidence": 0.95, "source_span": "12-May-2026"},
        "response_deadline": {"value": "2026-04-11", "confidence": 0.92, "source_span": "11 April 2026"},
    }
    return _envelope(fields, average=0.94)


@pytest.fixture()
def mock_provider_factory():
    """Factory that returns a MagicMock provider whose `complete` returns a JSON string.

    Matches `ai_providers.AIProvider.complete(system, user, max_tokens) -> str`.
    The extractor calls `provider.complete(...)` via `_run_extraction` (the
    dedicated EXTRACTION_SYSTEM_PROMPT, not the chat scope-lock).
    """
    def _factory(envelope_payload: dict) -> MagicMock:
        provider = MagicMock()
        provider.complete.return_value = json.dumps({"fields": envelope_payload.get("fields", {})})
        return provider
    return _factory


@pytest.fixture()
def fixture_text_path(tmp_path) -> dict[str, str]:
    """Resolve packaged fixture filenames to their on-disk path."""
    import pathlib
    here = pathlib.Path(__file__).parent / "fixtures"
    return {
        "gst_drc_01": str(here / "gst_drc_01_sample.txt"),
        "it_143_2": str(here / "it_143_2_sample.txt"),
        "malformed_gstin": str(here / "malformed_gstin_sample.txt"),
    }
