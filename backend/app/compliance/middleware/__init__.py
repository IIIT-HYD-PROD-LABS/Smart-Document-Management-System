"""FastAPI middleware for compliance — Phase 9.

Two middleware layers compose orthogonally on every /api/compliance/* request:

  1. TenantContextMiddleware (this package)
     - Resolves X-Client-Id header → ContextVars
     - SQLAlchemy connection-checkout listener writes ContextVars to PostgreSQL
       session vars (app.current_client_id, app.cross_client_mode, app.user_id)
     - RLS policies (migration 0015 + 0018) automatically filter rows

  2. Auditor expiry check (auditor_expiry.is_membership_active)
     - Used by require_compliance_permission Depends factory
     - Rejects with 403 if access_start/access_end window is closed

Per RESEARCH Pitfall 6: Celery workers do NOT inherit middleware — task code
must call set_tenant_context_for_celery() explicitly before issuing queries.
"""
