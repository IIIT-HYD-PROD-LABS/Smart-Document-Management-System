"""Application configuration loaded from environment variables."""

import ipaddress
import os
import urllib.parse
from pathlib import Path

import structlog
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

logger = structlog.stdlib.get_logger()

BASE_DIR = Path(__file__).resolve().parent.parent

# Recognized LLM providers. "ollama+gemini" runs Ollama then Gemini as fallback.
KNOWN_LLM_PROVIDERS = {"local", "ollama", "gemini", "ollama+gemini", "anthropic", "openai"}


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

    # TLS for REMOTE Postgres (local hosts always skip SSL). Secure by default:
    # with neither set, remote connections verify the server cert against the
    # system CA bundle and fail closed on an untrusted/self-signed cert.
    #   DB_SSL_ROOT_CERT : path to the server's CA cert -> verify against it
    #                      (verify-ca). Preferred for self-signed deployments.
    #   DB_SSL_NO_VERIFY : explicit opt-out -> encrypt but do NOT verify the
    #                      cert. Only for a trusted network where the CA cert
    #                      is not yet available (e.g. campus Postgres interim).
    DB_SSL_ROOT_CERT: str = ""
    DB_SSL_NO_VERIFY: bool = False

    # JWT Auth - REQUIRED, no default for SECRET_KEY
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MFA (TOTP) + per-account brute-force lockout
    MFA_ISSUER: str = "TaxSync"
    MFA_CHALLENGE_EXPIRE_MINUTES: int = 5   # TTL of the post-password challenge token
    MFA_BACKUP_CODE_COUNT: int = 10
    MAX_FAILED_LOGINS: int = 5              # consecutive failures before lockout
    LOCKOUT_DURATION_MINUTES: int = 15      # base lock window (doubles per repeat, capped)

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def origins_must_not_be_wildcard(cls, v: list[str]) -> list[str]:
        if "*" in v:
            raise ValueError(
                "ALLOWED_ORIGINS must not contain '*' (wildcard). "
                "Specify explicit origins, e.g. ['http://localhost:3000']."
            )
        return v

    # File Storage
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [
        "pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp", "gif", "docx"
    ]

    # AWS S3 (optional - set USE_S3=true to enable)
    USE_S3: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "smart-docs-bucket"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    # Redis SSL verification (set to false only for managed Redis with self-signed certs)
    REDIS_SSL_VERIFY: bool = True
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

    # Notice-extraction auto-apply gates (Phase 17 D-06). A notice auto-applies
    # (skips the review queue) only when the average AND the critical-field
    # (notice_number, authority) confidences clear these bars. Default 0.85 suits
    # frontier models that self-report calibrated confidence; lower them (e.g.
    # 0.6) for local models like Ollama that do not emit confidence (the
    # extractor then defaults it, so the gate is the only lever).
    EXTRACTION_AVG_GATE: float = 0.85
    EXTRACTION_CRITICAL_GATE: float = 0.85

    # OAuth (Phase 6 - optional)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = ""  # e.g. "http://localhost:8000" - used for OAuth redirects

    # Email (SMTP) - optional, used for early access approval emails
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@taxsync.in"
    SMTP_USE_TLS: bool = True

    # ===========================================================
    # Phase 9: Compliance Foundation (INFRA-06, CLIENT-04)
    # ===========================================================
    # PII encryption — Fernet symmetric. Generate via:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str = ""
    FERNET_KEY_OLD: str = ""  # Optional rotation key

    # PostgreSQL roles created by migration 0017_db_roles
    APP_RUNTIME_PASSWORD: str = ""
    APP_MIGRATOR_PASSWORD: str = ""

    # Connection strings for the two roles. Migrations use DATABASE_URL_MIGRATOR
    # (or DATABASE_URL fallback); the FastAPI process uses DATABASE_URL_RUNTIME
    # so RLS policies apply — but ONLY when DB_ENFORCE_RLS is true (see below).
    DATABASE_URL_RUNTIME: str = ""
    DATABASE_URL_MIGRATOR: str = ""

    # RLS activation gate. When False (default) the app engine connects via
    # DATABASE_URL (the owner role, BYPASSRLS) and tenant isolation rests on the
    # explicit per-endpoint client_id filters. When True the app engine connects
    # via DATABASE_URL_RUNTIME (the non-owner app_runtime role) so the RLS
    # policies are ENFORCED as a second, independent isolation layer.
    #
    # This is an EXPLICIT gate, deliberately NOT keyed on "is DATABASE_URL_RUNTIME
    # set", because the runtime DSN may be provisioned long before the database is
    # ready (comprehensive app_runtime grants applied). Flip to true only after
    # the grant migration has run against the target database, or every query
    # fail-closes to zero rows / permission-denied.
    DB_ENFORCE_RLS: bool = False

    @field_validator("FERNET_KEY")
    @classmethod
    def fernet_key_must_be_valid_if_set(cls, v: str) -> str:
        # Empty is allowed at startup: deployments that don't use
        # PII encryption / BYOK can run without one, and the runtime
        # check in pii_encryption.py will raise on first use. But if a
        # value IS set, decode it and confirm Fernet's actual requirement
        # (32 raw bytes after urlsafe-base64 decode) rather than relying on
        # the length+charset heuristic that false-rejected quoted/padded
        # keys and false-accepted Unicode alphanumerics.
        if not v:
            return v
        _hint = (
            'Generate via: python -c '
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
        import base64
        try:
            decoded = base64.urlsafe_b64decode(v.strip().encode("ascii"))
        except (ValueError, UnicodeEncodeError) as e:
            raise ValueError(
                f"FERNET_KEY is not valid urlsafe base64: {e}. {_hint}"
            ) from e
        if len(decoded) != 32:
            raise ValueError(
                f"FERNET_KEY must decode to 32 bytes (got {len(decoded)}). {_hint}"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        _generate_hint = (
            'Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )
        if not v or not v.strip():
            raise ValueError(
                f"SECRET_KEY must not be empty. {_generate_hint}"
            )
        insecure_values = {
            "super-secret-key-change-in-production",
            "super-secret-docker-key",
            "your-super-secret-key-change-this-in-production",
            "changeme",
            "secret",
            "test",
            "password",
            "development",
            "12345678901234567890123456789012",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
        if v.lower() in insecure_values:
            raise ValueError(
                f"SECRET_KEY must be changed from default insecure value. {_generate_hint}"
            )
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters. {_generate_hint}"
            )
        # Reject keys with very low entropy (all same char, all digits, all lowercase)
        if len(set(v)) < 10:
            raise ValueError(
                f"SECRET_KEY has too few unique characters (needs 10+). {_generate_hint}"
            )
        return v

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def ollama_base_url_must_be_safe(cls, v: str) -> str:
        # SEC4: OLLAMA_BASE_URL is fetched verbatim by OllamaProvider, so an
        # attacker-controlled or misconfigured value (e.g. the cloud metadata
        # endpoint 169.254.169.254) would let us SSRF. Restrict the scheme to
        # http/https and the host to loopback / RFC1918 private ranges /
        # host.docker.internal; reject anything else at startup.
        if not v:
            return v
        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"OLLAMA_BASE_URL scheme must be http or https (got '{parsed.scheme}')."
            )
        host = parsed.hostname
        if not host:
            raise ValueError(f"OLLAMA_BASE_URL has no host: '{v}'.")
        allowed_names = {"localhost", "host.docker.internal"}
        if host.lower() in allowed_names:
            return v
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(
                f"OLLAMA_BASE_URL host '{host}' is not allowed. Use localhost, "
                "host.docker.internal, or a loopback/private (RFC1918) address."
            ) from None
        if not (ip.is_loopback or ip.is_private):
            raise ValueError(
                f"OLLAMA_BASE_URL host '{host}' must be a loopback or private "
                "(RFC1918) address, not a public/link-local address."
            )
        return v

    @model_validator(mode="after")
    def warn_on_llm_provider_misconfiguration(self) -> "Settings":
        # D2: an unrecognized LLM_PROVIDER (or a recognized one missing its key)
        # silently degrades to local-only, so configured keys are ignored. Warn
        # loudly at config load instead of crashing the app.
        provider = self.LLM_PROVIDER.lower()
        if provider not in KNOWN_LLM_PROVIDERS:
            logger.warning(
                "llm_provider_unrecognized",
                provider=self.LLM_PROVIDER,
                known=sorted(KNOWN_LLM_PROVIDERS),
                effect="falling back to local-only extraction",
            )
            return self
        required_key = {
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider)
        # ollama+gemini needs Gemini only as the second-stage fallback; Ollama
        # itself needs no key, so don't warn for the combined provider.
        if required_key and not getattr(self, required_key):
            logger.warning(
                "llm_provider_missing_key",
                provider=provider,
                missing=required_key,
                effect="falling back to local-only extraction",
            )
        return self


settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.MODEL_DIR, exist_ok=True)
