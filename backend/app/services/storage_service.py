"""Storage service - local filesystem or AWS S3."""

import os
import uuid
from pathlib import Path

import boto3
import structlog
from botocore.exceptions import ClientError

from app.config import settings

logger = structlog.stdlib.get_logger()


def generate_filename(original_filename: str) -> str:
    """Generate a unique filename preserving the original extension."""
    ext = Path(original_filename).suffix
    return f"{uuid.uuid4().hex}{ext}"


def save_file_local(file_bytes: bytes, filename: str) -> str:
    """Save file to local upload directory. Returns the file path."""
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path


def upload_to_s3(file_bytes: bytes, filename: str) -> str:
    """Upload file to AWS S3. Returns the S3 URL."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    s3_key = f"documents/{filename}"
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
    )
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"


def get_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """Generate a presigned URL for downloading from S3."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
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
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    if s3_url and settings.USE_S3:
        s3_key = s3_url.split(f".amazonaws.com/")[-1]
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        try:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        except ClientError as e:
            logger.warning("s3_delete_failed", key=s3_key, error=str(e))
