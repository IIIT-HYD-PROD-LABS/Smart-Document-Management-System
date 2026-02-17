# Stack Research: Smart Document Management System -- New Additions

**Research Date:** 2026-02-17
**Scope:** New technologies needed for smart extraction, AI features, advanced search, enterprise auth, and production hardening
**Existing Stack:** Python 3.x, FastAPI 0.104.1, SQLAlchemy 2.0.23, PostgreSQL, Next.js 14.2.5, React 18, TypeScript, Tailwind CSS, scikit-learn, Tesseract OCR, pdfplumber, OpenCV, Docker, Redis/Celery

> **Version Verification Note:** All versions below are based on training data through May 2025. Versions marked with `[verify]` should be confirmed against PyPI/npm before pinning in requirements. The architectural recommendations and library choices remain valid regardless of minor version drift.

---

## 1. LLM Integration Layer (Smart Extraction + AI Summaries)

### 1A. LLM Provider SDKs

**OpenAI Python SDK**
- **Package:** `openai>=1.30.0` `[verify]`
- **Why:** GPT-4o and GPT-4o-mini are the strongest general-purpose models for structured data extraction from legal/financial documents. The v1.x SDK has native Pydantic model support for structured outputs (response_format=json_schema), which maps directly to your extraction schemas (dates, amounts, parties, clauses).
- **Confidence:** HIGH

**Anthropic Python SDK**
- **Package:** `anthropic>=0.28.0` `[verify]`
- **Why:** Claude 3.5 Sonnet / Claude Opus 4 excel at long-context document analysis (200K tokens). Critical for processing multi-page contracts and legal filings where the full document context matters for clause extraction.
- **Confidence:** HIGH

**What NOT to use:**
- **Google Vertex AI SDK (`google-cloud-aiplatform`):** Adds enormous dependency weight (500+ MB) and complex auth. Revisit for v2 if user demand exists.
- **Hugging Face Transformers for LLM inference:** Running 7B+ parameter models locally requires GPU infrastructure your target users won't have.
- **LlamaIndex:** Overlaps with LangChain but has a narrower focus on RAG. Since primary use case is extraction (not retrieval-augmented generation), LangChain's extraction chains are a better fit.

### 1B. LLM Orchestration Framework

**LangChain (Core)**
- **Package:** `langchain-core>=0.2.0` `[verify]`
- **Why:** Provides the abstraction layer for "user-configurable ML backend" requirement. LangChain's `BaseChatModel` interface lets you swap OpenAI, Anthropic, or local models without changing extraction logic. The `with_structured_output()` method directly maps extracted fields to Pydantic models.
- **Confidence:** HIGH

**LangChain Provider Packages**
- **Package:** `langchain-openai>=0.1.8` `[verify]`
- **Package:** `langchain-anthropic>=0.1.15` `[verify]`
- **Why:** Modular provider packages keep dependencies minimal. Only install what the deployment needs.
- **Confidence:** HIGH

**What NOT to use:**
- **Monolithic `langchain` package:** Pulls in dozens of unnecessary dependencies. Use `langchain-core` + specific provider packages only.
- **LiteLLM:** Simpler proxy layer but lacks LangChain's extraction chains, output parsers, and retry logic.
- **Direct API calls without a framework:** You will inevitably need retry logic, provider switching, structured output parsing, and token counting.

### 1C. Local NLP Models (Hybrid Extraction)

**spaCy**
- **Package:** `spacy>=3.7.0` `[verify]`
- **Model:** `en_core_web_trf` (transformer-based, ~500MB) or `en_core_web_lg` (CNN-based, ~560MB, no GPU needed)
- **Why:** Named Entity Recognition (NER) for extracting dates, monetary amounts, organization names, and person names from legal/financial text. Runs entirely locally (no API calls, no data leaving the system). Entity types (DATE, MONEY, ORG, PERSON) map directly to extraction fields.
- **Confidence:** HIGH

**dateparser**
- **Package:** `dateparser>=1.2.0` `[verify]`
- **Why:** Parses natural language dates from legal documents ("effective as of the 15th day of March, 2024", "due within 30 days of execution"). Far more robust than python-dateutil for the variety of date formats found in contracts.
- **Confidence:** HIGH

