# Architecture Research: Integrating Intelligence, Auth, and Production Features

**Research Date:** 2026-02-17
**Dimension:** Architecture
**Question:** How should smart extraction, AI features, advanced search, RBAC, and audit logging integrate with an existing FastAPI + Next.js + PostgreSQL document management architecture?

---

## Executive Summary

The existing system has a clean layered architecture (Next.js frontend, FastAPI REST API, SQLAlchemy/PostgreSQL, ML pipeline, storage abstraction) that provides strong integration points for new capabilities. This research defines six new architectural components, their boundaries, data flows, integration points with existing layers, and the build order that respects their dependency chain.

The core architectural principle: **new components integrate as service layers behind the existing API router layer**, preserving the current request flow while adding depth. The extraction pipeline extends the existing ML layer. Auth enhancements extend the existing security layer. Search and audit are new horizontal services that existing routers consume.

---

## 1. Component Definitions and Boundaries

### 1.1 LLM Extraction Service (`backend/app/services/extraction_service.py`)

**Purpose:** Extract structured data (dates, amounts, parties, clauses, deadlines) from document text using LLM providers, with fallback to local pattern-based extraction.

**Boundary:** Receives extracted text (string) and document type. Returns structured JSON with extracted fields. Does NOT touch the database, storage, or file system directly.

**Owns:**
- Provider abstraction (OpenAI, Anthropic, local regex fallback)
- Prompt templates per document type (contract, invoice, legal filing, financial report)
- Response parsing and validation
- Cost tracking per extraction call
- Retry logic and provider failover

**Does not own:**
- Text extraction from files (existing ML layer handles this via `app/ml/ocr.py` and `app/ml/pdf_extractor.py`)
- Database persistence of extracted data (router/task layer handles this)
- User-facing API endpoints (router layer handles this)

**Integration points with existing architecture:**
- **Consumes from:** `app/ml/classifier.py` output (extracted text + document category)
- **Called by:** `app/routers/documents.py` (upload flow) or `app/tasks/document_tasks.py` (async flow)
- **Configuration via:** `app/config.py` (API keys, provider selection, model names)

```
Existing flow:  file_bytes -> ml/ocr|pdf_extractor -> ml/classifier -> DB
New flow:       file_bytes -> ml/ocr|pdf_extractor -> ml/classifier -> extraction_service -> DB
                                                                          |
                                                                    LLM Provider API
```

**Internal structure:**
```python
class ExtractionProvider(ABC):
    """Abstract base for LLM providers."""
    async def extract(self, text: str, doc_type: str, schema: dict) -> dict: ...

class OpenAIProvider(ExtractionProvider): ...
class AnthropicProvider(ExtractionProvider): ...
class LocalPatternProvider(ExtractionProvider): ...  # regex fallback, no API cost

class ExtractionService:
    """Orchestrates extraction across providers with fallback."""
    def __init__(self, primary: ExtractionProvider, fallback: ExtractionProvider): ...
    async def extract_fields(self, text: str, doc_type: str) -> ExtractionResult: ...
```

---

### 1.2 AI Features Service (`backend/app/services/ai_service.py`)

**Purpose:** Generate document summaries, key insights, and question-answering over document content.

**Boundary:** Receives document text and a request type (summarize, extract insights, answer question). Returns generated text. Stateless -- does not persist anything itself.

**Owns:**
- Summary generation prompts
- Insight extraction logic
- Q&A over document text
- Provider abstraction (shares providers with extraction service)
- Response caching key generation

**Integration points:**
- **Shares providers with:** Extraction Service (same `ExtractionProvider` abstraction)
- **Called by:** New `app/routers/ai.py` router for on-demand features
- **Cache layer:** Redis (already configured at `settings.REDIS_URL`) for memoizing summaries

```
Frontend -> POST /api/ai/summarize/{doc_id} -> ai_router -> ai_service -> LLM Provider
                                                    |              |
                                                 get_doc       Redis cache
                                                 from DB       (check/store)
```

