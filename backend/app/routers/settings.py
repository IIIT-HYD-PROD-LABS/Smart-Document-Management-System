"""Settings API routes -- LLM provider configuration."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user_settings import UserLLMSettings
from app.schemas.settings import LLMSettingsResponse, LLMSettingsUpdate
from app.utils.security import get_current_user

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _build_response(row: UserLLMSettings) -> LLMSettingsResponse:
    """Build a safe LLM settings response (never leaks full API key)."""
    api_key_set = row.api_key_encrypted is not None
    api_key_last4: str | None = None

    if api_key_set:
        try:
            decrypted = row.decrypt_api_key()
            if decrypted and len(decrypted) >= 4:
                api_key_last4 = decrypted[-4:]
        except Exception:
            # If decryption fails, still report key is set but can't show last4
            logger.warning("failed_to_decrypt_api_key", user_id=row.user_id)

    return LLMSettingsResponse(
        llm_provider=row.llm_provider,
        model_name=row.model_name,
        api_key_set=api_key_set,
        api_key_last4=api_key_last4,
        ollama_base_url=row.ollama_base_url,
    )


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's LLM provider settings.

    The API key is NEVER returned in full -- only the last 4 characters are shown.
    """
    row = (
        db.query(UserLLMSettings)
        .filter(UserLLMSettings.user_id == current_user.id)
        .first()
    )

    if row is None:
        return LLMSettingsResponse()

    return _build_response(row)


@router.put("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(
    body: LLMSettingsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the current user's LLM provider settings.

    If body.api_key is provided it will be encrypted before storage.
    The response never returns the full API key.
    """
    row = (
        db.query(UserLLMSettings)
        .filter(UserLLMSettings.user_id == current_user.id)
        .first()
    )

    if row is None:
        row = UserLLMSettings(user_id=current_user.id)
        db.add(row)

    row.llm_provider = body.llm_provider
    row.model_name = body.model_name
    row.ollama_base_url = body.ollama_base_url

    # Only overwrite the encrypted key if a new key was provided
    if body.api_key is not None:
        row.encrypt_api_key(body.api_key)

    db.commit()
    db.refresh(row)

    logger.info(
        "llm_settings_updated",
        user_id=current_user.id,
        provider=body.llm_provider,
    )

    return _build_response(row)