**price-parser**
- **Package:** `price-parser>=0.3.4` `[verify]`
- **Why:** Extracts monetary amounts with currency from text ("$1,250,000.00", "USD 50,000"). Purpose-built for financial amount extraction.
- **Confidence:** MEDIUM

### 1D. Extraction Output Schemas

**Pydantic v2 (already installed via pydantic-settings)**
- No new dependency needed. Extraction output schemas (ContractExtraction, InvoiceExtraction, etc.) should be Pydantic v2 models.
- **Confidence:** HIGH

---

## 2. Advanced Full-Text Search

### 2A. PostgreSQL Full-Text Search (Primary Recommendation)

**SQLAlchemy TSVector Support**
- **Package:** No new package needed -- SQLAlchemy 2.0.23 + psycopg2-binary 2.9.9 already support `tsvector` and `tsquery`
- **Why PostgreSQL FTS over Elasticsearch:**
  1. You already have PostgreSQL -- no new infrastructure
  2. PostgreSQL FTS handles millions of documents with proper GIN indexes
  3. Elasticsearch adds operational complexity (separate cluster, JVM tuning)
  4. Zero additional infrastructure cost
  5. `ts_rank()` and `ts_rank_cd()` provide relevance scoring
  6. Built-in dictionary/stemming for English legal terminology
- **Implementation:**
  ```sql
  ALTER TABLE documents ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(extracted_text, '') || ' ' || coalesce(original_filename, ''))) STORED;
  CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);
  ```
- **Confidence:** HIGH

**What NOT to use:**
- **Elasticsearch / OpenSearch:** Overkill for 5-20 user teams
- **Typesense / Meilisearch:** Still a separate service to manage
- **pgvector for keyword search:** pgvector is for semantic/vector search, not keyword search

### 2B. Semantic Search (Enhancement, Phase 2)

**pgvector**
- **Package:** `pgvector>=0.3.0` `[verify]`
- **PostgreSQL extension:** `CREATE EXTENSION vector;`
- **Why:** Enables "search by meaning" -- user searches "payment deadline" and finds documents containing "remittance due date".
- **Confidence:** MEDIUM -- Valuable but not required for v1.

---

## 3. Role-Based Access Control (RBAC) + Document-Level Permissions

**No new library needed -- implement with existing stack**
- **Why:** RBAC for 5-20 user teams with 3 roles (admin, editor, viewer) is straightforward with SQLAlchemy models and FastAPI dependencies.
- **Implementation:** Add `role` enum to User model, create `DocumentPermission` model, create FastAPI dependencies: `require_role()`, `require_document_access()`.
- **Confidence:** HIGH

**What NOT to use:**
- **Casbin (`pycasbin`):** Policy engine overkill for 3-role model
- **OPA (Open Policy Agent):** Enterprise-grade, requires separate sidecar service

---

## 4. SSO / OAuth Integration

### 4A. Backend OAuth

**Authlib**
- **Package:** `authlib>=1.3.0` `[verify]`
- **Why:** Most complete OAuth 2.0 / OpenID Connect library for Python. Supports Google, Microsoft, and generic OIDC providers. ASGI-native, integrates cleanly with FastAPI.
- **Confidence:** HIGH

### 4B. Frontend OAuth

**next-auth (Auth.js)**
- **Package:** `next-auth@4.24.x` `[verify]`
- **Why:** Standard authentication library for Next.js. Handles OAuth provider configuration, session management, CSRF protection, and token refresh. Fixes security issues in current custom cookie-based auth.
- **Confidence:** HIGH

---

## 5. Production Security Hardening

| Package | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| slowapi | >=0.1.9 `[verify]` | Rate limiting middleware for FastAPI | HIGH |
| structlog | >=24.1.0 `[verify]` | Structured JSON logging | HIGH |
| secure | >=1.0.0 `[verify]` | Security headers (HSTS, CSP, etc.) | HIGH |
| cryptography | >=42.0.0 `[verify]` | AES-256 encryption for documents at rest | HIGH |
| starlette-csrf | >=3.0.0 `[verify]` | CSRF protection | MEDIUM |

