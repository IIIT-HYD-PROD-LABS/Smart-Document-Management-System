"""Tests for the LLM service (llm_service.py)."""

import json
from unittest.mock import patch

import pytest

from app.services.llm_service import (
    _parse_llm_response,
    _build_extraction_prompt,
    _sanitize_error,
    _get_provider_chain,
    LocalProvider,
    CATEGORY_FIELDS,
)


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    """_parse_llm_response handles JSON extraction from raw LLM output."""

    def test_valid_json_parses_correctly(self):
        raw = json.dumps({"fields": {"date": {"value": "2024-01-01", "confidence": 0.9}}, "summary": "A doc."})
        result = _parse_llm_response(raw)
        assert result["summary"] == "A doc."
        assert "date" in result["fields"]

    def test_json_with_code_fences_parses_correctly(self):
        inner = json.dumps({"fields": {}, "summary": "Test"})
        raw = f"```json\n{inner}\n```"
        result = _parse_llm_response(raw)
        assert result["summary"] == "Test"

    def test_empty_response_raises_value_error(self):
        with pytest.raises(ValueError, match="empty response"):
            _parse_llm_response("")

    def test_none_response_raises_value_error(self):
        with pytest.raises(ValueError, match="empty response"):
            _parse_llm_response(None)

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError, match="whitespace-only"):
            _parse_llm_response("   \n\t  ")

    def test_response_over_64kb_raises_value_error(self):
        huge = json.dumps({"fields": {}, "summary": "x" * 70000})
        with pytest.raises(ValueError, match="too large"):
            _parse_llm_response(huge)

    def test_non_dict_response_raises_value_error(self):
        raw = json.dumps([1, 2, 3])
        with pytest.raises(ValueError, match="not a JSON object"):
            _parse_llm_response(raw)

    def test_invalid_json_raises_json_decode_error(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("{invalid json!!}")

    def test_fields_not_dict_raises_value_error(self):
        raw = json.dumps({"fields": "not-a-dict", "summary": "ok"})
        with pytest.raises(ValueError, match="'fields' is not a dict"):
            _parse_llm_response(raw)

    def test_summary_not_string_raises_value_error(self):
        raw = json.dumps({"fields": {}, "summary": 123})
        with pytest.raises(ValueError, match="'summary' is not a string"):
            _parse_llm_response(raw)


# ---------------------------------------------------------------------------
# _build_extraction_prompt
# ---------------------------------------------------------------------------

class TestBuildExtractionPrompt:
    """_build_extraction_prompt constructs category-aware prompts."""

    def test_known_category_uses_correct_fields(self):
        prompt = _build_extraction_prompt("invoice text here", "invoices")
        for field in CATEGORY_FIELDS["invoices"]:
            assert field in prompt

    def test_unknown_category_falls_back_to_unknown_fields(self):
        prompt = _build_extraction_prompt("some text", "unknown")
        for field in CATEGORY_FIELDS["unknown"]:
            assert field in prompt

    def test_invalid_category_falls_back_to_unknown(self):
        prompt = _build_extraction_prompt("some text", "nonexistent_category_xyz")
        for field in CATEGORY_FIELDS["unknown"]:
            assert field in prompt
        # The invalid category is replaced with "unknown" before building prompt
        assert "nonexistent_category_xyz" not in prompt
        assert "unknown" in prompt

    def test_text_is_truncated_to_4000_chars(self):
        long_text = "A" * 8000
        prompt = _build_extraction_prompt(long_text, "bills")
        # The document text section between --- delimiters should be truncated to 4000 chars
        text_section = prompt.split("---\n")[1].split("\n---")[0]
        assert len(text_section) == 4000

    def test_prompt_contains_json_structure_hint(self):
        prompt = _build_extraction_prompt("text", "bills")
        assert '"fields"' in prompt
        assert '"summary"' in prompt


# ---------------------------------------------------------------------------
# _sanitize_error
# ---------------------------------------------------------------------------

class TestSanitizeError:
    """_sanitize_error redacts sensitive data from error messages."""

    def test_long_hex_strings_are_redacted(self):
        error_msg = "Error with key sk-abcdef1234567890abcdef1234567890ab in request"
        result = _sanitize_error(error_msg)
        assert "***REDACTED***" in result
        assert "sk-abcdef1234567890abcdef1234567890ab" not in result

    def test_key_value_patterns_are_redacted(self):
        error_msg = "Failed: api_key=my_secret_key_here&token=abc123"
        result = _sanitize_error(error_msg)
        assert "api_key=***" in result

    def test_short_strings_are_not_redacted(self):
        error_msg = "Connection refused on port 8080"
        result = _sanitize_error(error_msg)
        assert result == error_msg

    def test_multiple_sensitive_patterns(self):
        error_msg = "key=supersecret&password=hunter2"
        result = _sanitize_error(error_msg)
        assert "key=***" in result
        assert "password=***" in result

    def test_case_insensitive_key_value_redaction(self):
        error_msg = "TOKEN=mytoken123"
        result = _sanitize_error(error_msg)
        assert "TOKEN=***" in result


# ---------------------------------------------------------------------------
# LocalProvider.extract
# ---------------------------------------------------------------------------

class TestLocalProviderExtract:
    """LocalProvider.extract wraps the regex metadata extractor."""

    @patch("app.ml.metadata_extractor.extract_metadata")
    def test_returns_dict_with_fields_and_summary(self, mock_extract):
        mock_extract.return_value = {
            "dates": ["2024-01-15"],
            "amounts": [{"amount": 500.0, "currency": "INR"}],
            "vendor": "Acme Corp",
        }
        provider = LocalProvider()
        result = provider.extract("sample document text", "invoices")

        assert "fields" in result
        assert "summary" in result
        assert isinstance(result["fields"], dict)
        assert isinstance(result["summary"], str)

    @patch("app.ml.metadata_extractor.extract_metadata")
    def test_provider_field_is_not_set(self, mock_extract):
        mock_extract.return_value = {"dates": [], "amounts": [], "vendor": None}
        provider = LocalProvider()
        result = provider.extract("text", "bills")
        # provider key should NOT be set by LocalProvider -- caller sets it
        assert "provider" not in result

    @patch("app.ml.metadata_extractor.extract_metadata")
    def test_populates_fields_from_metadata(self, mock_extract):
        mock_extract.return_value = {
            "dates": ["2024-03-01"],
            "amounts": [{"amount": 100.0, "currency": "USD"}],
            "vendor": "TestCo",
        }
        provider = LocalProvider()
        result = provider.extract("some text", "bills")

        assert "dates" in result["fields"]
        assert result["fields"]["dates"]["confidence"] == 0.6
        assert "amounts" in result["fields"]
        assert "vendor" in result["fields"]

    @patch("app.ml.metadata_extractor.extract_metadata")
    def test_empty_metadata_returns_minimal_result(self, mock_extract):
        mock_extract.return_value = {"dates": [], "amounts": [], "vendor": None}
        provider = LocalProvider()
        result = provider.extract("", "unknown")

        assert result["fields"] == {}
        assert "summary" in result

    @patch("app.ml.metadata_extractor.extract_metadata")
    def test_summary_includes_vendor_and_amounts(self, mock_extract):
        mock_extract.return_value = {
            "dates": [],
            "amounts": [{"amount": 250.0, "currency": "INR"}],
            "vendor": "ShopX",
        }
        provider = LocalProvider()
        result = provider.extract("text", "bills")

        assert "ShopX" in result["summary"]
        assert "250.0" in result["summary"]


# ---------------------------------------------------------------------------
# _get_provider_chain
# ---------------------------------------------------------------------------

class TestGetProviderChain:
    """_get_provider_chain builds an ordered fallback chain of LLM providers."""

    @patch("app.services.llm_service.settings")
    def test_local_provider_returns_chain_ending_with_local(self, mock_settings):
        mock_settings.LLM_PROVIDER = "local"
        chain = _get_provider_chain()
        assert len(chain) >= 1
        last_name, last_provider = chain[-1]
        assert last_name == "local"
        assert isinstance(last_provider, LocalProvider)

    @patch("app.services.llm_service.settings")
    def test_chain_always_has_local_as_last_entry(self, mock_settings):
        mock_settings.LLM_PROVIDER = "gemini"
        mock_settings.GEMINI_API_KEY = ""  # no key, so gemini won't be added
        chain = _get_provider_chain()
        last_name, _ = chain[-1]
        assert last_name == "local"

    @patch("app.services.llm_service.settings")
    def test_ollama_provider_appears_when_configured(self, mock_settings):
        mock_settings.LLM_PROVIDER = "ollama"
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        mock_settings.LLM_MODEL = ""
        chain = _get_provider_chain()
        names = [name for name, _ in chain]
        assert "ollama" in names
        assert names[-1] == "local"

    @patch("app.services.llm_service.settings")
    def test_unknown_provider_still_has_local_fallback(self, mock_settings):
        mock_settings.LLM_PROVIDER = "nonexistent"
        chain = _get_provider_chain()
        assert len(chain) == 1
        assert chain[0][0] == "local"
