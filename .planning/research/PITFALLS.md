# PITFALLS.md
## Critical Failures & Common Mistakes in Legal/Finance Document Management Systems

**Project Context:** Smart Document Management SaaS for legal/finance professionals (5-20 user teams). FastAPI + Next.js + PostgreSQL + AWS S3, adding LLM extraction, advanced search, RBAC, and production hardening.

**Purpose:** This document catalogs mistakes that can derail the project, cause security breaches, or create massive technical debt. Each pitfall includes real-world evidence, warning signs, and mitigation strategies.

---

## 1. Critical Pitfalls (Cause Rewrites or Major Issues)

### 1.1 LLM Hallucination on Legal Documents

**What Goes Wrong:**
LLMs fabricate case citations, misinterpret legal clauses, or confidently extract incorrect dates/amounts from contracts. Stanford research (2024) found hallucination rates of **69-88%** on legal queries, with ChatGPT-4 hallucinating **58% of the time** and Llama 2 at **88%**. Lower court cases hallucinate more than Supreme Court cases (75%+ error rate on holdings).

**Why It Happens:**
- Legal documents use domain-specific language (Latin terms, statutory references)
- LLMs lack grounding in actual case law databases
- Training data quality varies dramatically for legal vs. general text
- Models don't understand the difference between "plaintiff" and "defendant" context
- Synthetic training data (like our current ML classifier) doesn't capture real legal nuances

**How to Avoid:**
- **Never use raw LLM output for legal facts** without human verification
- Implement confidence thresholds AND manual review workflows for extractions
- Use RAG (Retrieval-Augmented Generation) with verified legal databases
- Add "hallucination detection" by cross-referencing extracted case names against legal databases (Caselaw Access Project, CourtListener)
- Show extraction confidence scores prominently in UI
- Log all LLM inputs/outputs for audit trails

**Warning Signs:**
- Users report "wrong dates" or "case citations that don't exist"
- Extraction confidence scores cluster below 70%
- Legal team rejects documents due to "incorrect summaries"
- Compliance audits flag missing source verification

**Phase to Address:**
- **Phase 1 (Foundation):** Set up extraction audit logging
- **Phase 2 (Core Features):** Implement confidence scoring and human-in-the-loop review
- **Phase 3 (Advanced):** Add RAG with legal databases

**Real-World Example:**
A Manhattan lawyer submitted a ChatGPT-generated brief with "bogus judicial decisions, bogus quotes, and bogus internal citations" (2024 case). The lawyer faced sanctions.

---

### 1.2 Data Privacy Violations with External LLM APIs

**What Goes Wrong:**
Sending confidential legal/financial documents to OpenAI, Anthropic, or other LLM APIs violates attorney-client privilege, GDPR Article 44 (data transfers), and client confidentiality agreements. 77% of organizations cite regulatory compliance as a key barrier to generative AI adoption (2024).

**Why It Happens:**
- Default LLM API integrations send full document text to third-party servers
- Developers assume "encryption in transit" equals compliance
- No Data Processing Agreements (DPAs) with LLM providers
- EU customer data processed on US servers violates GDPR data residency rules
- API providers may use data for model training unless explicitly opted out

**How to Avoid:**
- **Use self-hosted LLMs** for sensitive documents (Llama 3.1, Mistral, private deployments)
- If using external APIs:
  - Sign Data Processing Agreements (DPAs) with providers
  - Enable opt-out from training data usage
  - Ensure EU data stays in EU data centers (GDPR Article 44)
  - Redact PII before sending to APIs (names, SSNs, account numbers)
- Add explicit user consent: "This document will be processed by [Provider] under our DPA"
- Implement client-side encryption for document storage
- Audit all API calls with document metadata (who, when, what data sent)

**Warning Signs:**
- Legal counsel raises concerns about "where data is processed"
- GDPR compliance audit flags "unauthorized data transfers"
- Clients ask "who has access to our documents?"
- No DPA in place with LLM provider

**Phase to Address:**
- **Phase 0 (Pre-Build):** Evaluate self-hosted vs. API-based LLMs
- **Phase 1 (Foundation):** Set up DPAs, configure API opt-outs, add audit logging
- **Phase 2 (Core Features):** Implement PII redaction, document-level consent tracking

**Current Codebase Issue:**
No LLM integration yet, but when added, the existing exception handling (line 77-79 in `documents.py`) would silently log errors without recording what data was sent to external services.

---

### 1.3 RBAC Permission Bypass Vulnerabilities

