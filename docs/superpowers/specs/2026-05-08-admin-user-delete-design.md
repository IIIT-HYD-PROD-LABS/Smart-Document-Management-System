# Admin user deletion — design

**Date:** 2026-05-08
**Status:** Approved (in-conversation), awaiting written-spec review
**Scope:** Add the ability for an `admin` to remove a user account from the system.

## Problem

The admin panel today supports only role change and active/inactive toggle. There is no way to remove a user account, so retired employees, test fixtures, and abuse cases pile up in the user list and continue to hold unique `email` / `username` / `oauth_id` slots.

The naive answer (hard `DELETE FROM users`) is blocked by the audit-log immutability trigger:
- `audit_logs.user_id` has `ON DELETE SET NULL`.
- Migration `0014_audit_log_immutability` installs a `BEFORE UPDATE OR DELETE` trigger on `audit_logs` that raises `EXCEPTION 'audit_logs is append-only — % is forbidden'`.
- A foreign-key cascade SET NULL is implemented as an `UPDATE`, so it would fire the trigger and abort the parent `DELETE` of the user. Hard delete therefore fails for any user with audit history.

## Decision

**Soft-delete with PII anonymization** under the existing `admin` role.

| Field | Action on delete |
|---|---|
| `deleted_at` | set to `now()` (new column, partial index) |
| `is_active` | `False` |
| `email` | `f"deleted-{id}-{epoch}@deleted.local"` (frees the unique slot for re-registration) |
| `username` | `f"deleted_{id}_{epoch}"` |
| `full_name` | `NULL` |
| `oauth_id` | `NULL` (frees the unique slot) |
| `hashed_password` | `NULL` |
| `refresh_tokens` (active) | revoked, `revoked_at = now()` |
| `documents` | cascade-deleted by FK (existing behavior) |
| `document_permissions` (as user) | cascade-deleted by FK |
| `document_permissions.granted_by` | SET NULL by FK |
| `audit_logs.user_id` | left intact — `audit_logs` keeps pointing at row id, but the row is now anonymized. Trigger never fires. |
| `compliance_*` references | already SET NULL on FK |

Why this choice:
- Audit chain stays cryptographically valid (ids unchanged, trigger untouched).
- GDPR-style PII removal satisfied.
- Unique slots (`email`, `username`, `oauth_id`) freed for future re-registration.
- Reversible if needed (the row exists, the deleted_at can be cleared by a DBA in an incident).
- No relaxation of the security model.

Why not a new `super_admin` role:
- Existing `admin` role already holds the most destructive privileges (role demotion, deactivation). Adding deletion to admin extends an existing trust boundary instead of creating a new one. A new role would require migration, frontend role guards, and add complexity for a single new capability.

## Architecture

```
Browser (Admin)                 FastAPI                        PostgreSQL
─────────────────               ───────                        ──────────
[Delete] click ──┐
                 │  DELETE /api/admin/users/{id}
                 ├──────────────────────────────►  require_admin
                 │                                 │
                 │                                 ├─ guard: not self
                 │                                 ├─ guard: user exists
                 │                                 ├─ guard: not last admin
                 │                                 │
                 │                                 ├──── txn ────────────►  UPDATE users
                 │                                 │                          SET deleted_at,
                 │                                 │                              email=…,
                 │                                 │                              username=…,
                 │                                 │                              oauth_id=NULL,
                 │                                 │                              hashed_password=NULL,
                 │                                 │                              full_name=NULL,
                 │                                 │                              is_active=false
                 │                                 │
                 │                                 │                       UPDATE refresh_tokens
                 │                                 │                          SET is_revoked=true,
                 │                                 │                              revoked_at=now()
                 │                                 │                       WHERE user_id=… AND NOT is_revoked
                 │                                 │
                 │                                 │                       (FK CASCADE removes
                 │                                 │                        documents + own perms;
                 │                                 │                        SET NULL on granted_by;
                 │                                 │                        audit_logs untouched.)
                 │                                 │
                 │                                 ├── BackgroundTasks: log_audit_event(action="user_delete", …)
                 │                                 │
                 │  200 {detail, user_id}          │
                 ◄─────────────────────────────────┘
```

## Components

### Backend (`backend/`)

1. **Migration `alembic/versions/0030_add_user_deleted_at.py`**
   - `ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ NULL;`
   - `CREATE INDEX ix_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NOT NULL;` (partial — soft-deleted rows are the minority)
   - `downgrade()` drops the index then the column.

2. **`app/models/user.py`**
   - Add `deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)`
   - Add `@property def is_deleted(self) -> bool: return self.deleted_at is not None`

3. **`app/schemas/admin.py`**
   - Extend `AdminUserResponse` with `deleted_at: datetime | None = None`

