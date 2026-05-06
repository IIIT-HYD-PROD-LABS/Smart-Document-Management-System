"""Phase 9 compliance ORM models package.

Models registered here map to the 8 compliance tables created by
migration 0013_compliance_foundation_schema:

  - Client + ClientRegistration  (compliance_clients, compliance_client_registrations)
  - ClientMembership             (compliance_client_memberships)
  - NoticeType                   (compliance_notice_types)
  - ComplianceNotice + NoticeActivity + NoticeTag
                                 (compliance_notices, compliance_notice_activity,
                                  compliance_notice_tags)
  - RegulatoryCalendar           (compliance_regulatory_calendar)

Important: this package eagerly imports every model class so that any
``from app.compliance.models.<x> import Y`` call (including the test
fixtures which only import individual classes) triggers full registration
with the SQLAlchemy declarative_base. Without these imports, relationships
like ``Client.memberships`` and ``Client.notices`` fail to resolve at
first instantiation with InvalidRequestError("expression 'ClientMembership'
failed to locate a name").

The User class from v1.0 (referenced by ``ClientMembership.user``) is
imported lazily by the consumer of this package. Tests using fixtures
that touch ClientMembership ensure ``app.models.user`` is loaded via the
conftest, and production paths import ``app.models`` which loads User
before any compliance class is touched.
"""

# noqa codes throughout: F401 — imported-but-unused. These are
# registry-side-effect imports. Removing them breaks SQLAlchemy
# relationship() resolution.

# Eagerly load v1.0 models that Phase 9 relationships reference
# (User <- ClientMembership.user, ComplianceNotice.assigned_user, etc.;
#  Document <- ComplianceNotice.document_id reverse-link).
# These imports make `from app.compliance.models.client import Client` work
# in isolation (e.g. test fixtures) without requiring the test to first
# load `app.models`.
from app.models.user import User  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

# Eagerly load every Phase 9 model class so cross-class relationship()
# strings resolve against the declarative_base registry on first ORM use.
from app.compliance.models.client import Client, ClientRegistration  # noqa: F401
from app.compliance.models.membership import ClientMembership  # noqa: F401
from app.compliance.models.notice import (  # noqa: F401
    ComplianceNotice,
    NoticeActivity,
    NoticeTag,
)
from app.compliance.models.notice_type import NoticeType  # noqa: F401
from app.compliance.models.regulatory_calendar import RegulatoryCalendar  # noqa: F401
from app.compliance.models.review_queue import NoticeReviewQueue  # noqa: F401
from app.compliance.models.alert import NoticeAlertLog, NoticeAlertRule  # noqa: F401
from app.compliance.models.response import (  # noqa: F401
    NoticeResponse,
    NoticeResponseVersion,
    NoticeResponseApproval,
    NoticeEvidenceAttachment,
)

__all__ = [
    "Client",
    "ClientRegistration",
    "ClientMembership",
    "ComplianceNotice",
    "NoticeActivity",
    "NoticeTag",
    "NoticeType",
    "NoticeReviewQueue",
    "NoticeAlertLog",
    "NoticeAlertRule",
    "NoticeResponse",
    "NoticeResponseVersion",
    "NoticeResponseApproval",
    "NoticeEvidenceAttachment",
    "RegulatoryCalendar",
]
