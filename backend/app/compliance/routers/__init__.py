"""Phase 9 compliance routers package — Wave 4.

Seven router modules expose compliance functionality over HTTP under the
`/api/compliance` prefix (mounted in app/main.py):

  - clients              CLIENT-01..03, CLIENT-05 (onboarding, detail, dashboard)
  - memberships          CLIENT-05, RBAC-04 (team add/remove)
  - notices              LIFE-01..08 (CRUD + transition + bulk + chain + upload)
  - reports              CLIENT-07 (health-summary on demand)
  - audit                AUDIT-01 (read-only audit log viewer)
  - notice_types         D-01 (lookup; admins seed via DB)
  - regulatory_calendar  INFRA-05 (lookup; seeded by migration 0016)

Per Plan 04: every endpoint composes Depends(require_compliance_permission(...))
so the 84-case role/permission matrix is enforced at the route layer. RLS
isolation is automatic via TenantContextMiddleware — routers do NOT scope
queries by client_id manually.
"""
