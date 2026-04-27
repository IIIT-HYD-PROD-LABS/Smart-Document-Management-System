"""Pydantic schemas for notice activity timeline (D-09)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Mirrors the CHECK constraint on compliance_notice_activity.type.
ActivityTypeT = Literal[
    "status_change",
    "note_added",
    "file_attached",
    "assigned",
]


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notice_id: int
    user_id: Optional[int] = None
    type: str
    details: dict
    created_at: datetime


class NoteAddRequest(BaseModel):
    """Body for POST /api/compliance/notices/{id}/notes.

    Service layer wraps this in log_activity(type='note_added',
    details={'note': ...}).
    """

    note: str = Field(..., min_length=1, max_length=2000)
