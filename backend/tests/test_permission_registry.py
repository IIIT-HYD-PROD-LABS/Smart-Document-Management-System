"""RBAC-01..06: Permission registry per-role permission set sanity."""



def test_compliance_head_has_approve():
    from app.compliance.services.permission_registry import (
        CompliancePermission,
        ComplianceRole,
        has_permission,
    )
    assert has_permission(
        ComplianceRole.COMPLIANCE_HEAD, CompliancePermission.NOTICE_APPROVE
    ) is True


def test_staff_lacks_approve():
    from app.compliance.services.permission_registry import (
        CompliancePermission,
        ComplianceRole,
        has_permission,
    )
    assert has_permission(
        ComplianceRole.STAFF, CompliancePermission.NOTICE_APPROVE
    ) is False


def test_auditor_has_audit_view():
    from app.compliance.services.permission_registry import (
        CompliancePermission,
        ComplianceRole,
        has_permission,
    )
    assert has_permission(
        ComplianceRole.AUDITOR, CompliancePermission.AUDIT_VIEW
    ) is True


def test_cfo_lacks_create():
    from app.compliance.services.permission_registry import (
        CompliancePermission,
        ComplianceRole,
        has_permission,
    )
    assert has_permission(
        ComplianceRole.CFO, CompliancePermission.NOTICE_CREATE
    ) is False


# Phase 10 — NOTICE_REVIEW permission grant matrix
def test_compliance_head_has_review():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.COMPLIANCE_HEAD, CompliancePermission.NOTICE_REVIEW
    ) is True


def test_ca_consultant_has_review():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.CA_CONSULTANT, CompliancePermission.NOTICE_REVIEW
    ) is True


def test_legal_team_has_review():
    """Legal team can override low-confidence classifications."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.LEGAL_TEAM, CompliancePermission.NOTICE_REVIEW
    ) is True


def test_auditor_lacks_review():
    """Auditors are read-only and must not override classifications."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.AUDITOR, CompliancePermission.NOTICE_REVIEW
    ) is False


def test_staff_lacks_review():
    """Staff cannot reassign authoritative classification — review is a senior decision."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.STAFF, CompliancePermission.NOTICE_REVIEW
    ) is False


def test_finance_team_lacks_review():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.FINANCE_TEAM, CompliancePermission.NOTICE_REVIEW
    ) is False


def test_cfo_lacks_review():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.CFO, CompliancePermission.NOTICE_REVIEW
    ) is False


# Phase 12 — multi-stage approval grants (RESEARCH-FINAL §1 #6)

def test_legal_team_has_approve_legal():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.LEGAL_TEAM, CompliancePermission.NOTICE_APPROVE_LEGAL
    ) is True


def test_cfo_has_approve_cfo():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.CFO, CompliancePermission.NOTICE_APPROVE_CFO
    ) is True


def test_compliance_head_lacks_approve_legal():
    """Compliance head approves at the Reviewer stage via NOTICE_APPROVE.
    They must not silently bypass the Legal gate."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.COMPLIANCE_HEAD, CompliancePermission.NOTICE_APPROVE_LEGAL
    ) is False


def test_compliance_head_lacks_approve_cfo():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.COMPLIANCE_HEAD, CompliancePermission.NOTICE_APPROVE_CFO
    ) is False


def test_ca_consultant_has_all_approval_stages():
    """Most permissive role — CA consultant can act at every stage."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.CA_CONSULTANT, CompliancePermission.NOTICE_APPROVE
    ) is True
    assert has_permission(
        ComplianceRole.CA_CONSULTANT, CompliancePermission.NOTICE_APPROVE_LEGAL
    ) is True
    assert has_permission(
        ComplianceRole.CA_CONSULTANT, CompliancePermission.NOTICE_APPROVE_CFO
    ) is True


def test_staff_has_attach_evidence():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.STAFF, CompliancePermission.NOTICE_ATTACH_EVIDENCE
    ) is True


def test_auditor_lacks_attach_evidence():
    """Auditor role is read-only and must not be able to mutate the evidence list."""
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.AUDITOR, CompliancePermission.NOTICE_ATTACH_EVIDENCE
    ) is False


def test_finance_team_lacks_approve_legal():
    from app.compliance.services.permission_registry import (
        CompliancePermission, ComplianceRole, has_permission,
    )
    assert has_permission(
        ComplianceRole.FINANCE_TEAM, CompliancePermission.NOTICE_APPROVE_LEGAL
    ) is False
