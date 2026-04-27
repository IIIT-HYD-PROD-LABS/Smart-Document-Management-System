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
    CLIENT_CREATE = "client:create"
    CLIENT_MANAGE_TEAM = "client:manage_team"
    REPORT_VIEW = "report:view"
    REPORT_EXPORT = "report:export"
    AUDIT_VIEW = "audit:view"
    ESCALATION_TRIGGER = "escalation:trigger"


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
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
    ComplianceRole.LEGAL_TEAM: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
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
        CompliancePermission.CLIENT_CREATE,
        CompliancePermission.CLIENT_MANAGE_TEAM,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
    }),
    ComplianceRole.STAFF: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.NOTICE_CREATE,
        CompliancePermission.NOTICE_DRAFT_RESPONSE,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
    ComplianceRole.CFO: frozenset({
        CompliancePermission.NOTICE_VIEW,
        CompliancePermission.REPORT_VIEW,
        CompliancePermission.REPORT_EXPORT,
        CompliancePermission.ESCALATION_TRIGGER,
    }),
}


def has_permission(role: ComplianceRole, perm: CompliancePermission) -> bool:
    """Returns True if `role` is granted `perm` in the registry."""
    return perm in ROLE_PERMISSIONS.get(role, frozenset())


def permissions_for_role(role: ComplianceRole) -> frozenset[CompliancePermission]:
    """Returns the full permission set for `role`. Empty frozenset for unknown role."""
    return ROLE_PERMISSIONS.get(role, frozenset())
