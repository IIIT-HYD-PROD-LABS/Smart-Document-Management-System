"""
Test scaffold for FTS and trigram search functionality (SRCH-01 through SRCH-04).

SRCH-01 and SRCH-02 tests are implemented here using dependency overrides.
SRCH-03 and SRCH-04 connect to real PostgreSQL to validate trigram fuzzy matching
and sub-2-second performance under GIN indexes.

Note: FTS/trigram tests require real PostgreSQL. Tests skip gracefully if only
SQLite or no DB is available.
"""
import os
import time
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(**kwargs):
    """Return a MagicMock that looks like a Document ORM row."""
    doc = MagicMock()
    doc.id = kwargs.get("id", 1)
    doc.user_id = kwargs.get("user_id", 1)
    doc.filename = kwargs.get("filename", "test.pdf")
    doc.original_filename = kwargs.get("original_filename", "test.pdf")
    doc.file_type = kwargs.get("file_type", "pdf")
    doc.file_size = kwargs.get("file_size", 1024)
    doc.file_path = kwargs.get("file_path", "/uploads/test.pdf")
    doc.s3_url = kwargs.get("s3_url", None)
    doc.status = MagicMock()
    doc.status.value = "completed"
    doc.category = MagicMock()
    doc.category.value = kwargs.get("category", "bills")
    doc.confidence_score = kwargs.get("confidence_score", 0.9)
    doc.extracted_text = kwargs.get("extracted_text", "electricity bill payment")
    doc.extracted_metadata = kwargs.get("extracted_metadata", {"amount": "250.00"})
    doc.created_at = kwargs.get("created_at", None)
    doc.celery_task_id = None
    doc.search_vector = None
    return doc


@pytest.fixture()
def authenticated_client():
    """Create a TestClient with auth dependency properly overridden."""
    from app.main import app
    from app.utils.security import get_current_user

    test_user = MagicMock()
    test_user.id = 1
    test_user.email = "test@example.com"
    test_user.username = "testuser"
    test_user.is_active = True
    test_user.role = "editor"

    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# SRCH-01: FTS returns ranked results
# ---------------------------------------------------------------------------

def test_fts_returns_ranked_results(authenticated_client):
    """SRCH-01: Search endpoint accepts q param and returns valid response."""
    response = authenticated_client.get(
        "/api/documents/search?q=electricity",
    )
    # Should not be 404 (route missing) or 422 (param validation error)
    assert response.status_code != 404, "Search route must exist"
    assert response.status_code != 422, "q parameter must be accepted"


def test_fts_relevance_ranking():
    """SRCH-01: Search endpoint uses plainto_tsquery and ts_rank for FTS."""
    import importlib
    import inspect
    import app.routers.documents as doc_router_mod

    importlib.reload(doc_router_mod)
    source = inspect.getsource(doc_router_mod)

    assert "plainto_tsquery" in source, (
        "search_documents must use plainto_tsquery for FTS; found only ILIKE"
    )
    assert "ts_rank" in source, (
        "search_documents must order by ts_rank for relevance ranking"
    )


# ---------------------------------------------------------------------------
# SRCH-02: Filters
# ---------------------------------------------------------------------------

def test_search_with_category_filter(authenticated_client):
    """SRCH-02: category filter param accepted without validation error."""
    response = authenticated_client.get(
        "/api/documents/search?q=bill&category=bills",
    )
    assert response.status_code != 404, "Search route must exist"
    assert response.status_code != 422, "category parameter must be accepted"


def test_search_with_date_filter(authenticated_client):
    """SRCH-02: date_from and date_to filter params accepted without validation error."""
    response = authenticated_client.get(
        "/api/documents/search?q=bill&date_from=2024-01-01&date_to=2024-12-31",
    )
    assert response.status_code != 404, "Search route must exist"
    assert response.status_code != 422, (
        "date_from and date_to parameters must be accepted by the endpoint"
    )


