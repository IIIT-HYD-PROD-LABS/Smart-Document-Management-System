"""7-role x 12-permission registry — Phase 9 RBAC-01..06.

Source: 09-RESEARCH.md Pattern 4. Per CONTEXT D-26, permissions are FLAT
per role — no inheritance hierarchy. The matrix encoded here is the source
of truth verified by tests/test_compliance_endpoints.py::test_role_permission_matrix
(84 parametrized cases).

NOTE: FINANCE_TEAM has NOTICE_VIEW but is scoped at the SERVICE LAYER to GST/IT
only — the permission registry grants the verb; the service rejects non-tax notices.
"""
from enum import Enum


class CompliancePermission(str, Enum):
    NOTICE_VIEW = "notice:view"
    NOTICE_CREATE = "notice:create"
    NOTICE_DRAFT_RESPONSE = "notice:draft_response"
    NOTICE_APPROVE = "notice:approve"
    NOTICE_SUBMIT = "notice:submit"
    NOTICE_BULK_UPDATE = "notice:bulk_update"
    NOTICE_REVIEW = "notice:review"
    # Phase 12 — multi-stage approval permissions. NOTICE_APPROVE (Phase 9)
    # covers the Reviewer stage; legal + CFO get dedicated permissions.
    NOTICE_APPROVE_LEGAL = "notice:approve_legal"
    NOTICE_APPROVE_CFO = "notice:approve_cfo"
    NOTICE_ATTACH_EVIDENCE = "notice:attach_evidence"
    CLIENT_CREATE = "client:create"
    CLIENT_MANAGE_TEAM = "client:manage_team"
    REPORT_VIEW = "report:view"
    REPORT_EXPORT = "report:export"
    AUDIT_VIEW = "audit:view"
    ESCALATION_TRIGGER = "escalation:trigger"
    # Phase 15 — gates Gmail OAuth + MCP tool invocation (D-05).
    EMAIL_INTEGRATION_USE = "email_integration:use"


class ComplianceRole(str, Enum):
    COMPLIANCE_HEAD = "compliance_head"
    LEGAL_TEAM = "legal_team"
    FINANCE_TEAM = "finance_team"
    AUDITOR = "auditor"
    CA_CONSULTANT = "ca_consultant"
    STAFF = "staff"
    CFO = "cfo"


# Per CONTEXT D-26: flat permissions, no inheritance.
# Maps to the 84-case matrix in tests/test_compliance_endpoints.py.
ROLE_PERMISSIONS: dict[ComplianceRole, frozenset[CompliancePermission]] = {
    ComplianceRole.COMPLIANCE_HEAD: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_APPROVE,
        CompliancePermission.NOTICE_SUBMIT,
        CompliancePermission.NOTICE_BULK_UPDATE,
        CompliancePermission.NOTICE_REVIEW,
        CompliancePermission.NOTICE_ATTACH_EVIDENCE,
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
        CompliancePermission.EMAIL_INTEGRATION_USE,
        # AUDIT_VIEW: senior in-house compliance owner is the natural
        # consumer of "what happened on this client?" — locking the audit
        # log to the auditor role only made the page useless for the
        # head, who then asked their auditor to forward exports. Putting
        # the read here keeps the DB-level append-only trigger as the
        # actual integrity guarantee; the role just controls *visibility*.
        CompliancePermission.AUDIT_VIEW,
    }),
    ComplianceRole.LEGAL_TEAM: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.NOTICE_REVIEW,
        CompliancePermission.NOTICE_APPROVE_LEGAL,
        CompliancePermission.NOTICE_ATTACH_EVIDENCE,
        CompliancePermission.REPORT_VIEW,
    }),
    ComplianceRole.FINANCE_TEAM: frozenset({
        CompliancePermission.NOTICE_VIEW,  # GST/IT scoping enforced in service layer
        CompliancePermission.REPORT_VIEW,
    }),
    ComplianceRole.AUDITOR: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.AUDIT_VIEW,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
    }),
    ComplianceRole.CA_CONSULTANT: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.NOTICE_APPROVE,
        CompliancePermission.NOTICE_SUBMIT,
        CompliancePermission.NOTICE_BULK_UPDATE,
        CompliancePermission.NOTICE_REVIEW,
        CompliancePermission.NOTICE_APPROVE_LEGAL,
        CompliancePermission.NOTICE_APPROVE_CFO,
        CompliancePermission.NOTICE_ATTACH_EVIDENCE,
        CompliancePermission.CLIENT_CREATE,
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.EMAIL_INTEGRATION_USE,
        # External CAs need the audit trail for their working papers —
        # an audit they cannot see is one they cannot rely on.
        CompliancePermission.AUDIT_VIEW,
    }),
    ComplianceRole.STAFF: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.NOTICE_ATTACH_EVIDENCE,
        CompliancePermission.ESCALATION_TRIGGER,
        CompliancePermission.EMAIL_INTEGRATION_USE,
    }),
    ComplianceRole.CFO: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_APPROVE_CFO,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
        CompliancePermission.EMAIL_INTEGRATION_USE,
    }),
}


def has_permission(role: ComplianceRole, perm: CompliancePermission) -> bool:
    """Returns True if `role` is granted `perm` in the registry."""
    return perm in ROLE_PERMISSIONS.get(role, frozenset())


def permissions_for_role(role: ComplianceRole) -> frozenset[CompliancePermission]:
    """Returns the full permission set for `role`. Empty frozenset for unknown role."""
    return ROLE_PERMISSIONS.get(role, frozenset())
