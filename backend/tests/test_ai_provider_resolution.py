"""Tests for the swappable AI provider layer — server-default resolution
(Ollama now, GPT-class later) and the widened notice-upload file types.

These cover the keystone of the 2026-06-04 sweep: the compliance AI surface
must work WITHOUT a per-tenant BYOK key by falling back to the server-default
provider (settings.LLM_PROVIDER), and notice uploads must accept every type the
generic uploader does. All pure-function / mocked — no DB required.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.compliance.services import ai_providers, ai_service


# ---------------------------------------------------------------------------
# build_provider — every supported name resolves; unknown raises
# ---------------------------------------------------------------------------


class TestBuildProvider:
    def test_anthropic(self):
        assert isinstance(
            ai_providers.build_provider("anthropic", "k", "m"),
            ai_providers.AnthropicProvider,
        )

    def test_google(self):
        assert isinstance(
            ai_providers.build_provider("google", "k", "gemini-2.0-flash"),
            ai_providers.GoogleProvider,
        )

    def test_ollama_needs_no_key(self):
        p = ai_providers.build_provider("ollama", "", "llama3.2")
        assert isinstance(p, ai_providers.OllamaProvider)

    def test_openai(self):
        # Constructing OpenAIProvider instantiates the SDK client lazily; a
        # dummy key is fine since no request is made.
        assert isinstance(
            ai_providers.build_provider("openai", "sk-test", "gpt-4o-mini"),
            ai_providers.OpenAIProvider,
        )

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown AI provider"):
            ai_providers.build_provider("definitely-not-a-provider", "k", "m")


# ---------------------------------------------------------------------------
# _server_default_config — settings.LLM_PROVIDER -> (provider, model, key)
# ---------------------------------------------------------------------------


class TestServerDefaultConfig:
    def test_ollama_no_key_needed(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "llama3.2")
        assert ai_service._server_default_config() == ("ollama", "llama3.2", "")

    def test_ollama_plus_gemini_prefers_ollama(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "ollama+gemini")
        monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "")
        prov, model, key = ai_service._server_default_config()
        assert prov == "ollama"
        # Per-provider default when LLM_MODEL unset. qwen2.5:3b is the local
        # default — it follows the extraction prompt more reliably than llama3.2
        # and self-reports usable per-field confidence (see _SERVER_DEFAULT_MODELS).
        assert model == "qwen2.5:3b"

    def test_gemini_maps_to_google_and_needs_key(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "gemini")
        monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "")
        monkeypatch.setattr(ai_service.settings, "GEMINI_API_KEY", "AIza-xxx")
        prov, model, key = ai_service._server_default_config()
        assert prov == "google" and key == "AIza-xxx"

    def test_keyed_provider_without_key_yields_none(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "openai")
        monkeypatch.setattr(ai_service.settings, "OPENAI_API_KEY", "")
        assert ai_service._server_default_config() is None

    def test_local_yields_none(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "local")
        assert ai_service._server_default_config() is None

    def test_unknown_yields_none(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "wat")
        assert ai_service._server_default_config() is None


# ---------------------------------------------------------------------------
# resolve_credential — BYOK wins, else server-default, else None
# ---------------------------------------------------------------------------


class TestResolveCredential:
    def test_byok_wins(self, monkeypatch):
        byok = SimpleNamespace(provider="anthropic", model="claude", api_key_enc=b"x")
        monkeypatch.setattr(ai_service, "get_credential", lambda db, cid: byok)
        out = ai_service.resolve_credential(object(), client_id=1)
        assert out is byok  # the real row, untouched

    def test_falls_back_to_server_default(self, monkeypatch):
        monkeypatch.setattr(ai_service, "get_credential", lambda db, cid: None)
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "llama3.2")
        out = ai_service.resolve_credential(object(), client_id=42)
        assert getattr(out, "is_server_default", False) is True
        assert out.provider == "ollama" and out.model == "llama3.2"

    def test_none_when_no_byok_and_no_server_default(self, monkeypatch):
        monkeypatch.setattr(ai_service, "get_credential", lambda db, cid: None)
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "local")
        assert ai_service.resolve_credential(object(), client_id=7) is None

    def test_build_active_provider_for_server_default_skips_decrypt(self, monkeypatch):
        # A server-default credential must NOT touch decrypt_field or db.commit.
        monkeypatch.setattr(ai_service, "get_credential", lambda db, cid: None)
        monkeypatch.setattr(ai_service.settings, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "llama3.2")
        cred = ai_service.resolve_credential(object(), client_id=1)

        def _boom(_):  # decrypt_field must never be called for server default
            raise AssertionError("decrypt_field should not run for server default")

        monkeypatch.setattr(ai_service, "decrypt_field", _boom)
        db = MagicMock()
        prov = ai_service._build_active_provider(db, cred)
        assert isinstance(prov, ai_providers.OllamaProvider)
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# OllamaProvider transport behavior (httpx mocked)
# ---------------------------------------------------------------------------


def _fake_resp(status_code, json_body=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_body if json_body is not None else {}
    return r


class TestOllamaProvider:
    def test_complete_success(self):
        p = ai_providers.OllamaProvider("", "llama3.2", base_url="http://localhost:11434")
        with patch.object(
            ai_providers.httpx,
            "post",
            return_value=_fake_resp(200, {"message": {"content": "hello"}}),
        ):
            assert p.complete("sys", "hi") == "hello"

    def test_404_gives_actionable_pull_hint(self):
        p = ai_providers.OllamaProvider("", "llama3.2", base_url="http://localhost:11434")
        with patch.object(ai_providers.httpx, "post", return_value=_fake_resp(404, text="not found")):
            with pytest.raises(ai_providers.AIProviderError, match="ollama pull"):
                p.complete("sys", "hi")

    def test_empty_content_raises(self):
        p = ai_providers.OllamaProvider("", "llama3.2", base_url="http://localhost:11434")
        with patch.object(ai_providers.httpx, "post", return_value=_fake_resp(200, {"message": {"content": ""}})):
            with pytest.raises(ai_providers.AIProviderError):
                p.complete("sys", "hi")


# ---------------------------------------------------------------------------
# Notice upload — widened file-type resolution
# ---------------------------------------------------------------------------


class TestNoticeUploadExt:
    def _ext(self, filename, content_type):
        from app.compliance.routers.notices import _resolve_upload_ext

        return _resolve_upload_ext(
            SimpleNamespace(filename=filename, content_type=content_type)
        )

    @pytest.mark.parametrize(
        "filename,ctype,expected",
        [
            ("notice.pdf", "application/pdf", "pdf"),
            ("scan.png", "image/png", "png"),
            ("scan.jpg", "image/jpeg", "jpg"),
            ("scan.jpeg", "image/jpeg", "jpeg"),
            ("scan.tiff", "image/tiff", "tiff"),
            ("scan.bmp", "image/bmp", "bmp"),
            ("letter.docx", "application/octet-stream", "docx"),  # ext wins over generic ctype
        ],
    )
    def test_accepts_all_document_types(self, filename, ctype, expected):
        assert self._ext(filename, ctype) == expected

    def test_content_type_fallback_when_no_extension(self):
        # Some clients send a name without an extension; fall back to ctype map.
        assert self._ext("upload", "application/pdf") == "pdf"

    def test_rejects_unsupported(self):
        assert self._ext("malware.exe", "application/x-msdownload") == ""

    def test_strips_null_bytes_in_filename(self):
        assert self._ext("evil\x00.pdf", "application/pdf") == "pdf"
