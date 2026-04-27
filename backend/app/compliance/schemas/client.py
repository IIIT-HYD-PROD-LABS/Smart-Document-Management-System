"""Pydantic schemas for client + registration + membership.

Covers CLIENT-01 (client CRUD), CLIENT-02 (multi-GSTIN registrations),
CLIENT-05 (atomic onboarding wizard), CLIENT-03 (dashboard aggregates).
"""
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.compliance.utils.indian_validators import (
    CIN_RX,
    DIN_RX,
    PAN_RX,
    validate_gstin,
)


# Lightweight email format check. We deliberately avoid pydantic.EmailStr
# (and the email-validator dependency it pulls) because the value is
# informational, the DB column is plain String(255), and the wizard UI
# also gates on browser-native <input type="email">. This regex catches
# obvious typos at the API boundary; full RFC 5322 compliance is not
# a Phase 9 requirement.
_EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Mirrors VALID_COMPLIANCE_ROLES in app.compliance.models.membership.
_COMPLIANCE_ROLE_VALUES = (
    "compliance_head",
    "legal_team",
    "finance_team",
    "auditor",
    "ca_consultant",
    "staff",
    "cfo",
)


class RegistrationCreate(BaseModel):
    """One row in the registrations[] step of onboarding (D-15)."""

    type: Literal["GSTIN", "PAN", "CIN", "DIN"]
    value: str = Field(..., min_length=8, max_length=30)
    state: Optional[str] = Field(None, max_length=5)

    @field_validator("value")
    @classmethod
    def _validate_value_format(cls, v: str, info):
        t = info.data.get("type")
        if t == "GSTIN" and not validate_gstin(v):
            raise ValueError(f"Invalid GSTIN: {v}")
        if t == "PAN" and not PAN_RX.match(v):
            raise ValueError(f"Invalid PAN: {v}")
        if t == "CIN" and not CIN_RX.match(v):
            raise ValueError(f"Invalid CIN: {v}")
        if t == "DIN" and not DIN_RX.match(v):
            raise ValueError(f"Invalid DIN: {v}")
        return v


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value: str
    state: Optional[str] = None
    is_active: bool
    created_at: datetime


class MembershipCreate(BaseModel):
    """One row in the team[] step of onboarding."""

    user_id: int
    compliance_role: Literal[
        "compliance_head",
        "legal_team",
        "finance_team",
        "auditor",
        "ca_consultant",
        "staff",
        "cfo",
    ]
    access_start: Optional[datetime] = None
    access_end: Optional[datetime] = None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    client_id: int
    compliance_role: str
    access_start: Optional[datetime] = None
    access_end: Optional[datetime] = None
    created_at: datetime


class ClientCreate(BaseModel):
    """Step 1 (Details) of the onboarding wizard (D-16)."""

    name: str = Field(..., min_length=2, max_length=200)
    client_type: Literal["pvt_ltd", "llp", "partnership", "sole_prop", "opc"]
    industry: Optional[str] = Field(None, max_length=100)
    primary_contact_email: Optional[str] = Field(None, max_length=255)

    @field_validator("primary_contact_email")
    @classmethod
    def _validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not _EMAIL_RX.match(v):
            raise ValueError(f"Invalid email format: {v}")
        return v


class ClientOnboardRequest(BaseModel):
    """Full multi-step onboarding payload (D-16 wizard).

    Per CLIENT-05 the entire request is processed atomically in a single
    transaction — registrations and team are optional (can be added later).
    """

    details: ClientCreate
    registrations: list[RegistrationCreate] = Field(default_factory=list)
    team: list[MembershipCreate] = Field(default_factory=list)


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_type: str
    industry: Optional[str] = None
    primary_contact_email: Optional[str] = None
    config_overrides: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientDetailOut(ClientOut):
    """Detail view embeds registrations + memberships."""

    registrations: list[RegistrationOut] = Field(default_factory=list)
    memberships: list[MembershipOut] = Field(default_factory=list)


class DashboardAggregates(BaseModel):
    """Per-client dashboard counts — output of get_dashboard_aggregates (D-18).

    Phase 9 always reports `by_risk_tier['unscored']` == total because
    risk scoring is a Phase 10 BERT classifier (D-06). UI renders the
    five-color contract from 09-UI-SPEC even when only `unscored` is non-zero.
    """

    total: int
    by_status: dict[str, int]
    by_authority: dict[str, int]
    by_risk_tier: dict[str, int]
    overdue: int
