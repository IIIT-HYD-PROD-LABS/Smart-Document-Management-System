# 04 · DATABASE SCHEMA

> PostgreSQL 16 · SQLAlchemy 2.0 · Alembic head `0032_add_ai_credentials` · RLS · FTS · audit trigger

## ★ Remember
- One DB, multi-tenant via Row Level Security
- `audit_logs` is immutable (DB trigger)
- Full-text search = `tsvector` + GIN + trigger-maintained
- 32 numbered Alembic revisions on `main`
- Production uses Supabase session-mode pooler

---

## 1. v1.0 core ERD

```
┌────────────┐  1   ∞ ┌────────────────┐
│   users    │────────│   documents    │
│  id (PK)   │        │ id (PK)        │
│  email UQ  │        │ user_id FK     │
│  role      │        │ category enum  │
│  hashed_pwd│        │ status  enum   │
│  oauth_id  │        │ celery_task_id │
│  deleted_at│        │ search_vector  │
└─────┬──────┘        │ ai_summary     │
      │               └────┬───────────┘
      │ 1∞                 │ 1∞
      ▼                    ▼
┌──────────────┐    ┌────────────────────┐
│refresh_tokens │   │document_permissions │
│ token UQ     │    │ document_id / user_id│
│ is_revoked   │    │ permission           │
│ replaced_by  │    └────────────────────┘
│ expires_at   │
└──────────────┘
          ┌────────────────────┐
          │   audit_logs       │  (immutable trigger)
          │ user_id / action   │
          └────────────────────┘
```

## 2. v2.0 compliance ERD

```
compliance_clients ──┬──► compliance_memberships ── users
   (tenant root)     │
                     ├──► compliance_client_registrations
                     ├──► compliance_notices
                     │      ├ parent_notice_id (self-FK)
                     │      ├ document_id  → v1.0 documents
                     │      ├ notice_type_id
                     │      ├ search_vector tsvector
                     │      ├ risk_tier · risk_score
                     │      └──► compliance_notice_activity
                     │           compliance_notice_tags
                     │           compliance_responses
                     │           compliance_response_drafts (versioned)
                     │
                     └──► ai_credentials (one row per tenant)

compliance_review_queue        (low-confidence triage)
compliance_regulatory_calendar (FY 25-26 seeds, 37 entries)
compliance_alerts              (APScheduler jobstore: apscheduler_jobs)
compliance_notice_types        (taxonomy)
compliance_audit_log           (append-only trigger)
```

---

## 3. `users` (selected columns)

| Column | Type |
|--------|------|
| id | int PK |
| email | varchar(255) UQ |
| username | varchar(100) UQ |
| hashed_password | varchar(255) NULL |
| role | `admin` \| `editor` \| `viewer` |
| auth_provider | `local` \| `google` \| `microsoft` |
| oauth_id | varchar(255) UQ NULL |
| is_active | boolean |
| deleted_at | timestamptz NULL **(soft-delete)** |
| created_at / updated_at | timestamptz |

## 4. `documents` (selected columns)

| Column | Note |
|--------|------|
| id | PK |
| user_id | FK users |
| filename / original_filename | storage + display |
| file_path / s3_url | one or the other |
| category | enum: bills · upi · tickets · tax · bank · invoices · unknown |
| status | pending → processing → completed / failed |
| confidence_score | float |
| celery_task_id | polling handle |
| extracted_text | text — feeds FTS |
| search_vector | tsvector — trigger-maintained |
| ai_summary / ai_extracted_fields | LLM output |
| highlighted_text | JSON spans |
| notice_id | Phase 9 FK to compliance_notices |
| source_email_id | Phase 15 FK to gmail_message_log |
| source | manual · portal · gmail · imap (CHECK) |

## 5. `compliance_notices` (selected columns)

| Column | Note |
|--------|------|
| id | PK |
| client_id | FK — RLS pivot |
| parent_notice_id | self-FK for SCN → Assessment → Demand → Appeal chain |
| document_id | FK → documents (reuses v1.0 OCR pipeline) |
| notice_number | indexed |
| authority | `GST · IT · MCA · RBI · SEBI` (CHECK) |
| status | 6-state machine (CHECK) |
| response_deadline / hearing_date / compliance_date / appeal_deadline | 4 dates |
| tax_demand · interest · penalty · total_liability | Numeric(18,2) INR |
| risk_score / risk_tier | Phase 10 ML |
| ner_extracted_fields | JSONB |
| search_vector | tsvector trigger-maintained |
| source | manual · portal · gmail · imap |

---

## 6. Row Level Security (RLS)

```sql
ALTER TABLE compliance_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_notices FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON compliance_notices
  USING (
    client_id = current_setting('app.current_client_id')::int
    OR current_setting('app.cross_client_mode')::bool
  );

-- migration 0019: fail-closed
CREATE POLICY deny_when_empty ON compliance_notices
  AS RESTRICTIVE TO app_runtime
  USING (current_setting('app.current_client_id', true) IS NOT NULL);
```

