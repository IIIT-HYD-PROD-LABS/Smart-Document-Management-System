"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Smart Document Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database - REQUIRED, no default
    DATABASE_URL: str

    # JWT Auth - REQUIRED, no default for SECRET_KEY
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # File Storage
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [
        "pdf", "png", "jpg", "jpeg", "tiff", "bmp", "docx"
    ]

    # AWS S3 (optional - set USE_S3=true to enable)
    USE_S3: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "smart-docs-bucket"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = True

    # ML Model
    MODEL_DIR: str = str(BASE_DIR / "models")
    ML_CONFIDENCE_THRESHOLD: float = 0.3

    # Tesseract OCR
    TESSERACT_CMD: str = ""  # Leave empty for default path

    # LLM Extraction (Phase 5)
    LLM_PROVIDER: str = "local"  # "ollama", "gemini", "anthropic", "openai", or "local"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = ""  # e.g. "llama3.2", "claude-sonnet-4-20250514", "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 60

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        insecure_values = {
            "super-secret-key-change-in-production",
            "super-secret-docker-key",
            "your-super-secret-key-change-this-in-production",
            "changeme",
            "secret",
        }
        if v in insecure_values:
            raise ValueError(
                "SECRET_KEY must be changed from default insecure value. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return v


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.MODEL_DIR, exist_ok=True)