---

### 1.3 Search Service (`backend/app/services/search_service.py`)

**Purpose:** Provide full-text search with relevance ranking, faceted filtering, and highlighted snippets.

**Technology decision: PostgreSQL Full-Text Search (not Elasticsearch)**

Rationale:
- **Team size (5-20 users):** PostgreSQL FTS handles this scale with ease
- **Existing infrastructure:** PostgreSQL is already running, no new service needed
- **Feature parity:** `tsvector`/`tsquery` with `ts_rank_cd` provides relevance ranking, prefix matching, phrase search, and language-aware stemming
- **Simpler data consistency:** Index updates in same transaction as document updates
- **Migration path:** Search service abstraction allows swapping in Elasticsearch later

**Implementation:**
```sql
ALTER TABLE documents ADD COLUMN search_vector tsvector;
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);

CREATE FUNCTION documents_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.original_filename, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.category::text, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.extracted_text, '')), 'C');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_search
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_trigger();
```

---

### 1.4 RBAC and Permissions Layer (`backend/app/services/permissions_service.py`)

**Purpose:** Enforce role-based access control at the team level and document-level permissions for sharing.

**New database models:**

```python
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(UserRole), nullable=False)  # admin, editor, viewer

class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    permission = Column(Enum(PermissionLevel), nullable=False)
```

**Permission check replaces current user_id filtering:**
```python
# Current:
query = db.query(Document).filter(Document.user_id == current_user.id)

# New: documents filtered by ownership OR explicit permission OR team membership
def get_accessible_documents(db: Session, user: User) -> Query:
    return db.query(Document).filter(
        or_(
            Document.user_id == user.id,
            Document.id.in_(
                db.query(DocumentPermission.document_id)
                .filter(DocumentPermission.user_id == user.id)
            ),
            Document.user_id.in_(
                db.query(TeamMember.user_id)
                .filter(TeamMember.team_id == user.team_id)
            ),
        )
    )
```

---

### 1.5 SSO/OAuth Integration (`backend/app/services/oauth_service.py`)

**Purpose:** Allow users to authenticate via Google or Microsoft identity providers, in addition to existing email/password auth.

**OAuth flow:**
```
Frontend                     Backend                         Google/Microsoft
   |                            |                                   |
   |-- GET /auth/oauth/google ->|                                   |
   |                            |-- redirect to provider auth URL ->|
   |<- 302 redirect ------------|                                   |
   |-- user authorizes -------->|                                   |
   |                            |<-- callback with auth_code -------|
   |                            |-- exchange code for tokens ------>|
   |                            |<-- user profile + tokens ---------|
   |                            |-- find/create User, issue JWT     |
   |<- redirect to /dashboard --|   (same token format as login)    |
```

---

### 1.6 Audit Logging Service (`backend/app/services/audit_service.py`)

**Purpose:** Record all security-relevant and compliance-relevant actions for legal/financial document management.

**Approach:** HTTP middleware for automatic request logging + explicit calls for business events. Non-blocking via BackgroundTasks.

---

## 2. Data Flow: Complete Document Processing Pipeline

```
[1] User uploads file via frontend dropzone
[2] POST /api/documents/upload
[3] FastAPI handler validates file (type, size) -- EXISTING
[4] Storage service saves file (local/S3) -- EXISTING
[5] Document record created, status=PROCESSING -- EXISTING
[6] ** Permission check: user has upload permission ** -- NEW (RBAC)
[7] ** Audit log: "document.upload" event ** -- NEW (Audit)
[8] Celery task dispatched -- EXISTING (needs wiring)
     +--[8a] Text extraction (OCR/PDF) -- EXISTING
     +--[8b] ML classification (TF-IDF + sklearn) -- EXISTING
     +--[8c] ** LLM extraction: dates, amounts, parties, clauses ** -- NEW
     +--[8d] ** AI summary generation ** -- NEW
     +--[8e] ** Search index update: tsvector populated ** -- NEW (auto via trigger)
[9] Document record updated with all fields
[10] ** Audit log: "document.processed" event ** -- NEW
[11] Frontend polls or receives update
[12] User searches via full-text search -- NEW (replaces ILIKE)
      ** RBAC filters results to accessible documents ** -- NEW
```

