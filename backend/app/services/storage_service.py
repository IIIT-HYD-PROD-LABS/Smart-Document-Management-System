"""Storage service - local filesystem or AWS S3."""

import os
import re
import uuid
from pathlib import Path

import boto3
import structlog
from botocore.exceptions import ClientError

from app.config import settings

logger = structlog.stdlib.get_logger()

# Magic byte signatures for file type validation
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
    "bmp": [b"BM"],
    "docx": [b"PK\x03\x04"],
}


def validate_magic_bytes(file_bytes: bytes, declared_extension: str) -> bool:
    """Validate that file content matches declared extension via magic bytes."""
    if not file_bytes:
        return False
    ext = declared_extension.lower().lstrip(".")
    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        return False
    return any(file_bytes[:len(sig)] == sig for sig in signatures)


def _validate_path_inside_upload_dir(file_path: str) -> str:
    """Resolve the path and ensure it is inside UPLOAD_DIR. Returns the resolved path."""
    real_path = os.path.realpath(file_path)
    real_upload_dir = os.path.realpath(settings.UPLOAD_DIR)
    if not real_path.startswith(real_upload_dir + os.sep) and real_path != real_upload_dir:
        logger.warning("path_traversal_detected", resolved=real_path, upload_dir=real_upload_dir)
        raise ValueError("Path traversal detected")
    return real_path


def _get_s3_client():
    """Create a configured boto3 S3 client."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def generate_filename(original_filename: str) -> str:
    """Generate a unique filename preserving the original extension."""
    ext = Path(original_filename).suffix
    return f"{uuid.uuid4().hex}{ext}"


def save_file_local(file_bytes: bytes, filename: str) -> str:
    """Save file to local upload directory. Returns the file path.

    Raises OSError on disk-full or permission errors so callers can return
    an appropriate HTTP response.
    """
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    file_path = _validate_path_inside_upload_dir(file_path)
    # Use restrictive permissions (owner read/write only) to prevent other
    # system users from reading uploaded documents.
    try:
        fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    except OSError as e:
        logger.error("file_open_failed", path=file_path, error=str(e))
        raise OSError("Storage unavailable") from e
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)
    except OSError as e:
        # fd is already closed by os.fdopen; only clean up the file
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error("file_write_failed", path=file_path, error=str(e))
        raise OSError("Storage write failed (disk may be full)") from e
    except BaseException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    return file_path


def upload_to_s3(file_bytes: bytes, filename: str) -> str:
    """Upload file to AWS S3. Returns the S3 URL.

    Raises ClientError on S3 failures so callers can return an appropriate
    HTTP response.
    """
    import mimetypes

    s3_client = _get_s3_client()
    s3_key = f"documents/{filename}"
    # Derive content type from filename; default to binary stream to prevent
    # browsers from sniffing/rendering uploaded content (XSS risk).
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            ContentDisposition="attachment",
        )
    except ClientError as e:
        logger.error("s3_upload_failed", key=s3_key, error=str(e))
        raise
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"


def get_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """Generate a presigned URL for downloading from S3."""
    s3_client = _get_s3_client()
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.warning("presigned_url_failed", key=s3_key, error=str(e))
        return ""


def save_file(file_bytes: bytes, original_filename: str) -> tuple[str, str | None]:
    """
    Save file using configured storage backend.
    Returns (file_path_or_filename, s3_url_or_None).
    """
    filename = generate_filename(original_filename)

    if settings.USE_S3:
        s3_url = upload_to_s3(file_bytes, filename)
        return filename, s3_url
    else:
        file_path = save_file_local(file_bytes, filename)
        return file_path, None


def delete_file(file_path: str | None, s3_url: str | None) -> None:
    """Delete a file from storage."""
    if file_path:
        try:
            real_path = _validate_path_inside_upload_dir(file_path)
            if os.path.exists(real_path):
                os.remove(real_path)
        except ValueError:
            logger.warning("path_traversal_blocked_on_delete")
    if s3_url and settings.USE_S3:
        s3_key = s3_url.split(".amazonaws.com/")[-1]
        s3_client = _get_s3_client()
        try:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        except ClientError as e:
            logger.warning("s3_delete_failed", key=s3_key, error=str(e))