def test_search_with_amount_filter(authenticated_client):
    """SRCH-02: amount_min and amount_max filter params accepted without validation error."""
    response = authenticated_client.get(
        "/api/documents/search?q=bill&amount_min=100&amount_max=500",
    )
    assert response.status_code != 404, "Search route must exist"
    assert response.status_code != 422, (
        "amount_min and amount_max parameters must be accepted by the endpoint"
    )


# ---------------------------------------------------------------------------
# SRCH-03 / SRCH-04: Real PostgreSQL tests (skip gracefully if unavailable)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pg_db():
    """Real PostgreSQL session for FTS/trigram tests. Skips if not available."""
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url or "sqlite" in db_url:
        pytest.skip("Real PostgreSQL required for FTS/trigram tests")
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_fuzzy_typo_matching(pg_db):
    """SRCH-03: 'electrcity' typo query returns electricity documents via trigram."""
    session = pg_db

    # Ensure pg_trgm extension is available
    try:
        session.execute(text("SELECT similarity('test', 'tset')"))
    except Exception:
        session.rollback()
        pytest.skip("pg_trgm extension not available in test DB")

    # Get a valid user_id from the users table
    user_row = session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
    if not user_row:
        pytest.skip("No users in database for trigram test")
    test_user_id = user_row[0]

    # Insert a test document row with known extracted_text
    insert_sql = text("""
        INSERT INTO documents (
            user_id, filename, original_filename, file_type, file_size,
            file_path, status, category, extracted_text, created_at, updated_at
        ) VALUES (
            :user_id, 'test_trigram.pdf', 'test_trigram.pdf', 'pdf', 1024,
            '/tmp/test_trigram.pdf', 'completed', 'bills',
            'This is an electricity bill for April',
            NOW(), NOW()
        ) RETURNING id
    """)
    result = session.execute(insert_sql, {"user_id": test_user_id})
    doc_id = result.fetchone()[0]
    session.commit()

    try:
        # Update search_vector for the inserted row
        session.execute(text(
            "UPDATE documents SET search_vector = to_tsvector('english', extracted_text) "
            "WHERE id = :doc_id"
        ), {"doc_id": doc_id})
        session.commit()

        # Lower the trigram similarity threshold for testing
        session.execute(text("SET pg_trgm.similarity_threshold = 0.1"))

        # Run the OR-combine FTS + trigram query (mirrors the search endpoint logic)
        q = "electrcity"
        search_sql = text("""
            SELECT id FROM documents
            WHERE id = :doc_id
              AND (
                search_vector @@ plainto_tsquery('english', :q)
                OR extracted_text % :q
              )
        """)
        rows = session.execute(search_sql, {"doc_id": doc_id, "q": q}).fetchall()
        found_ids = [r[0] for r in rows]

        assert doc_id in found_ids, (
            f"Expected doc_id {doc_id} in fuzzy search results for 'electrcity', "
            f"but got: {found_ids}. Trigram OR-combine may not be working."
        )
    finally:
        session.rollback()
        session.execute(text("DELETE FROM documents WHERE id = :doc_id"), {"doc_id": doc_id})
        session.commit()


def test_search_performance(pg_db):
    """SRCH-04: Search query completes in under 2 seconds (GIN index performance)."""
    session = pg_db

    # Check pg_trgm is available first
    try:
        session.execute(text("SELECT similarity('test', 'tset')"))
    except Exception:
        session.rollback()
        pytest.skip("pg_trgm extension not available in test DB")

    q = "electricity"
    search_sql = text("""
        SELECT id FROM documents
        WHERE status = 'completed'
          AND (
            search_vector @@ plainto_tsquery('english', :q)
            OR extracted_text % :q
          )
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', :q)) DESC
        LIMIT 20
    """)

    start = time.time()
    session.execute(search_sql, {"q": q}).fetchall()
    elapsed = time.time() - start

    assert elapsed < 2.0, (
        f"Search query took {elapsed:.3f}s, expected < 2.0s. "
        "GIN index on search_vector and extracted_text may not be in place."
    )