- RLS is set per table in `0015_compliance_rls_policies`
- `0017_db_roles.py` creates the `app_runtime` role (no BYPASSRLS)
- `0018_fix_rls_cross_client_recursion.py`
- `0019_rls_fail_closed_on_empty_tenant.py` — empty tenant returns zero rows
- `0024_supabase_security_advisor_fixes.py` — closes Supabase advisor flags

---

## 7. Audit immutability (DB trigger)

```sql
-- migration 0014 — defense in depth
CREATE FUNCTION reject_audit_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only';
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update
  BEFORE UPDATE OR DELETE ON audit_logs
  FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();

-- migration 0017 — revoke even from app_runtime role
REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime;
```

Even a compromised application cannot tamper. This is why `users` uses `deleted_at` for soft-delete (migration 0030) — actually deleting a user is blocked by the audit trigger.

---

## 8. Full-text search

```sql
-- migration 0003 (documents) + 0023 (compliance_notices)
ALTER TABLE documents ADD COLUMN search_vector tsvector;

CREATE INDEX ix_documents_fts ON documents USING GIN (search_vector);

CREATE FUNCTION docs_fts_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    to_tsvector('english', coalesce(NEW.original_filename,'')) ||
    to_tsvector('english', coalesce(NEW.extracted_text,''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER docs_fts BEFORE INSERT OR UPDATE
  ON documents FOR EACH ROW EXECUTE FUNCTION docs_fts_trigger();
```

`tsvector` is populated by the trigger only — never written from Python. The GIN index makes `@@ to_tsquery(...)` near-O(log n).

> **Trap:** never add `Index(...)` for GIN in SQLAlchemy — Alembic autogenerate has a known false-diff bug. Create the GIN index via `op.execute()` in the migration.

---

## 9. Alembic timeline (selected)

| Rev   | What |
|-------|------|
| 097ce… | initial — users, documents, refresh_tokens |
| 0003  | FTS tsvector + GIN + trgm |
| 0007  | OAuth fields |
| 0010  | audit_logs |
| 0013  | compliance foundation (10 tables) |
| 0014  | audit immutability trigger |
| 0015  | compliance RLS policies |
| 0017  | DB roles + REVOKE |
| 0019  | RLS fail-closed empty tenant |
| 0020  | Phase 10 ML columns + review_queue |
| 0021  | Phase 11 alert tables |
| 0022  | Phase 12 response workflow |
| 0023  | Phase 13 search_vector on notices |
| 0026  | apscheduler_jobs table |
| 0030  | users.deleted_at (soft-delete) |
| 0031  | client branding fields |
| **0032** | ai_credentials (BYOK Fernet) |

---

## 10. DB roles

| Role | Powers |
|------|--------|
| `postgres` | super (dev only) |
| `app_migrator` | OWNS schema · runs Alembic · BYPASSRLS |
| `app_runtime` | SELECT/INSERT only · NOT owner · NO BYPASSRLS · DELETE/UPDATE revoked on `audit_logs` |

The tenant-context listener does `SET ROLE app_runtime` on every cursor execute, even when authenticated as a higher-privilege user — guarantees RLS is enforced.

---

## 11. Key indexes

- `ix_documents_user_id`, `ix_documents_category`, `ix_documents_status`
- `idx_documents_category_user` (composite)
- `idx_documents_created_at`
- `ix_notices_client_status`, `ix_notices_client_authority` (composite)
- `ix_notice_activity_notice_created` (composite — timeline)
- `ix_documents_fts`, `ix_compliance_notices_fts` (GIN tsvector)
- `ix_documents_source`, `ix_documents_source_email_id`
- `idx_audit_action_created` (composite)

---

## 12. Enum catalogue

| Enum | Values |
|------|--------|
| UserRole | admin · editor · viewer |
| DocumentCategory | bills · upi · tickets · tax · bank · invoices · unknown |
| DocumentStatus | pending → processing → completed / failed |
| NoticeStatus | received → under_review → response_drafted → submitted → resolved / dismissed |
| Authority | GST · IT · MCA · RBI · SEBI |
| RiskTier | critical · high · medium · low |
| ResponseStage | drafter → reviewer → legal → cfo |
| ComplianceRole | compliance_head · legal · finance · auditor · ca · staff · cfo |

---

> "The DB is the last line of defense.
> If the app forgets to filter by tenant, RLS still does."

**Hygiene rules:**
- NEVER write `search_vector` from Python — let the trigger do it
- NEVER add an `Index(...)` for GIN in SQLAlchemy — use `op.execute()` in the migration
- NEVER hard-delete users — the audit trigger blocks it; use `deleted_at`
- NEVER assume RLS — always `SET ROLE app_runtime` in tests
