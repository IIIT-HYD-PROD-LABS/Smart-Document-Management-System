# Phase 4: Search & Retrieval - Research

**Researched:** 2026-03-11
**Domain:** PostgreSQL Full-Text Search (FTS), pg_trgm, SQLAlchemy 2.0 dialect, Alembic migrations
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRCH-01 | User can perform full-text search across all document content with relevance ranking (PostgreSQL FTS) | tsvector stored column + GIN index + ts_rank ordering |
| SRCH-02 | User can filter search results by category, date range, and amount | SQLAlchemy WHERE clauses on existing `category`, `created_at`, and `extracted_metadata->amount` columns |
| SRCH-03 | Search supports fuzzy matching for partial terms and typos | pg_trgm extension, % similarity operator, GIN index with gin_trgm_ops |
| SRCH-04 | Search response time is under 2 seconds | GIN indexes eliminate sequential scans; pg_trgm 98%+ faster than full-table ILIKE |
</phase_requirements>

---

## Summary

Phase 4 upgrades the existing `ILIKE`-based search (no ranking, no fuzzy, sequential scan) to PostgreSQL's native full-text search stack. The two technologies involved are independent: **tsvector/tsquery** (FTS) for relevance-ranked keyword search, and **pg_trgm** (trigrams) for fuzzy/typo-tolerant matching. Both operate entirely within PostgreSQL — no external search service is needed — and both are indexed with GIN indexes that make sub-2-second response times achievable even with thousands of documents.

The project already has the `extracted_text` column on the `documents` table, which is the primary search target. The migration path is: add a `TSVECTOR` column to the `documents` table, populate it from `extracted_text || original_filename`, create a GIN index on it, enable pg_trgm as a PostgreSQL extension, add a GIN trigram index on `extracted_text`, then update the search endpoint to use `@@` (FTS match) combined with `%` (trigram similarity) and rank results by `ts_rank`.

Filters (SRCH-02) bolt onto the upgraded search as simple additional WHERE clauses — the amount filter is slightly more complex because amounts live inside the `extracted_metadata` JSONB column.

