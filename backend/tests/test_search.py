"""
Test scaffold for FTS and trigram search functionality (SRCH-01 through SRCH-04).

All tests are stubs marked to skip until plan 04-02 implements the search endpoint.

Note: FTS/trigram tests (test_fuzzy_typo_matching, test_search_performance) require
a real PostgreSQL instance -- they skip on SQLite conftest.
"""
import pytest


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_fts_returns_ranked_results():
    """SRCH-01: FTS match returns documents containing query term."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_fts_relevance_ranking():
    """SRCH-01: ts_rank orders most-relevant documents first."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_search_with_category_filter():
    """SRCH-02: category filter narrows FTS results to matching category."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_search_with_date_filter():
    """SRCH-02: date_from/date_to params filter results by created_at."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_search_with_amount_filter():
    """SRCH-02: amount_min/amount_max filters on extracted_metadata['amount']."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_fuzzy_typo_matching():
    """SRCH-03: 'electrcity' typo query returns electricity documents via trigram."""
    pass


@pytest.mark.skip(reason="stub -- implement in plan 04-02")
def test_search_performance():
    """SRCH-04: search returns in under 2 seconds with GIN index in place."""
    pass
