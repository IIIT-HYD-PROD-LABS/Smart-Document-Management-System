from app.models.user import User
from app.models.document import Document
from app.models.refresh_token import RefreshToken
from app.models.document_permission import DocumentPermission
from app.models.document_version import DocumentVersion
from app.models.audit_log import AuditLog

# Phase 9 compliance models — register with the SQLAlchemy declarative_base
# so relationship() resolution finds them at app startup. Without these
# imports, ComplianceNotice / ClientMembership / Client are not in the
# class registry and Document.notice / Client.notices / Client.memberships
# fail with InvalidRequestError on first ORM access.
from app.compliance.models.client import Client, ClientRegistration  # noqa: F401, E402
from app.compliance.models.membership import ClientMembership  # noqa: F401, E402
from app.compliance.models.notice import (  # noqa: F401, E402
    ComplianceNotice,
    NoticeActivity,
    NoticeTag,
)
from app.compliance.models.notice_type import NoticeType  # noqa: F401, E402
from app.compliance.models.regulatory_calendar import RegulatoryCalendar  # noqa: F401, E402

# Phase 15 Gmail models — register so SQLAlchemy resolves Document.source_email
# relationship() and the email tests can reference these classes directly.
from app.email.models import (  # noqa: F401, E402
    GmailCredential,
    GmailFilterRule,
    GmailFetchLog,
    GmailMessageLog,
    Bill,
)

__all__ = [
    # v1.0
    "User",
    "Document",
    "RefreshToken",
    "DocumentPermission",
    "DocumentVersion",
    "AuditLog",
    # Phase 9 compliance
    "Client",
    "ClientRegistration",
    "ClientMembership",
    "ComplianceNotice",
    "NoticeActivity",
    "NoticeTag",
    "NoticeType",
    "RegulatoryCalendar",
    # Phase 15 gmail
    "GmailCredential",
    "GmailFilterRule",
    "GmailFetchLog",
    "GmailMessageLog",
    "Bill",
]
