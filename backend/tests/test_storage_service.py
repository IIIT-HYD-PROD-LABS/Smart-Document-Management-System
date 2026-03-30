"""Tests for the storage service (storage_service.py)."""

import os
import uuid
from unittest.mock import patch, MagicMock

import pytest

from app.services.storage_service import (
    generate_filename,
    validate_magic_bytes,
    _validate_path_inside_upload_dir,
)


# ---------------------------------------------------------------------------
# generate_filename
# ---------------------------------------------------------------------------

class TestGenerateFilename:
    """generate_filename returns a UUID-hex filename preserving extension."""

    def test_returns_uuid_hex_with_extension(self):
        result = generate_filename("report.pdf")
        stem, ext = os.path.splitext(result)
        assert ext == ".pdf"
        # stem must be a valid 32-char hex string (uuid4 without hyphens)
        assert len(stem) == 32
        uuid.UUID(stem, version=4)  # raises if not valid hex

    def test_preserves_extension_as_lowercase_input(self):
        # The function preserves the original extension using pathlib.suffix,
        # which keeps it as-is. Extension case comes from the caller.
        result = generate_filename("photo.PNG")
        assert result.endswith(".PNG")

    def test_no_extension(self):
        result = generate_filename("Makefile")
        stem = result
        assert len(stem) == 32

    def test_double_extension_keeps_last(self):
        result = generate_filename("archive.tar.gz")
        assert result.endswith(".gz")

    def test_different_calls_produce_unique_names(self):
        names = {generate_filename("a.pdf") for _ in range(50)}
        assert len(names) == 50


# ---------------------------------------------------------------------------
# validate_magic_bytes
# ---------------------------------------------------------------------------

class TestValidateMagicBytes:
    """validate_magic_bytes checks file content against declared extension."""

    def test_pdf_magic_bytes_match_pdf(self):
        content = b"%PDF-1.4 rest of file"
        assert validate_magic_bytes(content, "pdf") is True

    def test_pdf_with_dot_prefix(self):
        content = b"%PDF-1.7"
        assert validate_magic_bytes(content, ".pdf") is True

    def test_png_magic_bytes_match_png(self):
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        assert validate_magic_bytes(content, "png") is True

    def test_jpeg_magic_bytes_match_jpg(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 20
        assert validate_magic_bytes(content, "jpg") is True

    def test_jpeg_magic_bytes_match_jpeg(self):
        content = b"\xff\xd8\xff\xe1" + b"\x00" * 20
        assert validate_magic_bytes(content, "jpeg") is True

    def test_docx_pk_magic_bytes_match_docx(self):
        content = b"PK\x03\x04" + b"\x00" * 30
        assert validate_magic_bytes(content, "docx") is True

    def test_wrong_magic_bytes_for_extension(self):
        # PNG header claimed as PDF
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        assert validate_magic_bytes(content, "pdf") is False

    def test_empty_content_returns_false(self):
        assert validate_magic_bytes(b"", "pdf") is False

    def test_unknown_extension_returns_false(self):
        assert validate_magic_bytes(b"%PDF-1.4", "xyz") is False

    def test_extension_case_insensitive(self):
        content = b"%PDF-1.4 data"
        assert validate_magic_bytes(content, "PDF") is True


# ---------------------------------------------------------------------------
# _validate_path_inside_upload_dir
# ---------------------------------------------------------------------------

class TestValidatePathInsideUploadDir:
    """_validate_path_inside_upload_dir prevents path traversal."""

    def test_valid_path_within_upload_dir(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, "file.pdf")

        mock_settings = MagicMock()
        mock_settings.UPLOAD_DIR = upload_dir

        with patch("app.services.storage_service.settings", mock_settings):
            result = _validate_path_inside_upload_dir(file_path)
        assert result == os.path.realpath(file_path)

    def test_path_with_traversal_is_rejected(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        # Attempt to escape via ../
        malicious_path = os.path.join(upload_dir, "..", "etc", "passwd")

        mock_settings = MagicMock()
        mock_settings.UPLOAD_DIR = upload_dir

        with patch("app.services.storage_service.settings", mock_settings):
            with pytest.raises(ValueError, match="Path traversal detected"):
                _validate_path_inside_upload_dir(malicious_path)

    def test_path_outside_upload_dir_is_rejected(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        outside_path = str(tmp_path / "other" / "secret.txt")

        mock_settings = MagicMock()
        mock_settings.UPLOAD_DIR = upload_dir

        with patch("app.services.storage_service.settings", mock_settings):
            with pytest.raises(ValueError, match="Path traversal detected"):
                _validate_path_inside_upload_dir(outside_path)

    def test_symlink_resolved_correctly(self, tmp_path):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        # Create a symlink inside upload_dir that points outside
        target = tmp_path / "outside.txt"
        target.write_text("secret")
        link = upload_dir / "link.txt"
        link.symlink_to(target)

        mock_settings = MagicMock()
        mock_settings.UPLOAD_DIR = str(upload_dir)

        with patch("app.services.storage_service.settings", mock_settings):
            with pytest.raises(ValueError, match="Path traversal detected"):
                _validate_path_inside_upload_dir(str(link))
