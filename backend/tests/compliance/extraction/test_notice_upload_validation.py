"""Phase 17 hardening — notice upload validation (size cap + magic bytes).

`_read_validated_upload` is the shared guard for both POST /notices/{id}/upload
and POST /notices/extract-preview. It must stream a size cap before buffering
(memory-exhaustion DoS) and magic-byte validate against the declared type
(content_type is client-spoofable).
"""
from __future__ import annotations

import io

import pytest
from fastapi import HTTPException

_PDF = b"%PDF-1.4\n" + b"x" * 64
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class _FakeUpload:
    def __init__(self, content_type: str, data: bytes):
        self.content_type = content_type
        self.file = io.BytesIO(data)
        self.filename = "notice"


def test_accepts_valid_pdf():
    from app.compliance.routers.notices import _read_validated_upload

    contents, ext = _read_validated_upload(_FakeUpload("application/pdf", _PDF))
    assert ext == "pdf"
    assert contents == _PDF


def test_accepts_valid_png():
    from app.compliance.routers.notices import _read_validated_upload

    contents, ext = _read_validated_upload(_FakeUpload("image/png", _PNG))
    assert ext in ("png",)
    assert contents == _PNG


def test_rejects_disallowed_content_type():
    from app.compliance.routers.notices import _read_validated_upload

    with pytest.raises(HTTPException) as exc:
        _read_validated_upload(_FakeUpload("application/zip", _PDF))
    assert exc.value.status_code == 400


def test_rejects_spoofed_content_type():
    """content_type says PDF but the bytes are HTML — magic-byte check catches it."""
    from app.compliance.routers.notices import _read_validated_upload

    with pytest.raises(HTTPException) as exc:
        _read_validated_upload(_FakeUpload("application/pdf", b"<html>not a pdf</html>"))
    assert exc.value.status_code == 400


def test_enforces_size_cap(monkeypatch):
    from app.compliance.routers import notices

    # Shrink the cap so a tiny payload trips it without allocating 50 MB.
    monkeypatch.setattr(notices.settings, "MAX_FILE_SIZE_MB", 0)
    with pytest.raises(HTTPException) as exc:
        notices._read_validated_upload(_FakeUpload("application/pdf", _PDF))
    assert exc.value.status_code == 413
