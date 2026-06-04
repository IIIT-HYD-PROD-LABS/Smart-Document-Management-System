"""Phase 17 EXTRACT-01 / EXTRACT-02 — extractor service contract.

Plan 17-03 GREEN. The extractor:
  - looks up the tenant's BYOK credential via Phase 16 get_credential,
  - calls provider.complete(SCOPE_LOCK_SYSTEM, build_user_prompt(text)),
  - filters returned fields to FIELD_SCHEMA, computes raw average,
  - runs validator, writes audit, returns envelope.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def test_extractor_envelope_shape(extraction_envelope_fixture):
    """Envelope per D-03: fields, average_confidence, model, tokens_in, tokens_out, latency_ms."""
    env = extraction_envelope_fixture
    assert set(env.keys()) >= {
        "fields", "average_confidence", "model",
        "tokens_in", "tokens_out", "latency_ms",
    }
    for field_name, payload in env["fields"].items():
        assert set(payload.keys()) >= {"value", "confidence", "source_span"}, (
            f"D-03 requires value+confidence+source_span on field {field_name}"
        )
        assert 0.0 <= payload["confidence"] <= 1.0


def test_extract_notice_fields_raises_when_credential_missing():
    """D-14: when NO provider is available (no per-tenant BYOK row AND no
    server-default provider), extraction raises the typed error the router maps
    to 412.

    Post-2026-06-04: the extractor resolves its provider via
    ai_service.resolve_credential, which falls back to the server-default
    provider (settings.LLM_PROVIDER, e.g. Ollama) when a tenant has no key.
    resolve_credential returns None only when neither source is available, so we
    stub it to None to exercise the genuine "nothing configured" path.
    """
    from app.compliance.services.notice_extractor_service import (
        NoticeExtractionCredentialMissingError,
        extract_notice_fields,
    )
    with patch(
        "app.compliance.services.notice_extractor_service.ai_service.resolve_credential",
        return_value=None,
    ):
        with pytest.raises(NoticeExtractionCredentialMissingError):
            extract_notice_fields(
                db=MagicMock(),
                client_id=1,
                user_id=1,
                text="anything",
            )


class TestNormalizeFields:
    """Provider output is coerced to the {value, confidence} envelope shape so a
    small/local model that returns flat strings or omits confidence does not 500
    or collapse the average to 0 (the 2026-06-04 'shows manual entry' bug)."""

    def _norm(self, fields):
        from app.compliance.services.notice_extractor_service import _normalize_fields
        return _normalize_fields(fields)

    def test_flat_scalar_is_wrapped(self):
        out = self._norm({"notice_number": "DRC-01/2026/4456"})
        assert out["notice_number"]["value"] == "DRC-01/2026/4456"
        assert 0.0 < out["notice_number"]["confidence"] <= 1.0

    def test_missing_confidence_gets_nonzero_default(self):
        out = self._norm({"authority": {"value": "GST"}})
        assert out["authority"]["value"] == "GST"
        assert out["authority"]["confidence"] > 0.0  # not 0.0 -> not all-"review"

    def test_present_confidence_preserved_and_clamped(self):
        out = self._norm({"a": {"value": "v", "confidence": 0.9}, "b": {"value": "v", "confidence": 5}})
        assert out["a"]["confidence"] == 0.9
        assert out["b"]["confidence"] == 1.0  # clamped to <= 1.0

    def test_list_value_wrapped(self):
        out = self._norm({"legal_sections": ["Section 67"]})
        assert out["legal_sections"]["value"] == ["Section 67"]
        assert "confidence" in out["legal_sections"]


def test_extract_notice_fields_happy_path_filters_to_schema(
    mock_provider_factory, extraction_envelope_fixture
):
    """D-01 + D-04: extractor calls provider.complete, drops non-schema keys, returns envelope."""
    from app.compliance.services import notice_extractor_service

    # Cred stub
    cred = MagicMock(provider="anthropic", model="claude-sonnet-test")
    # Provider returns extra junk fields alongside valid ones — extractor must drop the junk
    payload = {
        "fields": {
            **extraction_envelope_fixture["fields"],
            "horoscope": {"value": "Sagittarius", "confidence": 0.99, "source_span": "stars"},
        }
    }
    provider = MagicMock()
    provider.complete.return_value = json.dumps(payload)

    with patch.object(notice_extractor_service.ai_service, "get_credential", return_value=cred), \
         patch.object(notice_extractor_service.ai_service, "_build_active_provider", return_value=provider), \
         patch.object(notice_extractor_service, "log_audit_event_strict", return_value=True):
        env = notice_extractor_service.extract_notice_fields(
            db=MagicMock(), client_id=1, user_id=1, text="sample text"
        )

    assert "horoscope" not in env["fields"], "extractor must drop fields outside FIELD_SCHEMA (D-04)"
    assert "notice_number" in env["fields"]
    assert env["model"] == "anthropic:claude-sonnet-test"
    assert env["latency_ms"] >= 0
    provider.complete.assert_called_once()


def test_extract_notice_fields_writes_redacted_audit_row(
    mock_provider_factory, extraction_envelope_fixture
):
    """D-16: audit args carry provider/model/tokens/latency/avg/body_sha/field_keys — no values."""
    from app.compliance.services import notice_extractor_service

    cred = MagicMock(provider="anthropic", model="claude-sonnet-test")
    provider = MagicMock()
    provider.complete.return_value = json.dumps(
        {"fields": extraction_envelope_fixture["fields"]}
    )

    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return True

    with patch.object(notice_extractor_service.ai_service, "get_credential", return_value=cred), \
         patch.object(notice_extractor_service.ai_service, "_build_active_provider", return_value=provider), \
         patch.object(notice_extractor_service, "log_audit_event_strict", side_effect=_capture):
        notice_extractor_service.extract_notice_fields(
            db=MagicMock(), client_id=1, user_id=42, text="sample notice text",
        )

    assert captured["action"] == "notice_ai_extract"
    assert captured["resource_type"] == "compliance_notice"
    assert captured["user_id"] == 42
    details = captured["details"]
    expected_keys = {"provider", "model", "tokens_in", "tokens_out", "latency_ms",
                     "average_confidence", "fields_returned", "body_sha256"}
    assert expected_keys.issubset(details.keys())
    # NEGATIVE: no raw values, no body text, no source spans
    serialised = json.dumps(details)
    assert "DRC-01/2026/4456" not in serialised, "extracted notice_number must not leak into audit"
    assert "sample notice text" not in serialised, "raw body must not leak into audit"
    assert "Goods and Services Tax" not in serialised, "source_span must not leak into audit"


def test_extract_notice_fields_truncates_to_max_window():
    """D-15: input is clipped to MAX_TEXT_WINDOW chars so the token budget holds."""
    from app.compliance.services.notice_extraction_prompt import (
        MAX_TEXT_WINDOW,
        build_user_prompt,
    )
    # Use a marker char the prompt template itself does not contain.
    marker = "¶"  # pilcrow
    assert marker not in build_user_prompt(""), "marker leaked into template; pick another"
    long_text = marker * (MAX_TEXT_WINDOW * 3)
    user_msg = build_user_prompt(long_text)
    assert user_msg.count(marker) == MAX_TEXT_WINDOW, "prompt must clip text to MAX_TEXT_WINDOW chars"


def test_extract_window_covers_fields_past_legacy_4000_chars():
    """Regression: real notices lead with letterhead + legal recitals and place
    the demand table / response deadline later in the document. The legacy
    4000-char window clipped those, so financial fields came back blank. The
    window must reach the demand block of a normal multi-page notice."""
    from app.compliance.services.notice_extraction_prompt import (
        MAX_TEXT_WINDOW,
        build_user_prompt,
    )
    preamble = "WHEREAS on examination of the records it is observed that ... " * 110
    assert len(preamble) > 4000, "preamble must exceed the legacy window for a valid regression"
    demand = "DEMAND Tax 145000 Interest 12000 Penalty 5000 Total 162000 respond by 2026-05-30"
    prompt = build_user_prompt(preamble + demand)
    assert MAX_TEXT_WINDOW >= 16000, "window must cover a multi-page notice, not just one page"
    assert "DEMAND Tax 145000" in prompt, "demand block past 4000 chars must reach the model"
    assert "2026-05-30" in prompt, "response deadline past 4000 chars must reach the model"


def test_extract_notice_fields_propagates_out_of_scope():
    """D-13: OUT_OF_SCOPE sentinel from the model bubbles up as AIOutOfScopeError."""
    from app.compliance.services import ai_service, notice_extractor_service

    cred = MagicMock(provider="anthropic", model="claude-sonnet-test")
    provider = MagicMock()
    provider.complete.return_value = "OUT_OF_SCOPE"

    with patch.object(notice_extractor_service.ai_service, "get_credential", return_value=cred), \
         patch.object(notice_extractor_service.ai_service, "_build_active_provider", return_value=provider), \
         patch.object(notice_extractor_service, "log_audit_event_strict", return_value=True):
        with pytest.raises(ai_service.AIOutOfScopeError):
            notice_extractor_service.extract_notice_fields(
                db=MagicMock(), client_id=1, user_id=1, text="anything",
            )