**What Goes Wrong:**
Users access documents they shouldn't see due to misconfigured Role-Based Access Control. Common failures include:
- Horizontal privilege escalation (User A reads User B's documents)
- Vertical privilege escalation (Junior associate sees partner-only files)
- Object-level authorization missing (API checks user auth but not document ownership)
- Permission inheritance bugs (deleted team members retain access)

Research shows overlapping/bloated RBAC roles are a top cause of enterprise security vulnerabilities (2024).

**Why It Happens:**
- Current code only checks `Document.user_id == current_user.id` (line 105, 256 in `documents.py`)
- No team/organization/matter-based permissions
- No "need-to-know" enforcement (all team members see all docs by default)
- Missing permission checks on file download endpoints
- JWT tokens lack role/permission claims

**How to Avoid:**
- Implement **hierarchical permissions**: Organization → Matter → Document
- Use attribute-based access control (ABAC) for complex rules ("only assigned attorneys on Matter X")
- Add permission checks at EVERY database query:
  ```python
  # BAD (current code)
  doc = db.query(Document).filter(Document.id == document_id).first()

  # GOOD
  doc = db.query(Document).join(Matter).filter(
      Document.id == document_id,
      Matter.id.in_(current_user.accessible_matter_ids)
  ).first()
  ```
- Test permission boundaries with automated security tests (e.g., "user1 cannot see user2's docs")
- Audit all permission changes (log who granted/revoked access)
- Implement "least privilege" by default (no access unless explicitly granted)

**Warning Signs:**
- Users report "I saw someone else's document"
- Penetration testing finds authorization bypasses
- No permission-specific unit tests
- Database queries lack permission filters

**Phase to Address:**
- **Phase 1 (Foundation):** Add organization/matter models, basic RBAC
- **Phase 2 (Core Features):** Implement permission middleware, add security tests
- **Phase 3 (Advanced):** ABAC for complex rules, audit logging

**Current Codebase Issue:**
All documents.py routes check `current_user.id` but lack team/matter context. Adding shared documents in Phase 2 will break this model.

---

### 1.4 Document Encryption Implementation Failures

**What Goes Wrong:**
Encryption done incorrectly provides false security. Common mistakes:
- Encryption at rest but keys stored in same database
- No encryption in transit (HTTP instead of HTTPS)
- Weak encryption algorithms (DES, MD5)
- Key management failures (hardcoded keys, no rotation)
- Customer-Managed Keys (CMK) only apply to data at rest, not in-transit processing

2024 data breach average cost: **$4.88 million**, with 46% involving customer PII. 86% of organizations experienced successful attacks on in-transit data (Cisco 2023).

**Why It Happens:**
- Developers assume "S3 encryption" is enough (it's not—keys must be managed separately)
- No end-to-end encryption (data decrypted at API gateway, re-encrypted to S3)
- TLS misconfiguration (weak ciphers, expired certificates)
- Plaintext storage of extracted document text in PostgreSQL (line 73 `documents.py`)

**How to Avoid:**
- **Encrypt at rest AND in transit:**
  - Use S3 Server-Side Encryption with KMS (SSE-KMS), not default SSE-S3
  - Rotate KMS keys quarterly
  - Enable TLS 1.3 for all API traffic (reject TLS 1.0/1.1)
- **Encrypt sensitive database fields:**
  - Use `pgcrypto` for PostgreSQL column-level encryption
  - Encrypt `extracted_text`, `original_filename` in DB
  - Store encryption keys in AWS Secrets Manager, not code
- **End-to-end encryption option:**
  - Client-side encryption for highest security (user holds keys)
  - Backend cannot read document contents
- **Key management:**
  - Never hardcode keys (current issue: `SECRET_KEY` default in `config.py` line 23)
  - Use AWS KMS or HashiCorp Vault
  - Implement key rotation policies

**Warning Signs:**
- Hardcoded secrets in config files
- Database backups contain plaintext document text
- No key rotation schedule
- Security audit flags "data in transit not encrypted"

**Phase to Address:**
- **Phase 0 (Immediate):** Remove hardcoded `SECRET_KEY`, enforce HTTPS
- **Phase 1 (Foundation):** Enable S3 SSE-KMS, set up AWS Secrets Manager
- **Phase 2 (Core Features):** Encrypt sensitive DB fields with `pgcrypto`
- **Phase 3 (Advanced):** Optional client-side encryption for ultra-sensitive clients

**Current Codebase Issues:**
- `config.py` line 23: `SECRET_KEY = "super-secret-key-change-in-production"` (CRITICAL)
- No S3 encryption configured in `storage_service.py`
- `extracted_text` stored as plaintext in PostgreSQL

---

### 1.5 JWT Security Weaknesses

**What Goes Wrong:**
JWT vulnerabilities allow attackers to forge tokens and impersonate users. Critical issues:
- Algorithm confusion (accept `alg: none`)
- Signature verification bypassed
- Long-lived tokens never expire
- No token rotation/refresh mechanism
- Service account keys permanent (a 2024 key still valid in 2026)

Six critical CVEs from 2025 expose millions to remote code execution via JWT flaws.

**Why It Happens:**
- JWT libraries have default vulnerabilities if not configured correctly
- Tokens stored in localStorage (vulnerable to XSS)
- No `exp` claim validation
- Key management failures (signing keys in code, no rotation)

**How to Avoid:**
- **Strict signature verification:**
  - Explicitly specify algorithm (`HS256` only, reject `none`)
  - Validate `exp`, `nbf`, `iat` claims
  - Reject tokens without signatures
- **Short-lived tokens + refresh tokens:**
  - Access tokens: 15-30 minutes (not 24 hours like current config)
  - Refresh tokens: 7 days, stored in httpOnly cookies
  - Rotate refresh tokens on each use
- **Secure storage:**
  - Store tokens in httpOnly, secure, SameSite cookies (not localStorage)
  - Add CSRF protection for cookie-based auth
- **Key rotation:**
  - Rotate JWT signing keys monthly
  - Use asymmetric keys (RS256) instead of symmetric (HS256) for better security
- **Monitoring:**
  - Log all token issuance/validation failures
  - Detect anomalous token usage (same token from multiple IPs)

**Warning Signs:**
- Tokens never expire (config shows 24-hour tokens)
- No refresh token mechanism
- Signing key in source code
- No token revocation capability

**Phase to Address:**
- **Phase 0 (Immediate):** Reduce token lifetime to 30 minutes, add `exp` validation
- **Phase 1 (Foundation):** Implement refresh tokens, rotate signing keys
- **Phase 2 (Core Features):** Switch to RS256, add token revocation list
- **Phase 3 (Advanced):** Anomaly detection for token usage

**Current Codebase Issues:**
- `config.py` line 25: 24-hour token expiration (too long)
- `security.py` line 37: Using symmetric HS256 (asymmetric RS256 preferred)
- No refresh token mechanism
- Hardcoded `SECRET_KEY` used for signing

---

### 1.6 Database Migration Failures on Production Data

**What Goes Wrong:**
Schema migrations corrupt data, cause downtime, or fail mid-migration with partial data loss. Bloor Group reports **80%+ of migrations run over time/budget**, with legacy formats causing **45% of failures** and average delays of **3-6 months**.

**Why It Happens:**
- No migration testing on production-scale data
- Forward-only migrations (no rollback plan)
- Schema changes break application code (deployed code expects old schema)
- Locks on large tables cause timeouts
- Data type mismatches (storing text in integer columns)
- Relationship constraints break (orphaned foreign keys)

**Real-World Example:**
TSB Bank (2018): Migration introduced millions of data inconsistencies—mismapped customer records, incorrect balances, unauthorized transactions. Called "most significant IT disaster in UK banking history."

**How to Avoid:**
- **Test migrations thoroughly:**
  - Use production database backups in staging
  - Test with full production data volume (not 100-row test data)
  - Test rollback procedures
- **Zero-downtime migrations:**
  - Add new columns as nullable first, then backfill data
  - Use dual-write pattern (write to old + new columns during transition)
  - Avoid lock-heavy operations (`ALTER TABLE` on 100M rows)
- **Version migrations:**
  - Use Alembic (FastAPI) with auto-generated but human-reviewed migrations
  - Each migration must have a rollback script
  - Tag migrations with ticket/issue numbers for traceability
- **Validation:**
  - Run data integrity checks post-migration (row counts, foreign key validity)
  - Compare checksums of critical data before/after
- **Backup:**
  - Take full database backup before migration
  - Test restore procedure (don't assume backups work)

**Warning Signs:**
- Migrations only tested on dev databases with 10 rows
- No rollback scripts
- Manual SQL changes instead of versioned migrations
- Production outages after deployments

**Phase to Address:**
- **Phase 0 (Immediate):** Set up Alembic, create initial migration
- **Phase 1 (Foundation):** Test migrations on production-scale data, add rollback scripts
- **Phase 2-4:** Pre-test all schema changes in staging with full data clones

**Current Codebase Issues:**
- No migration framework visible (likely using SQLAlchemy auto-create, which breaks on schema changes)
- No rollback procedures
- Adding FTS (Phase 2) or RBAC tables (Phase 1) will require careful migration planning

---

## 2. Moderate Pitfalls (Cause Delays or Technical Debt)

### 2.1 LLM Cost Explosion at Scale

**What Goes Wrong:**
LLM API costs grow exponentially due to:
- Context window bloat (500 tokens → 2,000 tokens with chat history)
- Multi-turn conversations accumulate context
- Processing same document multiple times (no caching)
- Using expensive models for simple tasks (GPT-4 for classification when GPT-3.5 Turbo sufficient)

**Real-World Data (2024):**
- Enterprise chatbot saw **3x token consumption growth** in 30 days after adding memory
- If starting with 500 tokens/query, growing to 2,000 = **4x cost multiplier per request**
- DeepSeek R1 costs **$0.55/$2.19 per million tokens** vs. GPT-4 at **$5/$15** (90% savings)

**How to Avoid:**
- **Tiered model strategy:**
  - Use small models (GPT-3.5 Turbo, GPT-4o mini) for classification
  - Reserve GPT-4/Claude Opus for complex extraction
- **Caching:**
  - Cache extracted document text (don't re-extract on every view)
  - Use semantic caching for similar queries
- **Context management:**
  - Limit conversation history to last 5 messages
  - Summarize old context instead of sending full history
- **Cost monitoring:**
  - Set billing alerts at $100, $500, $1000 thresholds
  - Log per-user API costs
  - Implement rate limiting (10 extractions/user/hour)

**Warning Signs:**
- Monthly API bill jumps 10x unexpectedly
- Users abuse "re-extract" features
- No cost tracking per user/document

**Phase to Address:**
- **Phase 2 (Core Features):** Implement extraction caching, tiered models
- **Phase 3 (Advanced):** Add cost monitoring dashboard, per-user quotas

---

### 2.2 Search Index Synchronization Issues

**What Goes Wrong:**
Full-text search indexes (PostgreSQL FTS, Elasticsearch) become stale/out-of-sync with source data:
- Document updated in PostgreSQL but FTS index not rebuilt
- Elasticsearch loses data during network partitions
- Concurrent updates corrupt index state
- Index rebuilding takes hours and blocks writes

**Why It Happens:**
- No CDC (Change Data Capture) pipeline
- Manual index rebuilding
- Elasticsearch update API has no concurrency safety
- PostgreSQL ILIKE (current implementation) doesn't use indexes efficiently

**How to Avoid:**
- **For PostgreSQL FTS (Phase 2):**
  - Use triggers to auto-update `tsvector` columns on INSERT/UPDATE
  - Create GIN indexes on `tsvector` columns
  - Use `ts_rank` for relevance sorting
- **For Elasticsearch (future):**
  - Use Debezium or Logstash for CDC-based sync
  - Implement versioning to handle concurrent updates
  - Set up monitoring for sync lag (alert if >5 minutes behind)
- **Testing:**
  - Add integration tests: "update document, verify search reflects change within 30s"

**Warning Signs:**
- Users report "I updated a document but search doesn't find new content"
- Search returns deleted documents
- Index rebuild scripts run manually

**Phase to Address:**
- **Phase 2 (Core Features):** Replace ILIKE with PostgreSQL FTS + triggers
- **Phase 3 (Advanced):** Migrate to Elasticsearch with CDC sync

**Current Codebase Issues:**
- `documents.py` line 113: Uses `ILIKE` (slow, no relevance ranking)
- No FTS indexes defined in `document.py` model
- No CDC pipeline for eventual Elasticsearch migration

---

### 2.3 OAuth State Management Bugs

**What Goes Wrong:**
OAuth/OIDC integration failures:
- State parameter missing (CSRF vulnerability, CVE-2024-10318)
- Nonce not validated (session fixation)
- Token reuse attacks
- Provider-specific quirks (Microsoft vs. Google vs. Okta)

**Why It Happens:**
- Copy-paste OAuth examples without understanding
- Not validating `state` parameter on callback
- Storing OAuth tokens in localStorage (XSS risk)

**How to Avoid:**
- **Use battle-tested libraries:** NextAuth.js (Next.js), Authlib (FastAPI)
- **Validate everything:**
  - Check `state` parameter matches what you sent
  - Validate `nonce` in ID token
  - Verify token signatures
- **Secure storage:**
  - Store OAuth tokens in httpOnly cookies
  - Use session storage, not localStorage
- **Test with multiple providers:**
  - Google, Microsoft, Okta each have different quirks
  - Test error cases (user denies access, expired token)

**Warning Signs:**
- OAuth callback fails with cryptic errors
- Users get logged in as wrong person
- Security audit flags missing state validation

**Phase to Address:**
- **Phase 2 (Core Features):** Add OAuth SSO with NextAuth.js/Authlib
- Test with 2+ providers before launch

---

### 2.4 Over-Engineering Permission Models

**What Goes Wrong:**
Building a permission system more complex than needed:
- Supporting 20 roles when 3 would suffice (Admin, Attorney, Paralegal)
- Implementing custom ABAC when RBAC is enough
- Permission checks everywhere hurt performance (N+1 queries)

**How to Avoid:**
- **Start simple:**
  - Phase 1: Organization-level permissions (Owner/Member)
  - Phase 2: Matter-level permissions (Attorney/Paralegal)
  - Phase 3: Document-level if needed
- **Use existing patterns:**
  - Django-style permissions (add, change, delete, view)
  - Don't invent custom permission languages
- **Optimize checks:**
  - Cache user permissions in session (not DB hit per request)
  - Use SQL JOINs to filter querysets, not Python loops

**Warning Signs:**
- 10+ roles defined in Phase 1
- Permission checks take >100ms
- Business users don't understand permission model

**Phase to Address:**
- **Phase 1:** Org-level RBAC (3 roles max)
- **Phase 2:** Matter-level permissions
- **Phase 3:** Evaluate if document-level needed (probably not)

---

### 2.5 ML Model Accuracy Degradation Over Time

**What Goes Wrong:**
Document classifier accuracy drops from 85% to 65% over 6 months due to:
- **Data drift:** New document types not in training data (e.g., blockchain contracts in 2024)
- **Concept drift:** Legal language evolves (new regulations change terminology)
- **Model staleness:** Trained on 2023 data, doesn't recognize 2025 patterns

**Real-World Stats (2024):**
- **91% of ML models degrade** over time (MIT study)
- **75% of businesses** see AI performance declines without monitoring
- Models unchanged for 6+ months see **35% error rate increase**
- Global fintech saw credit scoring precision drop **18% in 6 months**

**Why It Happens:**
- No model retraining pipeline
- No accuracy monitoring in production
- Training data frozen at launch
- Model trained on synthetic data (current issue: line 13 `classifier.py` has finance-only categories)

**How to Avoid:**
- **Production monitoring:**
  - Track confidence scores over time (alert if avg drops below 70%)
  - Sample 5% of predictions for human review
  - Log misclassifications reported by users
- **Retraining pipeline:**
  - Collect production labels (users correct wrong classifications)
  - Retrain monthly with new data
  - A/B test new models before deployment
- **Data collection:**
  - Add "Report Incorrect Classification" button
  - Store user corrections as ground truth
- **Thresholds for action:**
  - Retrain if accuracy drops below 80%
  - Alert if confidence scores trend downward for 7+ days

**Warning Signs:**
- Users frequently override ML classifications
- Confidence scores drop from 85% average to 60%
- New document types get "unknown" classification

**Phase to Address:**
- **Phase 2 (Core Features):** Add classification feedback UI, log corrections
- **Phase 3 (Advanced):** Automate retraining pipeline, A/B testing
- **Phase 4 (Production):** Continuous monitoring dashboard

**Current Codebase Issues:**
- `classifier.py` line 13: Finance-only categories (bills, UPI, tickets, tax, bank, invoices)
- No legal document types (contracts, briefs, discovery, pleadings)
- No retraining pipeline
- Model trained on synthetic data (no production feedback loop)

---

## 3. Minor Pitfalls (Annoying but Recoverable)

### 3.1 File Upload Size Limits Too Small

**What Goes Wrong:**
50MB limit (`config.py` line 29) blocks legitimate legal documents:
- Contract packages with exhibits: 100-500MB
- Discovery document sets: 1GB+
- Scanned case files: 200MB+

**How to Avoid:**
- Increase limit to 200MB for legal documents
- Add chunked upload for files >100MB
- Use resumable uploads (AWS S3 multipart upload)

**Phase to Address:** Phase 1 (bump to 200MB), Phase 2 (chunked uploads)

---

### 3.2 Lack of Bulk Operations

**What Goes Wrong:**
Users must upload/tag/delete documents one-by-one. Law firms need:
- Bulk upload (drag 50 files)
- Batch classification correction
- Multi-select delete

**How to Avoid:**
- Add batch upload endpoint (accept array of files)
- UI: Multi-select checkboxes + bulk actions toolbar
- Background jobs for bulk operations (Celery)

**Phase to Address:** Phase 2 (bulk upload), Phase 3 (bulk tagging)

---

### 3.3 Poor Error Messages for Users

**What Goes Wrong:**
User sees "Processing error: list index out of range" (line 79 `documents.py`) instead of "OCR failed: document appears blank."

**How to Avoid:**
- Never show raw exceptions to users
- Map technical errors to user-friendly messages:
  - `TesseractError` → "Could not read text from image"
  - `S3 403` → "Permission denied accessing storage"
- Return actionable guidance: "Try uploading a clearer scan"

**Phase to Address:** Phase 1 (immediate - sanitize all error messages)

---

### 3.4 No Document Preview

**What Goes Wrong:**
Users can't verify document content without downloading. Need:
- PDF preview in browser (PDF.js)
- Image thumbnails
- Text preview (first 500 chars)

**How to Avoid:**
- Use PDF.js for client-side rendering
- Generate thumbnails on upload (ImageMagick)
- Show extracted text snippet in search results

**Phase to Address:** Phase 2 (thumbnails), Phase 3 (full preview)

---

## 4. Technical Debt Patterns

### 4.1 "We'll Add Logging Later" Syndrome

**Debt:** No structured logging (`print` statements in `classifier.py` line 27).

**Long-Term Cost:**
- Can't debug production issues
- No audit trail for compliance
- Can't track performance bottlenecks

**Fix:** Add structured logging (Python `logging` + JSON formatter) in Phase 1.

---

### 4.2 Synchronous Processing Blocks Uploads

**Debt:** Document processing happens synchronously (line 69-82 `documents.py`).

**Long-Term Cost:**
- Upload endpoint times out for slow OCR
- Users wait 30+ seconds for classification
- Can't scale to concurrent uploads

**Fix:** Move to Celery background tasks in Phase 2.

---

### 4.3 Generic Exception Handling

**Debt:** `except Exception as e` (line 77 `documents.py`) catches everything.

**Long-Term Cost:**
- Hides bugs (silent failures)
- Can't distinguish transient errors from fatal bugs
- No retry logic for network failures

**Fix:** Catch specific exceptions (`TesseractError`, `S3ClientError`), log with context.

---

### 4.4 No Database Connection Pooling

**Debt:** Default SQLAlchemy settings may not pool connections efficiently.

**Long-Term Cost:**
- Connection exhaustion under load
- Slow query performance
- Database server overload

**Fix:** Configure connection pool in `database.py` (pool_size, max_overflow).

---

## 5. Integration Gotchas

### 5.1 LLM API Rate Limits

**Gotcha:** OpenAI enforces per-minute token limits (90k tokens/min for Tier 1).

**Impact:** Batch document processing hits rate limit, jobs fail.

**Mitigation:**
- Implement exponential backoff retry
- Queue system with rate limiting (Celery + Redis)
- Monitor `RateLimitError` exceptions, pause processing

---

### 5.2 OAuth Provider-Specific Quirks

**Gotcha:**
- Google requires `prompt=consent` for refresh tokens
- Microsoft requires `offline_access` scope for refresh tokens
- Okta returns groups in `groups` claim, Azure AD in `roles`

**Mitigation:**
- Test with ALL target providers before launch
- Abstract provider differences in adapter layer
- Use NextAuth.js (handles quirks automatically)

---

### 5.3 PostgreSQL Full-Text Search Locale Issues

**Gotcha:** FTS configurations are language-specific (`english`, `spanish`). Default `english` config stems "legalization" → "legal" but mishandles legal Latin terms ("habeas corpus").

**Mitigation:**
- Use `simple` configuration for legal documents (no stemming)
- Create custom FTS configuration for legal terminology
- Test with real legal document corpus

---

### 5.4 S3 Eventual Consistency

**Gotcha:** After `PUT`, immediate `GET` may return 404 (rare but happens).

**Mitigation:**
- Use S3 Strong Consistency (default since Dec 2020, but verify region support)
- Add retry logic for 404 on newly uploaded files
- Don't assume upload succeeded—verify with HEAD request

---

### 5.5 Celery Task Serialization

**Gotcha:** Passing SQLAlchemy objects to Celery tasks breaks (not JSON serializable).

**Mitigation:**
- Pass IDs, not objects: `process_document.delay(doc_id)` not `process_document.delay(doc)`
- Use `apply_async` with `serializer='json'` explicitly

---

## 6. Performance Traps

### 6.1 N+1 Query Problem

**Trap:** Loading 100 documents + their owners = 101 queries (line 132-133 `documents.py`).

**Symptom:** API response takes 2+ seconds for 20 documents.

**Fix:** Use `joinedload` or `selectinload`:
```python
query.options(joinedload(Document.owner)).all()
```

---

### 6.2 ILIKE Without Indexes

**Trap:** `ILIKE '%search%'` does full table scan (line 113 `documents.py`).

**Symptom:** Search takes 5+ seconds on 100k documents.

**Fix:** Use PostgreSQL FTS with GIN index (Phase 2).

---

### 6.3 Uploading Large Files to Memory

**Trap:** `await file.read()` loads entire file into RAM (line 40 `documents.py`).

**Symptom:** 100MB upload causes OOM error.

**Fix:** Stream uploads to S3 using `file.file` (file-like object):
```python
s3_client.upload_fileobj(file.file, bucket, key)
```

---

### 6.4 Unbounded Pagination

**Trap:** `per_page=100` max (line 99) but users can request page 1000 (offset 100,000).

**Symptom:** Query takes 30+ seconds, times out.

**Fix:**
- Limit total offset (e.g., max page 100)
- Use cursor-based pagination for deep pagination
- Return error: "Please narrow your search, too many results"

---

### 6.5 Missing Database Indexes

**Trap:** Filtering by `category` + `user_id` without composite index.

**Symptom:** Slow queries as data grows.

**Fix:** Already addressed in `document.py` line 75 (`idx_documents_category_user`) but verify index is created via migration.

---

## 7. Security Mistakes (Domain-Specific)

### 7.1 Leaking Document Existence via Error Messages

**Mistake:** Returning 404 "Document not found" vs. 403 "Access denied" leaks info.

**Attack:** Attacker iterates document IDs to map what exists.

**Fix:** Always return 404 for unauthorized access (don't distinguish "exists but forbidden" from "doesn't exist").

---

### 7.2 No Document Access Audit Trail

**Mistake:** Not logging who viewed/downloaded documents.

**Risk:** Legal discovery requires proof of "who saw what when."

**Fix:**
- Log all document access: `user_id`, `document_id`, `action` (view/download), `timestamp`, `ip_address`
- Retention: 7 years for legal compliance
- UI: "Document Access History" tab

**Phase to Address:** Phase 2 (Core Features)

---

### 7.3 Client-Side File Type Validation Only

**Mistake:** Trusting file extension from client (line 32 `documents.py`).

**Attack:** Upload `malware.exe` renamed to `malware.pdf`.

**Fix:**
- Validate MIME type server-side (use `python-magic`)
- Check file magic bytes (PDF starts with `%PDF`)
- Reject mismatched extensions (file claims .pdf but magic bytes say .exe)

**Phase to Address:** Phase 1 (Immediate)

---

### 7.4 Directory Traversal in File Paths

**Mistake:** If `file_path` construction uses user input:
```python
# BAD
file_path = f"{UPLOAD_DIR}/{user_input_filename}"
# User sends "../../etc/passwd"
```

**Current Code:** Safe (uses `generate_filename` with UUID), but ensure future changes don't break this.

**Fix:** Always sanitize filenames, never trust user input.

---

### 7.5 Missing Rate Limiting

**Mistake:** No rate limiting on upload/search endpoints.

**Attack:** User uploads 1000 documents/minute, DoS attack or cost explosion.

**Fix:**
- Add rate limiting: 20 uploads/hour per user, 100 searches/hour
- Use Redis-backed rate limiter (slowapi for FastAPI)

**Phase to Address:** Phase 2 (Core Features)

---

### 7.6 Exposing Internal IDs

**Mistake:** Using sequential integer IDs (line 33 `document.py`).

**Risk:** Attacker guesses document IDs (1, 2, 3...) to enumerate all documents.

**Fix:**
- Use UUIDs for document IDs (non-guessable)
- Or: Use integer IDs but add HMAC check in URL: `/documents/{id}/{hmac(id, secret)}`

**Phase to Address:** Phase 1 (switch to UUIDs)

---

## 8. UX Pitfalls for Legal/Finance Professionals

### 8.1 Legal-Specific Terminology Mismatch

**Pitfall:** UI says "folders" but lawyers expect "matters" or "cases."

**Impact:** Cognitive load, users think it's not built for them.

**Fix:** Use domain language:
- "Matter" not "Project"
- "Brief" not "Document Type: Brief"
- "Opposing Counsel" not "External User"

---

### 8.2 No Conflict Check Workflow

**Pitfall:** Law firms need "conflict check" before accepting cases (search if client name appears in other matters).

**Impact:** Manual process, high risk of ethics violations.

**Fix:**
- Add "Conflict Check" search (searches all firm documents, not just user's)
- Warn if potential conflict detected
- Log all conflict checks for ethics compliance

**Phase to Address:** Phase 3 (Advanced Features)

---

### 8.3 Missing Billable Hours Integration

**Pitfall:** Lawyers track time spent on documents in separate tools.

**Impact:** Context switching, lost billable time.

**Fix:**
- Add "Time Entry" button on document view
- Integrate with billing systems (Clio, PracticePanther)

**Phase to Address:** Phase 4 (Production Hardening)

---

### 8.4 No Redaction Tool

**Pitfall:** Lawyers must use external tools to redact SSNs, PII before filing.

**Impact:** Users export to Adobe, redact, re-upload (broken workflow).

**Fix:**
- Built-in redaction tool (black boxes over text)
- Auto-detect PII with regex (SSN: XXX-XX-XXXX)
- Permanent redaction (removes underlying text, not just visual)

**Phase to Address:** Phase 3 (Advanced Features)

---

### 8.5 Overloading Users with ML Confidence Scores

**Pitfall:** Showing "Confidence: 0.73482" confuses non-technical users.

**Impact:** Users ignore useful signal or distrust system.

**Fix:**
- Simplify: "High Confidence" (>80%), "Medium" (60-80%), "Low" (<60%)
- Or: Color coding (green/yellow/red)
- Hide exact scores behind "Show Details"

**Phase to Address:** Phase 2 (Core Features)

---

## 9. "Looks Done But Isn't" Checklist

Use this to avoid declaring features "complete" prematurely:

### Document Upload
- [ ] Works with 200MB files (not just 5MB test PDFs)
- [ ] Handles corrupted files gracefully (doesn't crash)
- [ ] Background processing (not blocking)
- [ ] Progress indicator (not just "Loading...")
- [ ] Retry failed uploads
- [ ] Validates MIME type server-side

### Search
- [ ] Relevance ranking (not just text match)
- [ ] Handles special characters (`&`, `%`, quotes)
- [ ] Performance: <500ms for 100k documents
- [ ] Pagination doesn't break on deep pages
- [ ] Highlights matched terms in results

### Authentication
- [ ] Refresh tokens (not just 24-hour access tokens)
- [ ] Token revocation (logout actually works)
- [ ] Handles concurrent logins (desktop + mobile)
- [ ] Password reset flow (with expiring tokens)
- [ ] CSRF protection

### Permissions
- [ ] Tested: User A cannot access User B's documents
- [ ] Tested: Deleted users lose access immediately
- [ ] Audit log of permission changes
- [ ] UI clearly shows "you don't have access" vs. "doesn't exist"

### ML Classification
- [ ] Trained on real data (not just synthetic)
- [ ] Handles multi-language documents
- [ ] Confidence threshold tuned on validation set
- [ ] Misclassification feedback loop
- [ ] Performance: <2 seconds per document

### Production Readiness
- [ ] All secrets in environment variables (not code)
- [ ] Structured logging to centralized system
- [ ] Health check endpoint (`/health`)
- [ ] Metrics exposed (Prometheus)
- [ ] Database connection pooling configured
- [ ] Error tracking (Sentry)
- [ ] Automated backups tested (restore verified)

---

## 10. Phase-Specific Warnings

### Phase 0: Foundation & Planning
**⚠️ Don't Skip:**
- Threat modeling (STRIDE framework)
- Data classification (what's PII, what's privileged)
- Compliance requirements doc (GDPR, ABA Model Rules)
- Load testing plan (how to simulate 20 concurrent users)

**⚠️ Common Mistake:** Assuming "we'll add security later" → it's 10x harder to retrofit.

---

### Phase 1: Basic RBAC & Security Hardening
**⚠️ Critical Path Items:**
- Remove hardcoded `SECRET_KEY` (blocks launch)
- Switch to UUIDs for document IDs (hard to change later)
- Set up proper migration framework (Alembic)

**⚠️ Don't Over-Build:**
- Don't implement 10 roles if 3 suffice
- Don't add field-level permissions yet
- Don't optimize queries with <1000 records

**⚠️ Testing Gaps:**
- Permission bypass testing (use automated security tests)
- Concurrent user testing (20 users uploading simultaneously)

---

### Phase 2: Advanced Search & LLM Integration
**⚠️ Critical Decision:** Self-hosted vs. API-based LLMs
- If using APIs: DPAs must be signed BEFORE integration
- If self-hosting: Infrastructure costs spike (GPU instances)

**⚠️ Search Pitfalls:**
- PostgreSQL FTS is fine for 100k documents, breaks at 1M+ (plan Elasticsearch migration)
- FTS triggers can slow down writes (test with 100 concurrent inserts)

**⚠️ LLM Integration:**
- Don't trust extraction accuracy without validation set
- Test hallucination rate on YOUR legal documents (not public benchmarks)
- Set cost alerts BEFORE testing at scale

---

### Phase 3: Production Features
**⚠️ Performance Cliffs:**
- Thumbnail generation blocks uploads (move to background)
- Bulk operations time out (need job queue)
- Elasticsearch sync lag grows (need monitoring)

**⚠️ UX Gotchas:**
- Advanced search too complex for non-power users (add "Simple/Advanced" toggle)
- Too many classification categories confuse users (group hierarchically)

---

### Phase 4: Scaling & Hardening
**⚠️ Infrastructure:**
- Don't assume single-server deployment scales (plan multi-region)
- Load balancer health checks must account for async workers
- Database read replicas need monitoring for replication lag

**⚠️ Monitoring Blindspots:**
- LLM API failures may not trigger alerts (need custom metrics)
- Celery worker crashes silently (need heartbeat monitoring)

---

## 11. Recovery Strategies (When Pitfalls Occur)

### Data Breach Response Plan
**If confidential documents leaked:**
1. **Immediate (Hour 0):**
   - Revoke all API keys/tokens
   - Disable affected user accounts
   - Take snapshot of logs (evidence preservation)
2. **Day 1:**
   - Notify affected clients (GDPR: 72-hour deadline)
   - Engage legal counsel + forensics team
   - Identify breach vector (credential leak? SQL injection?)
3. **Week 1:**
   - Implement fix + deploy
   - Force password reset for all users
   - Publish post-mortem (build trust)

**Prevention > Recovery:** Encrypt all documents at rest NOW, not after breach.

---

### LLM Hallucination Incident
**If user reports incorrect extraction caused legal error:**
1. **Immediate:**
   - Pull document + LLM input/output from logs
   - Disable auto-classification for that document type
   - Switch to manual review queue
2. **Day 1:**
   - Identify if systematic (affects all contracts) or one-off
   - If systematic: disable LLM feature, revert to manual workflow
3. **Week 1:**
   - Retrain/tune model on failure cases
   - Add validation checks (cross-reference extracted dates against OCR text)
   - Re-enable with human-in-the-loop review

**Key:** Have manual fallback workflow ready (don't depend 100% on LLM).

---

### Database Migration Failure
**If migration corrupts production data:**
1. **Immediate (5 min):**
   - STOP migration script
   - Put application in maintenance mode
   - Assess damage (run data integrity checks)
2. **Hour 1:**
   - If corruption detected: Restore from pre-migration backup
   - If data OK but migration incomplete: Roll forward or roll back (based on testing)
3. **Day 1:**
   - Post-mortem: Why did it fail? (timeout? constraint violation?)
   - Fix migration script
   - Test on staging (full production data clone)
4. **Week 1:**
   - Re-attempt migration with monitoring
   - Verify data integrity post-migration

**Prevention:** ALWAYS test migrations on production-scale data in staging.

---

### OAuth Integration Breaks
**If users can't log in after OAuth deployment:**
1. **Immediate:**
   - Enable fallback to password-based login
   - Check OAuth provider status (is Google down?)
   - Review callback URL configuration (common issue)
2. **Hour 1:**
   - Check logs for specific error (invalid_state? invalid_grant?)
   - Test OAuth flow in incognito window (cache issues)
3. **Day 1:**
   - If provider-side issue: Add status page link
   - If our issue: Roll back OAuth, keep password login

**Prevention:** Don't disable password login until OAuth proven stable for 1+ week.

---

### Performance Degradation
**If search goes from 200ms to 5 seconds:**
1. **Immediate:**
   - Check query logs (which query is slow?)
   - Run `EXPLAIN ANALYZE` on slow query
   - Check if index missing or not used
2. **Hour 1:**
   - Add missing index
   - Scale up database (if CPU/memory maxed)
3. **Week 1:**
   - Implement caching (Redis)
   - Optimize slow queries
   - Add performance monitoring (alert if p95 latency >1s)

**Prevention:** Set up query performance monitoring from Day 1 (pg_stat_statements).

---

### Cost Spike
**If AWS bill jumps from $100 to $5,000:**
1. **Immediate:**
   - Check AWS Cost Explorer (which service?)
   - If S3: Look for data transfer spikes
   - If LLM API: Check token usage logs
2. **Hour 1:**
   - Disable suspect service (if abuse detected)
   - Set billing alarm (alert at $1000)
3. **Day 1:**
   - Identify root cause (user uploaded 10TB? LLM infinite loop?)
   - Implement rate limiting
   - Add per-user cost tracking

**Prevention:** Set billing alerts at $100, $500, $1000 thresholds BEFORE launch.

---

## Conclusion: Use This Document Actively

**How to Use This Document:**

1. **Pre-Phase Checklist:** Before starting each phase, read relevant sections
2. **Code Review:** Reference during PR reviews ("Are we doing the SQL injection thing?")
3. **Incident Response:** When issues occur, check Recovery Strategies
4. **Onboarding:** New developers read this before touching code

**Keep It Updated:**
- Add new pitfalls as discovered
- Mark resolved issues with `[FIXED in vX.X]`
- Link to specific commits/PRs that address each issue

**Success Metric:** If you catch 80% of these pitfalls BEFORE they hit production, this document succeeded.

---

## Sources & Further Reading

### LLM Hallucination & Legal AI
- [Stanford Law: Hallucinating Law - Legal Mistakes with LLMs are Pervasive](https://law.stanford.edu/2024/01/11/hallucinating-law-legal-mistakes-with-large-language-models-are-pervasive/)
- [Stanford HAI: Legal Hallucination Research](https://hai.stanford.edu/news/hallucinating-law-legal-mistakes-large-language-models-are-pervasive)
- [LLM Hallucinations: Production Failures ($500B problem)](https://medium.com/@yobiebenjamin/the-500-billion-hallucination-how-llms-are-failing-in-production-75ebb589a76c)

### Legal DMS Challenges
- [LexWorkplace: Implementing Legal Document Management Systems](https://lexworkplace.com/implementing-a-document-management-system/)
- [Everything Wrong With Legal Document Management Software](https://lexworkplace.com/everything-wrong-with-legal-document-management-software/)
- [Filevine: 5 Most Brutal Challenges for Legal Document Management](https://www.filevine.com/blog/most-brutal-challenges-for-legal-document-management/)
- [Document Management Challenges 2024](https://www.b2be.com/en_us/blog/document-management-challenges-2024/)

### Security & RBAC
- [RBAC Best Practices 2025](https://www.osohq.com/learn/rbac-best-practices)
- [SSO Protocol Security Vulnerabilities (SAML, OAuth, OIDC, JWT)](https://guptadeepak.com/security-vulnerabilities-in-saml-oauth-2-0-openid-connect-and-jwt/)
- [Common OAuth Vulnerabilities - Doyensec](https://blog.doyensec.com/2025/01/30/oauth-common-vulnerabilities.html)
- [JWT Vulnerabilities List 2026](https://redsentry.com/resources/blog/jwt-vulnerabilities-list-2026-security-risks-mitigation-guide)

### Data Privacy & GDPR
- [Navigating GDPR Compliance in LLM Lifecycle](https://www.private-ai.com/en/2024/04/02/gdpr-llm-lifecycle/)
- [Balancing Innovation and Privacy: LLMs under GDPR](https://www.getdynamiq.ai/post/balancing-innovation-and-privacy-llms-under-gdpr)
- [Data Security for Third-Party LLM APIs in Enterprise](https://www.rohan-paul.com/p/data-security-and-privacy-precautions)

### Database & Performance
- [PostgreSQL Full-Text Search Performance](https://risingwave.com/blog/implementing-high-performance-full-text-search-in-postgres/)
- [When Postgres Stops Being Good Enough for FTS](https://www.meilisearch.com/blog/postgres-full-text-search-limitations)
- [Search Index Sync: PostgreSQL to Elasticsearch](https://gocardless.com/blog/syncing-postgres-to-elasticsearch-lessons-learned/)

### Database Migrations
- [Data Migration Risks Checklist](https://www.montecarlodata.com/blog-data-migration-risks-checklist/)
- [Common Data Migration Challenges](https://www.datafold.com/blog/common-data-migration-risks)
- [Migration War Stories: When Database Moves Go Wrong](https://www.alibabacloud.com/tech-news/a/database_migration/guh6vm4vpd-migration-war-stories-when-database-moves-go-wrong)

### Encryption
- [5 Common Mistakes with Encryption at Rest](https://evervault.com/blog/common-mistakes-encryption-at-rest)
- [Data at Rest vs In Transit Encryption](https://www.serverion.com/uncategorized/data-at-rest-vs-data-in-transit-encryption-explained/)

### LLM Costs & Scaling
- [LLM API Pricing Comparison 2025](https://intuitionlabs.ai/articles/llm-api-pricing-comparison-2025)
- [The Real Cost of Scaling LLMs](https://www.appunite.com/blog/the-real-cost-of-scaling-llms)
- [Taming the Beast: Cost Optimization for LLM API Calls](https://medium.com/@ajayverma23/taming-the-beast-cost-optimization-strategies-for-llm-api-calls-in-production-11f16dbe2c39)

### ML Model Drift
- [Handling LLM Model Drift in Production](https://www.rohan-paul.com/p/ml-interview-q-series-handling-llm)
- [Model Drift Detection: Preventing Silent Accuracy Decay](https://wetranscloud.com/blog/model-drift-detection-accuracy-decay)
- [AI Model Drift & Retraining Guide](https://smartdev.com/ai-model-drift-retraining-a-guide-for-ml-system-maintenance/)

### FastAPI Security
- [FastAPI Production Deployment Best Practices](https://render.com/articles/fastapi-production-deployment-best-practices)
- [FastAPI Best Practices for Production 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [Practical Guide to FastAPI Security](https://davidmuraya.com/blog/fastapi-security-guide/)

### Legal ML & Classification
- [Legal ML Datasets Collection](https://github.com/neelguha/legal-ml-datasets)
- [Multi-label Legal Document Classification Challenges](https://www.sciencedirect.com/science/article/abs/pii/S0306437921000016)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-17
**Maintained By:** Engineering Team
**Review Cycle:** Monthly during active development, quarterly post-launch
