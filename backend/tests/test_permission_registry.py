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
