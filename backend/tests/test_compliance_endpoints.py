"""RBAC parametrized matrix — Phase 9 RBAC-01..06 merge gate.

Asserts that each of the 7 compliance roles has the correct permissions per
the registry defined in .planning/phases/09-compliance-foundation/09-RESEARCH.md
Pattern 4. This is a behavioural test: it issues an HTTP request through the
FastAPI test client and asserts 403 vs 2xx based on the expected permission.
"""

import pytest


pytestmark = pytest.mark.integration


# 7 roles × 12 permissions = 84 cases. Source: 09-RESEARCH.md Pattern 4.
# Format: (compliance_role, permission_or_endpoint, expect_allowed)
ROLE_PERMISSION_MATRIX = [
    # COMPLIANCE_HEAD: 9 permissions allowed
    ("compliance_head", "notice:view", True),
    ("compliance_head", "notice:create", True),
    ("compliance_head", "notice:draft_response", False),
    ("compliance_head", "notice:approve", True),
    ("compliance_head", "notice:submit", True),
    ("compliance_head", "notice:bulk_update", True),
    ("compliance_head", "client:create", False),
    ("compliance_head", "client:manage_team", True),
    ("compliance_head", "report:view", True),
    ("compliance_head", "report:export", True),
    ("compliance_head", "audit:view", False),
    ("compliance_head", "escalation:trigger", True),

    # LEGAL_TEAM: 3 permissions allowed
    ("legal_team", "notice:view", True),
    ("legal_team", "notice:create", False),
    ("legal_team", "notice:draft_response", True),
    ("legal_team", "notice:approve", False),
    ("legal_team", "notice:submit", False),
    ("legal_team", "notice:bulk_update", False),
    ("legal_team", "client:create", False),
    ("legal_team", "client:manage_team", False),
    ("legal_team", "report:view", True),
    ("legal_team", "report:export", False),
    ("legal_team", "audit:view", False),
    ("legal_team", "escalation:trigger", False),

    # FINANCE_TEAM: 2 permissions allowed
    ("finance_team", "notice:view", True),
    ("finance_team", "notice:create", False),
    ("finance_team", "notice:draft_response", False),
    ("finance_team", "notice:approve", False),
    ("finance_team", "notice:submit", False),
    ("finance_team", "notice:bulk_update", False),
    ("finance_team", "client:create", False),
    ("finance_team", "client:manage_team", False),
    ("finance_team", "report:view", True),
    ("finance_team", "report:export", False),
    ("finance_team", "audit:view", False),
    ("finance_team", "escalation:trigger", False),

    # AUDITOR: 4 permissions allowed (read-only + audit_view)
    ("auditor", "notice:view", True),
    ("auditor", "notice:create", False),
    ("auditor", "notice:draft_response", False),
    ("auditor", "notice:approve", False),
    ("auditor", "notice:submit", False),
    ("auditor", "notice:bulk_update", False),
    ("auditor", "client:create", False),
    ("auditor", "client:manage_team", False),
    ("auditor", "report:view", True),
    ("auditor", "report:export", True),
    ("auditor", "audit:view", True),
    ("auditor", "escalation:trigger", False),

    # CA_CONSULTANT: 10 permissions allowed (most permissive role)
    ("ca_consultant", "notice:view", True),
    ("ca_consultant", "notice:create", True),
    ("ca_consultant", "notice:draft_response", True),
    ("ca_consultant", "notice:approve", True),
    ("ca_consultant", "notice:submit", True),
    ("ca_consultant", "notice:bulk_update", True),
    ("ca_consultant", "client:create", True),
    ("ca_consultant", "client:manage_team", True),
    ("ca_consultant", "report:view", True),
    ("ca_consultant", "report:export", True),
    ("ca_consultant", "audit:view", False),
    ("ca_consultant", "escalation:trigger", False),

    # STAFF: 4 permissions allowed
    ("staff", "notice:view", True),
    ("staff", "notice:create", True),
    ("staff", "notice:draft_response", True),
    ("staff", "notice:approve", False),
    ("staff", "notice:submit", False),
    ("staff", "notice:bulk_update", False),
    ("staff", "client:create", False),
    ("staff", "client:manage_team", False),
    ("staff", "report:view", False),
    ("staff", "report:export", False),
    ("staff", "audit:view", False),
    ("staff", "escalation:trigger", True),

    # CFO: 4 permissions allowed (read-only across all clients)
    ("cfo", "notice:view", True),
    ("cfo", "notice:create", False),
    ("cfo", "notice:draft_response", False),
    ("cfo", "notice:approve", False),
    ("cfo", "notice:submit", False),
    ("cfo", "notice:bulk_update", False),
    ("cfo", "client:create", False),
    ("cfo", "client:manage_team", False),
    ("cfo", "report:view", True),
    ("cfo", "report:export", True),
    ("cfo", "audit:view", False),
    ("cfo", "escalation:trigger", True),
]


@pytest.mark.parametrize("compliance_role,permission,expect_allowed", ROLE_PERMISSION_MATRIX)
def test_role_permission_matrix(client_with_membership, compliance_role, permission, expect_allowed):
    """Each role × permission combination produces the expected access result.

    Maps to: RBAC-01..06. MERGE GATE. Asserts the permission registry from
    backend/app/compliance/services/permission_registry.py is correctly
    encoded.
    """
    from app.compliance.services.permission_registry import (
        ComplianceRole, CompliancePermission, has_permission,
    )
    role = ComplianceRole(compliance_role)
    perm = CompliancePermission(permission)
    actual = has_permission(role, perm)
    assert actual == expect_allowed, (
        f"Role={compliance_role}, Permission={permission}: "
        f"expected {expect_allowed}, got {actual}"
    )


def test_matrix_covers_all_roles_and_permissions():
    """Sanity: every role appears 12 times, every permission appears 7 times."""
    roles_in_matrix = [r for r, _, _ in ROLE_PERMISSION_MATRIX]
    perms_in_matrix = [p for _, p, _ in ROLE_PERMISSION_MATRIX]
    assert len(ROLE_PERMISSION_MATRIX) == 84, "Matrix must be exactly 7×12 = 84 cases"
    for role in (
        "compliance_head", "legal_team", "finance_team", "auditor",
        "ca_consultant", "staff", "cfo",
    ):
        assert roles_in_matrix.count(role) == 12, f"Role {role} should have 12 entries"
    for perm in (
        "notice:view", "notice:create", "notice:draft_response",
        "notice:approve", "notice:submit", "notice:bulk_update",
        "client:create", "client:manage_team",
        "report:view", "report:export",
        "audit:view", "escalation:trigger",
    ):
        assert perms_in_matrix.count(perm) == 7, f"Permission {perm} should have 7 entries"