---

## 3. Integration Points with Existing Layers

| New Component | Integrates With | How |
|---|---|---|
| **Extraction Service** | `app/ml/classifier.py` | Called after `extract_and_classify()` |
| **Extraction Service** | `app/config.py` | Reads LLM provider settings |
| **Search Service** | `app/models/document.py` | Adds `search_vector` column |
| **Search Service** | `app/routers/documents.py` | Replaces `search_documents()` |
| **RBAC Layer** | `app/utils/security.py` | Extends `get_current_user()` |
| **RBAC Layer** | `app/routers/documents.py` | Replaces `user_id` filter |
| **SSO/OAuth** | `app/routers/auth.py` | Adds OAuth endpoints |
| **Audit Logging** | `app/main.py` | Adds HTTP middleware |

### Modified Existing Files (by change volume)

1. `backend/app/routers/documents.py` -- Permission filtering, extraction, FTS search
2. `backend/app/models/document.py` -- search_vector, extracted_fields, summary columns
3. `backend/app/config.py` -- LLM, OAuth, audit, search settings
4. `backend/app/utils/security.py` -- Role-aware dependencies
5. `backend/app/models/user.py` -- team_id, role fields
6. `backend/app/main.py` -- New routers, audit middleware
7. `backend/app/tasks/document_tasks.py` -- Extraction + AI steps

### New Files to Create

```
backend/app/
  services/
    extraction_service.py
    ai_service.py
    search_service.py
    permissions_service.py
    oauth_service.py
    audit_service.py
  models/
    team.py, team_member.py, document_permission.py, oauth_account.py, audit_log.py
  routers/
    ai.py, admin.py, teams.py, permissions.py
  schemas/
    ai.py, team.py, permission.py, audit.py
```

---

## 4. Build Order

### Phase 1: Foundation
- **Step 1.1:** Initialize Alembic for database migrations
- **Step 1.2:** Audit logging (table + service + middleware)
- **Step 1.3:** PostgreSQL Full-Text Search (tsvector + GIN)

### Phase 2: Auth and Access Control
- **Step 2.1:** RBAC -- Teams, roles, permission service
- **Step 2.2:** Document-level permissions
- **Step 2.3:** SSO/OAuth integration

### Phase 3: Intelligence Layer
- **Step 3.1:** LLM extraction pipeline
- **Step 3.2:** AI features (summaries, insights, Q&A)
- **Step 3.3:** Wire Celery for full async pipeline

### Dependency Graph
```
Step 1.1: Alembic Migrations
    |
    +---> Step 1.2: Audit Logging
    +---> Step 1.3: Full-Text Search
    +---> Step 2.1: RBAC (Teams + Roles)
              |
              +---> Step 2.2: Document Permissions
              +---> Step 2.3: SSO/OAuth
              +---> Step 3.1: LLM Extraction Pipeline
                        |
                        +---> Step 3.2: AI Features
                        +---> Step 3.3: Async Pipeline
```

---

## 5. Docker Compose Changes

No new services required. PostgreSQL FTS eliminates the need for Elasticsearch. Redis handles caching. Only new environment variables added to existing backend service.

---

## 6. Risk Assessment

| Component | Integration Risk | Mitigation |
|---|---|---|
| **LLM Extraction** | External API dependency, variable latency, cost | Local fallback, timeouts, cost caps |
| **Full-Text Search** | Migration on existing data | Background backfill task |
| **RBAC** | Changes every document query | Comprehensive tests, default-deny |
| **SSO/OAuth** | External provider changes | Provider abstraction, version-pinned SDKs |
| **Audit Logging** | High write volume | Async writes, batch inserts, partitioning |

---

*Architecture research completed: 2026-02-17*