---

## 6. Testing Additions

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| pytest-asyncio | >=0.23.0 `[verify]` | Async test support for FastAPI |
| factory-boy | >=3.3.0 `[verify]` | Test data factories for models |
| respx | >=0.21.0 `[verify]` | Mock httpx requests for LLM/OAuth testing |

### Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| jest | ^29.x `[verify]` | Test runner |
| @testing-library/react | ^15.x `[verify]` | React component testing |
| msw | ^2.x `[verify]` | API mocking at network level |

---

## 7. Frontend Additions

| Package | Version | Purpose |
|---------|---------|---------|
| @tanstack/react-query | ^5.x `[verify]` | Server state management with caching |
| @tanstack/react-table | ^8.x `[verify]` | Headless table for search results |
| react-pdf | ^9.x `[verify]` | In-browser PDF preview |
| react-hook-form | ^7.x `[verify]` | Type-safe form handling |
| zod | ^3.22.x `[verify]` | Runtime schema validation |

---

## 8. Infrastructure Additions

**prometheus-fastapi-instrumentator**
- **Package:** `prometheus-fastapi-instrumentator>=7.0.0` `[verify]`
- **Why:** Prometheus metrics from FastAPI. Enables monitoring of API performance and ML processing times.

**Celery -- just wire it up (already installed)**
- No new package. Refactor document upload to use `.delay()`, add status polling endpoint.

---

## Summary: Complete New Dependency List

### Backend (requirements.txt additions)

```
# LLM Integration
openai>=1.30.0
anthropic>=0.28.0
langchain-core>=0.2.0
langchain-openai>=0.1.8
langchain-anthropic>=0.1.15

# Local NLP
spacy>=3.7.0
dateparser>=1.2.0
price-parser>=0.3.4

# Semantic Search (Phase 2)
pgvector>=0.3.0

# OAuth / SSO
authlib>=1.3.0

# Security Hardening
slowapi>=0.1.9
structlog>=24.1.0
secure>=1.0.0
cryptography>=42.0.0

# Monitoring
prometheus-fastapi-instrumentator>=7.0.0

# Testing (dev)
pytest-asyncio>=0.23.0
factory-boy>=3.3.0
respx>=0.21.0
```

### Frontend (package.json additions)

```json
{
  "dependencies": {
    "next-auth": "^4.24.0",
    "@tanstack/react-query": "^5.0.0",
    "@tanstack/react-table": "^8.0.0",
    "react-pdf": "^9.0.0",
    "react-hook-form": "^7.0.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "@testing-library/react": "^15.0.0",
    "msw": "^2.0.0"
  }
}
```

---

## Explicit Exclusions

| Technology | Reason |
|-----------|--------|
| Elasticsearch / OpenSearch | Overkill infrastructure for your scale |
| Pinecone / Weaviate / Qdrant | External vector DB unnecessary; pgvector suffices |
| Casbin / OPA | Policy engines overkill for 3-role RBAC |
| Clerk / Auth0 / Firebase Auth | Hosted auth with per-user fees and vendor lock-in |
| HuggingFace Transformers (large) | Requires GPU; use spaCy locally, LLM APIs for heavy lifting |
| MongoDB / DynamoDB | Adding a second database without clear benefit |
| GraphQL | REST is sufficient for document CRUD |

---

## Implementation Priority

1. **structlog** -- Immediate; needed before adding features
2. **Security hardening** (slowapi, secure, CORS fix, secrets) -- Immediate
3. **PostgreSQL Full-Text Search** (tsvector + GIN) -- Week 1; no new deps
4. **RBAC** (custom models) -- Week 1-2; foundational
5. **LLM Integration** (openai, anthropic, langchain, spaCy) -- Week 2-3; core differentiator
6. **OAuth/SSO** (authlib + next-auth) -- Week 3-4; depends on RBAC
7. **File Encryption** (cryptography) -- Week 3-4; independent
8. **Frontend Enhancements** (react-query, react-table, etc.) -- Week 2-4; parallel
9. **Semantic Search** (pgvector) -- Phase 2
10. **Monitoring** (prometheus) -- Before production deployment

---
*Stack research completed: 2026-02-17*
