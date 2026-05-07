"""GmailFetchLog response — Phase 15 EMAIL-07."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GmailFetchLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    credential_id: int
    status: str
    messages_processed: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