**Primary recommendation:** Use a stored `TSVECTOR` column (populated by a trigger) over a functional index, because Alembic has a confirmed bug (issue #1390) where functional `to_tsvector()` indexes trigger spurious migration diffs on every autogenerate run. The trigger approach keeps the model clean and avoids Alembic noise.

---

## Standard Stack

### Core
| Library / Feature | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| PostgreSQL FTS (tsvector/tsquery) | Built into Postgres | Stemmed full-text search with relevance ranking | Native; zero extra dependencies |
| pg_trgm | PostgreSQL extension (built-in) | Trigram similarity for fuzzy/typo matching | Only fuzzy solution native to Postgres |
| SQLAlchemy TSVECTOR type | `sqlalchemy.dialects.postgresql.TSVECTOR` | Type-safe column definition | Part of the SQLAlchemy 2.0 PostgreSQL dialect |
| sqlalchemy `func.*` | SQLAlchemy 2.0 | `func.to_tsvector`, `func.ts_rank`, `func.plainto_tsquery` | Official SQLAlchemy dialect approach |
| Alembic `op.execute()` | 1.18.4 (already installed) | Run raw DDL for triggers and pg_trgm extension | Required due to Alembic tsvector index bug |

### Supporting
| Library / Feature | Version | Purpose | When to Use |
|-------------------|---------|---------|-------------|
| GIN index (tsvector) | PostgreSQL built-in | Fast FTS lookups via inverted index | Always — without it FTS is slower than ILIKE |
| GIN index (gin_trgm_ops) | pg_trgm operator class | Fast trigram similarity lookups | Always — without it trigram search is O(n) |
| `websearch_to_tsquery` | PostgreSQL built-in | Handles multi-word user input safely | Alternative to `plainto_tsquery` if users type `AND`/`OR` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PostgreSQL FTS | Elasticsearch / OpenSearch | Elasticsearch far more powerful, but adds a service to deploy/maintain; overkill for thousands of documents |
| Stored tsvector column + trigger | Functional index on to_tsvector() | Functional index avoids the trigger but causes Alembic autogenerate to produce false diffs on every run (confirmed upstream bug) |
| pg_trgm via PostgreSQL | Python fuzzy libs (fuzzywuzzy, rapidfuzz) | Python-side fuzzy requires fetching all rows first; pg_trgm is indexed and runs inside the DB |

**Installation:** No new Python packages required. pg_trgm is a bundled PostgreSQL extension enabled with SQL:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## Architecture Patterns

### Current Search Endpoint (what must change)

```
GET /api/documents/search?q=...&category=...
```

Current implementation at `backend/app/routers/documents.py:129`:
- Uses `Document.extracted_text.ilike(f"%{q}%")` — sequential scan, no ranking, no typo tolerance
- Only supports `category` filter
- No date range or amount filter

### Target Search Endpoint

```
GET /api/documents/search?q=...&category=...&date_from=...&date_to=...&amount_min=...&amount_max=...
```

New implementation must:
1. Use tsvector `@@` match operator (SRCH-01)
2. Apply optional category/date/amount WHERE clauses (SRCH-02)
3. Fall back to OR-combine with trigram `%` similarity for typo tolerance (SRCH-03)
4. Order by `ts_rank` descending
5. Return in under 2 seconds (SRCH-04) — guaranteed by GIN indexes

### Recommended Database Changes

```
documents table (existing)
├── extracted_text TEXT       -- already exists, source for search
├── original_filename TEXT    -- already exists, included in search vector
├── search_vector TSVECTOR    -- NEW: stored column, populated by trigger
├── extracted_metadata JSONB  -- already exists, used for amount filter
├── category ENUM             -- already exists, already indexed
└── created_at DATETIME       -- already exists, used for date filter

indexes (new)
├── idx_documents_search_vector GIN (search_vector)
└── idx_documents_trgm GIN (extracted_text gin_trgm_ops)
```

### Pattern 1: Stored TSVECTOR Column with Trigger

**What:** A `TSVECTOR` column is stored on the `documents` table and kept up-to-date by a PostgreSQL trigger that fires on INSERT and UPDATE. The trigger calls `to_tsvector('english', ...)` combining `extracted_text` and `original_filename`.

**When to use:** This approach for any project using Alembic autogenerate — avoids the Alembic functional-index false-diff bug (issue #1390).

**Alembic migration (use `op.execute` for trigger and extension DDL):**
```python
# Source: Alembic docs + Alembic issue #1390 workaround pattern
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

def upgrade() -> None:
    # 1. Enable pg_trgm extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. Add the stored tsvector column
    op.add_column("documents", sa.Column("search_vector", TSVECTOR(), nullable=True))

    # 3. Backfill existing rows
    op.execute("""
        UPDATE documents
        SET search_vector = to_tsvector('english',
            COALESCE(extracted_text, '') || ' ' || COALESCE(original_filename, ''))
        WHERE status = 'completed'
    """)

    # 4. GIN index for FTS (use op.execute to avoid Alembic tsvector index bug)
    op.execute("""
        CREATE INDEX idx_documents_search_vector
        ON documents USING GIN (search_vector)
    """)

    # 5. GIN trigram index for fuzzy matching
    op.execute("""
        CREATE INDEX idx_documents_trgm
        ON documents USING GIN (extracted_text gin_trgm_ops)
    """)

    # 6. Trigger function to keep search_vector in sync
    op.execute("""
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                COALESCE(NEW.extracted_text, '') || ' ' ||
                COALESCE(NEW.original_filename, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 7. Attach trigger to table
    op.execute("""
        CREATE TRIGGER documents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update")
    op.execute("DROP INDEX IF EXISTS idx_documents_trgm")
    op.execute("DROP INDEX IF EXISTS idx_documents_search_vector")
    op.drop_column("documents", "search_vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

### Pattern 2: SQLAlchemy Model Update

**What:** Add the `search_vector` column to the `Document` model so SQLAlchemy is aware of it (for backfill operations and future `autogenerate` hints).

```python
# backend/app/models/document.py
from sqlalchemy.dialects.postgresql import TSVECTOR

class Document(Base):
    # ... existing columns ...
    search_vector = Column(TSVECTOR, nullable=True)
```

**Important:** Do NOT add the GIN index for `search_vector` to `__table_args__` using SQLAlchemy `Index(...)`. Doing so will recreate the Alembic autogenerate false-diff bug. Let the migration manage it with raw DDL only.

### Pattern 3: Updated Search Query (SQLAlchemy 2.0)

**What:** Replace the ILIKE query with a FTS match combined with trigram fallback, ordered by relevance rank.

```python
# Source: SQLAlchemy 2.0 PostgreSQL docs + community patterns
from sqlalchemy import func, or_, cast
from sqlalchemy.dialects.postgresql import TSVECTOR

def search_documents(q: str, category: str | None, date_from, date_to, amount_min, amount_max, ...):
    # Normalize query for FTS
    search_query = func.plainto_tsquery("english", q)

    # Base filter: user ownership + completed status
    base = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.status == DocumentStatus.COMPLETED,
    )

    # FTS match OR trigram similarity (OR-combine for typo tolerance)
    base = base.filter(
        or_(
            Document.search_vector.op("@@")(search_query),
            Document.extracted_text.op("%")(q),      # trigram similarity
        )
    )

    # SRCH-02: optional filters
    if category:
        base = base.filter(Document.category == DocumentCategory(category.lower()))
    if date_from:
        base = base.filter(Document.created_at >= date_from)
    if date_to:
        base = base.filter(Document.created_at <= date_to)
    if amount_min is not None:
        base = base.filter(
            Document.extracted_metadata["amount"].astext.cast(Float) >= amount_min
        )
    if amount_max is not None:
        base = base.filter(
            Document.extracted_metadata["amount"].astext.cast(Float) <= amount_max
        )

    # Rank by FTS relevance
    rank = func.ts_rank(Document.search_vector, search_query)
    documents = base.order_by(rank.desc()).offset(...).limit(...).all()
```

### Pattern 4: Frontend Filter Extension

The existing search page (`frontend/src/app/dashboard/search/page.tsx`) already has the form and API call structure. The `documentsApi.search` function in `frontend/src/lib/api.ts` needs new optional parameters appended to the query string.

```typescript
// frontend/src/lib/api.ts — extended search function
search: (query: string, category?: string, dateFrom?: string, dateTo?: string, amountMin?: number, amountMax?: number) => {
    const params = new URLSearchParams({ q: query });
    if (category) params.append("category", category);
    if (dateFrom) params.append("date_from", dateFrom);
    if (dateTo) params.append("date_to", dateTo);
    if (amountMin !== undefined) params.append("amount_min", String(amountMin));
    if (amountMax !== undefined) params.append("amount_max", String(amountMax));
    return api.get(`/documents/search?${params.toString()}`);
},
```

### Recommended Project Structure Changes

```
backend/
├── alembic/versions/
│   └── 0003_add_fts_and_trgm.py     -- NEW: FTS migration (tsvector, GIN, trigger, pg_trgm)
├── app/
│   ├── models/
│   │   └── document.py              -- ADD: search_vector TSVECTOR column
│   ├── routers/
│   │   └── documents.py             -- MODIFY: search endpoint (FTS + filters)
│   └── schemas/
│       └── document.py              -- MODIFY: SearchRequest + new filter fields
frontend/
└── src/
    ├── lib/
    │   └── api.ts                   -- MODIFY: documentsApi.search() — add filter params
    └── app/dashboard/search/
        └── page.tsx                 -- MODIFY: add date/amount filter inputs + UI
```

### Anti-Patterns to Avoid

- **Defining GIN tsvector index in SQLAlchemy `__table_args__`:** Causes Alembic to generate false diffs on every `autogenerate` run (Alembic issue #1390). Always manage this index via `op.execute()` in the migration.
- **Using `to_tsquery()` directly with raw user input:** `to_tsquery()` expects formatted query syntax; raw user input will raise syntax errors. Always use `plainto_tsquery()` (or `websearch_to_tsquery()`) for user-provided strings.
- **Applying `func.to_tsvector()` inline in WHERE clause:** Defeats the GIN index — PostgreSQL cannot use the index if tsvector is calculated at query time rather than from a stored column. Performance degrades from ~0.88s to ~41s on 10M rows.
- **Filtering on `extracted_metadata['amount']` without NULL guard:** The JSONB field is nullable; cast without COALESCE will silently drop documents with no amount data from results.
- **Running `CREATE EXTENSION pg_trgm` inside `upgrade()` without `IF NOT EXISTS`:** Extensions are cluster-scoped in PostgreSQL; re-running the migration on a DB where it already exists without IF NOT EXISTS will raise an error.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relevance ranking | Custom scoring algorithm | `func.ts_rank()` | Postgres ts_rank implements BM25-adjacent ranking accounting for word frequency and position |
| Fuzzy/typo matching | Python Levenshtein at application layer | `pg_trgm` % operator | DB-side with GIN index; Python-side requires loading all rows into memory first |
| Full-text tokenization and stemming | Custom tokenizer | `to_tsvector('english', ...)` | Postgres handles stemming (electricity = electric), stopword removal, and multi-language config |
| Multi-word phrase search | Custom AND logic | `plainto_tsquery()` | Automatically converts "electricity bill" into `electricity & bill` tsquery |
| Search indexing triggers | Celery task to recompute search_vector | PostgreSQL BEFORE INSERT/UPDATE trigger | Triggers are synchronous and in-transaction; Celery would create race conditions and add latency |

**Key insight:** PostgreSQL's FTS + pg_trgm stack handles every search requirement in this phase. Building any of these at the application layer would require fetching rows to Python, is harder to test, and defeats the purpose of indexing.

---

## Common Pitfalls

### Pitfall 1: ILIKE route still registered before /search
**What goes wrong:** FastAPI route `/documents/{document_id}` is a parameterized route. If the router evaluates `/{document_id}` before `/search`, a request to `/documents/search` matches `document_id="search"` and returns 422 or 404 instead of hitting the search endpoint.
**Why it happens:** FastAPI registers routes in declaration order; path parameters are greedy.
**How to avoid:** The current `documents.py` already declares `/search` before `/{document_id}` (line 129 vs 280). Maintain this order when adding new filter parameters to the search endpoint.
**Warning signs:** 422 Unprocessable Entity on search requests; `document_id` validation errors in logs.

### Pitfall 2: Alembic autogenerate triggers false tsvector index diffs
**What goes wrong:** After applying the migration, every subsequent `alembic revision --autogenerate` generates a migration that drops and recreates the GIN index — even with no schema changes.
**Why it happens:** Confirmed upstream bug in Alembic (issue #1390): Alembic cannot properly compare functional indexes using `to_tsvector()` and always marks them as changed.
**How to avoid:** Create the GIN index using `op.execute()` with raw DDL in the migration. Do NOT declare it in `Document.__table_args__` as a SQLAlchemy `Index(...)` object.
**Warning signs:** New auto-generated migration file that only drops and recreates `idx_documents_search_vector` with no other changes.

### Pitfall 3: search_vector not populated for existing documents
**What goes wrong:** The trigger fires on INSERT/UPDATE, but documents already in the database have `search_vector = NULL`. Searching returns zero results for all existing documents until they are re-processed.
**Why it happens:** Triggers don't backfill historical data.
**How to avoid:** Include a backfill UPDATE in the migration's `upgrade()` function that sets `search_vector` for all existing completed documents.
**Warning signs:** Search returns 0 results in dev immediately after migration despite documents existing.

### Pitfall 4: pg_trgm similarity threshold too high for short query terms
**What goes wrong:** Single-word short queries (e.g., "tax") return no results via trigram because the similarity score is below the default threshold (0.3). The trigram of "tax" vs "tax documents" may score below threshold.
**Why it happens:** pg_trgm similarity requires at least 3 characters in both strings and is sensitive to string length.
**How to avoid:** The OR-combine pattern (FTS `@@` OR trigram `%`) handles this: short exact terms hit via FTS even if trigram misses. For queries shorter than 3 characters, skip the trigram arm and use only FTS.
**Warning signs:** Short-query searches return empty results; longer misspelled queries ("electrcity") return results correctly.

### Pitfall 5: amount filter on JSONB field breaks for NULL or non-numeric values
**What goes wrong:** `Document.extracted_metadata["amount"].astext.cast(Float)` raises a DB error or silently filters out documents when `extracted_metadata` is NULL or the `amount` key is absent.
**Why it happens:** JSONB path access on a NULL column raises a PostgreSQL error; casting non-numeric strings to Float also fails.
**How to avoid:** Use `Document.extracted_metadata.isnot(None)` guard before applying the amount filter, and cast via `sa.func.nullif(...)` or filter with `COALESCE`. Alternatively, cast via SQLAlchemy's `try_cast` or apply a regex-validated amount input.
**Warning signs:** 500 errors on search when amount filter is applied; documents without amount metadata disappear from all search results.

---

## Code Examples

### FTS Match with ts_rank Ordering
```python
# Source: SQLAlchemy 2.0 PostgreSQL dialect docs (docs.sqlalchemy.org/en/20/dialects/postgresql.html)
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TSVECTOR

search_query = func.plainto_tsquery("english", user_input)
rank = func.ts_rank(Document.search_vector, search_query)

results = (
    db.query(Document)
    .filter(Document.search_vector.op("@@")(search_query))
    .order_by(rank.desc())
    .all()
)
```

### Trigram Similarity Operator
```python
# Source: PostgreSQL pg_trgm docs (postgresql.org/docs/current/pgtrgm.html)
# Requires pg_trgm extension and gin_trgm_ops GIN index on the column

results = (
    db.query(Document)
    .filter(Document.extracted_text.op("%")(user_input))
    .all()
)
# % operator returns true when similarity(extracted_text, user_input) > pg_trgm.similarity_threshold (default 0.3)
```

### Combined FTS + Fuzzy Search
```python
# OR-combine: FTS catches exact/stemmed matches; trigram catches typos
from sqlalchemy import or_, func

search_query = func.plainto_tsquery("english", user_input)
rank = func.ts_rank(Document.search_vector, search_query)

results = (
    db.query(Document)
    .filter(
        or_(
            Document.search_vector.op("@@")(search_query),
            Document.extracted_text.op("%")(user_input),
        )
    )
    .order_by(rank.desc())
    .all()
)
```

### JSONB Amount Filter (safe)
```python
# Guard against NULL metadata before applying cast
from sqlalchemy import Float

if amount_min is not None:
    query = query.filter(
        Document.extracted_metadata.isnot(None),
        Document.extracted_metadata["amount"].astext.cast(Float) >= amount_min,
    )
```

### Alembic Migration GIN Index (raw DDL pattern)
```python
# Source: Alembic issue #1390 workaround
# Use op.execute() to prevent autogenerate false-diff bug

def upgrade():
    op.execute("""
        CREATE INDEX idx_documents_search_vector
        ON documents USING GIN (search_vector)
    """)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ILIKE substring match | tsvector `@@` FTS match | This phase | Stemming, relevance ranking, index-backed |
| No typo tolerance | pg_trgm trigram similarity | This phase | "electrcity" returns electricity bills |
| Order by `created_at DESC` | Order by `ts_rank DESC` | This phase | Most relevant result first, not most recent |
| Category filter only | Category + date range + amount range | This phase | SRCH-02 satisfied |
| SQLAlchemy match() shorthand | Direct `@@` operator via `.op("@@")` | Ongoing | `match()` works but `.op("@@")` with explicit `plainto_tsquery` is clearer about query type used |

**Deprecated/outdated:**
- `to_tsquery()` with raw user input: Replaced by `plainto_tsquery()` (or `websearch_to_tsquery()`) for all user-provided text — `to_tsquery` requires pre-formatted query syntax that users cannot be expected to provide.

---

## Open Questions

1. **Should search also cover `original_filename` for typos?**
   - What we know: FTS already includes `original_filename` in the `search_vector` (it's part of the trigger concatenation). Trigram index only covers `extracted_text`.
   - What's unclear: Whether a separate GIN trigram index on `original_filename` would provide meaningful value.
   - Recommendation: Skip for now. Filename typos are less common than text typos. Can be added in v2 without schema changes.

2. **Language configuration for Indian financial documents**
   - What we know: `to_tsvector('english', ...)` is used. English stemming handles most words in Indian financial documents (they are predominantly English-language).
   - What's unclear: OCR output for scanned documents may contain noise tokens that English stemming handles poorly.
   - Recommendation: Use `'english'` config for Phase 4. The `'simple'` config (no stemming) is an alternative if stemming causes false negatives, but this is LOW confidence — defer validation to actual document testing.

3. **pg_trgm similarity threshold tuning**
   - What we know: Default threshold is 0.3. Lower = more fuzzy (more false positives), higher = stricter.
   - What's unclear: Whether 0.3 is the right threshold for 3-6 character document-specific terms (UPI, GST, PAN).
   - Recommendation: Start with default 0.3. The OR-combine pattern (FTS OR trigram) limits false positive exposure. Threshold can be tuned per-query with `SET pg_trgm.similarity_threshold = 0.25` if needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.3 |
| Config file | none — discovered via `pytest` in `backend/` |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-01 | FTS search returns ranked results matching document content | unit (mock DB) | `pytest tests/test_search.py::test_fts_returns_ranked_results -x` | Wave 0 |
| SRCH-01 | ts_rank ordering: most relevant document ranks first | unit (mock DB) | `pytest tests/test_search.py::test_fts_relevance_ranking -x` | Wave 0 |
| SRCH-02 | Category filter combined with text search narrows results | unit (mock DB) | `pytest tests/test_search.py::test_search_with_category_filter -x` | Wave 0 |
| SRCH-02 | Date range filter returns only documents within range | unit (mock DB) | `pytest tests/test_search.py::test_search_with_date_filter -x` | Wave 0 |
| SRCH-02 | Amount range filter uses JSONB metadata field safely | unit (mock DB) | `pytest tests/test_search.py::test_search_with_amount_filter -x` | Wave 0 |
| SRCH-03 | "electrcity" query returns electricity bill documents | integration (real PG) | `pytest tests/test_search.py::test_fuzzy_typo_matching -x` | Wave 0 |
| SRCH-04 | Search response time under 2 seconds | smoke | `pytest tests/test_search.py::test_search_performance -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_search.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_search.py` — covers all SRCH-01 through SRCH-04 test cases above
- [ ] Migration test: verify `search_vector` column exists and GIN index is created after `alembic upgrade head`
- [ ] Note: conftest.py exists but uses SQLite mock — FTS/trigram tests that exercise actual operators require a real PostgreSQL connection. Fuzzy matching tests (SRCH-03) and performance tests (SRCH-04) MUST use a test PostgreSQL instance, not SQLite.

---

## Sources

### Primary (HIGH confidence)
- [SQLAlchemy 2.0 PostgreSQL Dialect - Full Text Search](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) — TSVECTOR type, func.plainto_tsquery, match() operator, bool_op("@@"), ts_rank patterns
- [PostgreSQL 18 Docs - Text Search Indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html) — GIN vs GiST recommendation, index types for text search
- [PostgreSQL 18 Docs - Text Search Tables](https://www.postgresql.org/docs/current/textsearch-tables.html) — stored column vs functional index tradeoff
- [PostgreSQL 18 Docs - pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html) — trigram operators, GIN operator class, similarity threshold

### Secondary (MEDIUM confidence)
- [Alembic issue #1390 - tsvector index false diffs](https://github.com/sqlalchemy/alembic/issues/1390) — confirmed bug, `op.execute()` workaround validated by upstream discussion
- [PostgreSQL FTS performance benchmark 2025](https://blog.vectorchord.ai/postgresql-full-text-search-fast-when-done-right-debunking-the-slow-myth) — 41s unoptimized vs 0.88s with stored tsvector + GIN
- [pg_trgm fuzzy search - Neon Docs](https://neon.com/docs/extensions/pg_trgm) — operator class, GIN setup for gin_trgm_ops
- [FastAPI FTS pattern - Sling Academy](https://www.slingacademy.com/article/how-to-use-postgresql-full-text-search-in-fastapi-applications/) — FastAPI + SQLAlchemy + plainto_tsquery endpoint pattern

### Tertiary (LOW confidence)
- [Postgres FTS engine - Xata blog](https://xata.io/blog/postgres-full-text-search-engine) — advanced ranking and highlighting patterns (not yet needed in Phase 4)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are built into PostgreSQL or SQLAlchemy 2.0 dialect; verified against official docs
- Architecture: HIGH — stored tsvector + trigger + GIN pattern is well-documented and the Alembic workaround is verified via upstream issue
- Pitfalls: HIGH for items 1-4; MEDIUM for item 5 (JSONB cast behavior tested against docs but not against this codebase's specific Postgres version)
- Validation architecture: MEDIUM — test framework pattern established but test files need to be created in Wave 0; FTS/trigram unit tests require real Postgres (not SQLite conftest)

**Research date:** 2026-03-11
**Valid until:** 2026-09-11 (stable stack — Postgres FTS API has not changed in 10+ years; SQLAlchemy dialect stable since 2.0)