4. **`app/routers/admin.py`** — new endpoint:
   ```python
   @router.delete("/users/{user_id}")
   @limiter.limit("5/minute")
   def delete_user(
       request, response, background_tasks,
       user_id: int = PathParam(..., ge=1),
       db = Depends(get_db),
       current_user = Depends(require_admin),
   ):
       # guards
       if user_id == current_user.id:
           raise HTTPException(400, "Cannot delete your own account")
       user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
       if not user:
           raise HTTPException(404, "User not found")
       if user.role == "admin":
           remaining = db.query(func.count(User.id)).filter(
               User.role == "admin", User.is_active == True, User.deleted_at.is_(None)
           ).scalar()
           if remaining <= 1:
               raise HTTPException(400, "Cannot delete the last admin")

       # anonymize + soft-delete
       ts = int(datetime.now(timezone.utc).timestamp())
       user.email = f"deleted-{user.id}-{ts}@deleted.local"
       user.username = f"deleted_{user.id}_{ts}"
       user.full_name = None
       user.oauth_id = None
       user.hashed_password = None
       user.is_active = False
       user.deleted_at = datetime.now(timezone.utc)

       # revoke tokens
       db.query(RefreshToken).filter(
           RefreshToken.user_id == user_id,
           RefreshToken.is_revoked == False,
       ).update({"is_revoked": True, "revoked_at": datetime.now(timezone.utc)})

       try:
           db.commit()
       except (IntegrityError, OperationalError):
           db.rollback()
           raise HTTPException(503, "Failed to delete user")

       background_tasks.add_task(
           log_audit_event,
           user_id=current_user.id, action="user_delete",
           resource_type="user", resource_id=user_id,
           details={"deleted_username_was": …, "deleted_email_was": …},
           ip_address=…
       )
       return {"detail": "User deleted", "user_id": user_id}
   ```

5. **`list_users` filter** — add `.filter(User.deleted_at.is_(None))` so soft-deleted rows do not appear in the admin list. Same for `get_user_detail` (404s a deleted user instead of revealing its anonymized state).

### Frontend (`frontend/`)

1. **`src/lib/api.ts`** — `adminApi.deleteUser(id: number) => api.delete('/admin/users/${id}')`

2. **`src/app/dashboard/admin/page.tsx`**
   - Add a `Delete` icon button (FiTrash2, danger color) per row.
   - Disabled for self (matches the existing role/status disabled pattern).
   - Click opens a confirmation modal:
     - Shows username, email, document count, irreversible warning.
     - Type-to-confirm (user must retype the username); button stays disabled until match.
     - On confirm → call API → toast + refetch list + refetch stats.
   - The modal lives in a small new component: `src/components/admin/DeleteUserModal.tsx`.

### Tests (`backend/tests/test_admin.py`)

- `test_admin_can_delete_user`
- `test_admin_cannot_delete_self`
- `test_admin_cannot_delete_last_admin`
- `test_non_admin_cannot_delete`
- `test_deleted_user_cannot_login` (verifies the existing `is_active` guard fires)
- `test_deleted_user_pii_anonymized`
- `test_deleted_user_documents_cascaded`
- `test_deleted_user_refresh_tokens_revoked`
- `test_deleted_user_audit_log_preserved` (the trigger-bypass invariant)
- `test_deleted_user_excluded_from_list`

## Error handling

- DB write failure (IntegrityError / OperationalError) → 503, transaction rolled back, no anonymization persisted.
- Audit-event write is `BackgroundTasks` so it cannot roll back the user delete; failures land in structlog (mirroring existing pattern in `update_user_role`).
- Type-to-confirm modal prevents accidental deletes.

## Out of scope (explicit YAGNI)

- Restore-deleted-user endpoint (DBA-only via SQL until a real product need surfaces).
- Bulk delete.
- Email notification to deleted user.
- Cascading delete of compliance memberships beyond the existing FK CASCADE — already handled by `0017_db_roles` + `compliance_memberships.user_id ON DELETE CASCADE`.
- New `super_admin` role.

## Risks

| Risk | Mitigation |
|---|---|
| Admin accidentally deletes a real user | Type-to-confirm modal + last-admin guard + 5/min rate limit |
| Re-registration with the same email creates two rows | Anonymized email is unique per (id, epoch) — original email slot is free, new registration creates a new row |
| Audit log holds dangling user_id | Designed: row still exists (anonymized), so the FK is still satisfied; reports that join `audit_logs.user_id → users.id` see the anonymized row |
| Soft-deleted user shows up in compliance role lookups | Existing FK CASCADE on `compliance_memberships.user_id` removes their memberships; permission checks resolve to no roles |
