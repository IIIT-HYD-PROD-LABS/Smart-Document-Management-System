"""Phase 13 unified_search_service unit tests — query construction.

Pure-Python tests for the query normalizer + early-return paths. End-to-end
ts_query execution is covered by the Phase 13 smoke script (which inserts
real rows + asserts ranked results)."""
from unittest.mock import MagicMock

from app.compliance.services.unified_search_service import (
    _normalize_query,
    search,
)


def test_normalize_strips_punctuation_and_joins_with_and():
    assert _normalize_query("DRC-01 GST 2026") == "drc & 01 & gst & 2026"


def test_normalize_returns_none_for_empty():
    assert _normalize_query("") is None
    assert _normalize_query("   ") is None
    assert _normalize_query("!!!") is None


def test_normalize_lowercases_tokens():
    assert _normalize_query("URGENT Notice") == "urgent & notice"


def test_normalize_handles_quotes_and_special_chars():
    """User input with quotes / SQL-injection-shaped content must be neutralized."""
    assert _normalize_query("'; DROP TABLE foo--") == "drop & table & foo"
    # Single quotes are escaped to nothing; remaining tokens still searchable.


def test_search_short_circuits_on_empty_query():
    """Empty / punctuation-only query returns [] without hitting the DB."""
    db = MagicMock()
    db.execute.side_effect = AssertionError("must not be called")
    assert search(db, query="", user_id=1) == []
    assert search(db, query="!!!", user_id=1) == []


def test_search_short_circuits_when_no_entity_types():
    """No entity types selected = no SQL parts to UNION = empty list."""
    db = MagicMock()
    db.execute.side_effect = AssertionError("must not be called")
    assert search(db, query="anything", user_id=1, entity_types=[]) == []


def test_search_calls_execute_with_normalized_tsquery():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    search(db, query="GST DRC-01", user_id=1, entity_types=["notice"])
    args, kwargs = db.execute.call_args
    # Bound parameter is the normalized form
    bind_params = args[1]
    assert bind_params["tsquery"] == "gst & drc & 01"
    assert bind_params["limit"] == 25
    assert bind_params["offset"] == 0


def test_search_caps_page_size_at_50():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    search(db, query="x", user_id=1, page_size=999)
    args, _ = db.execute.call_args
    assert args[1]["limit"] == 50


def test_search_offset_computed_from_page():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    search(db, query="x", user_id=1, page=3, page_size=10)
    args, _ = db.execute.call_args
    assert args[1]["offset"] == 20
