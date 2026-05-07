"""Phase 15 Pydantic schemas."""
from app.email.schemas.credential import (  # noqa: F401
    GmailCredentialCreate,
    GmailCredentialResponse,
    GmailCredentialUpdate,
)
from app.email.schemas.filter_rule import (  # noqa: F401
    GmailFilterRuleCreate,
    GmailFilterRuleResponse,
    GmailFilterRuleUpdate,
)
from app.email.schemas.bill import (  # noqa: F401
    BillFilterParams,
    BillMarkPaidRequest,
    BillResponse,
)
from app.email.schemas.fetch_log import GmailFetchLogResponse  # noqa: F401

__all__ = [
    "GmailCredentialCreate",
    "GmailCredentialResponse",
    "GmailCredentialUpdate",
    "GmailFilterRuleCreate",
    "GmailFilterRuleResponse",
    "GmailFilterRuleUpdate",
    "BillFilterParams",
    "BillMarkPaidRequest",
    "BillResponse",
    "GmailFetchLogResponse",
]
