"""GmailFilterRule Pydantic schemas — Phase 15 EMAIL-04.

Lower priority value wins when multiple rules match (open question #5).
priority bounded to [1, 10000] — well above the default of 100, leaves
room for user-defined priorities at both ends.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RouteTo = Literal["compliance_notice", "bill", "dms_only", "ignore"]


class GmailFilterRuleCreate(BaseModel):
    priority: int = Field(default=100, ge=1, le=10000)
    sender_pattern: Optional[str] = Field(default=None, max_length=255)
    subject_pattern: Optional[str] = Field(default=None, max_length=255)
    label_include: Optional[str] = Field(default=None, max_length=255)
    label_exclude: Optional[str] = Field(default=None, max_length=255)
    route_to: RouteTo
    enabled: bool = True


class GmailFilterRuleUpdate(BaseModel):
    priority: Optional[int] = Field(default=None, ge=1, le=10000)
    sender_pattern: Optional[str] = Field(default=None, max_length=255)
    subject_pattern: Optional[str] = Field(default=None, max_length=255)
    label_include: Optional[str] = Field(default=None, max_length=255)
    label_exclude: Optional[str] = Field(default=None, max_length=255)
    route_to: Optional[RouteTo] = None
    enabled: Optional[bool] = None


class GmailFilterRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    credential_id: int
    priority: int
    sender_pattern: Optional[str] = None
    subject_pattern: Optional[str] = None
    label_include: Optional[str] = None
    label_exclude: Optional[str] = None
    route_to: str
    enabled: bool
    created_at: datetime
