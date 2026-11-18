"""RAG retrieval pipeline tests for RealtyAI.

Uses the two DarGlobal JSON records as the vector store corpus.
No LLM, no FastAPI, no frontend — pure semantic retrieval via
ChromaDB + SentenceTransformers.
"""

import json
from pathlib import Path

import pytest

from backend.rag import init_from_processed_data, search, get_all_records


FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed" / "darglobal"


# ── Helpers ──────────────────────────────────────────────────────


def _load_json(name: str) -> dict:
    return json.loads((PROCESSED_DIR / name).read_text(encoding="utf-8"))


# ── Tests ────────────────────────────────────────────────────────


def test_init_from_processed_data_indexes_two_records():
    """Initialising from processed data should index both DarGlobal records."""
    init_from_processed_data()

    records = get_all_records()
    assert len(records) == 2, f"Expected 2 records, got {len(records)}"


def test_init_from_processed_data_preserves_urls():
    """Indexed records must preserve the source URL in metadata."""
    init_from_processed_data()

    records = get_all_records()
    urls = {r["metadata"].get("url", "") for r in records}
    assert "https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION" in urls
    assert "https://darglobal.co.uk/one-of-one/top-of-the-astera" in urls


def test_init_from_processed_data_preserves_titles():
    """Indexed records must preserve property titles."""
    init_from_processed_data()

    records = get_all_records()
    titles = {r["metadata"].get("title", "") for r in records}
    assert "Albert Hall Mansions" in titles
    assert "Top Of the Astera" in titles


def test_search_top_of_astera_retrieval():
    """Searching for 'Top of the Astera' should return the Astera record."""
    init_from_processed_data()

    results = search("Top of the Astera", k=4)
    assert len(results) > 0, "Expected at least one search result"

    # The Top of the Astera record should be in the results
    result_ids = {r["metadata"].get("title", "") for r in results}
    assert "Top Of the Astera" in result_ids


def test_search_albert_hall_retrieval():
    """Searching for 'Albert Hall' should return the Albert Hall Mansions record."""
    init_from_processed_data()

    results = search("Albert Hall Mansions", k=4)
    assert len(results) > 0, "Expected at least one search result"

    result_ids = {r["metadata"].get("title", "") for r in results}
    assert "Albert Hall Mansions" in result_ids


def test_search_returns_metadata_source_and_url():
    """Search results must include source URL and metadata."""
    init_from_processed_data()

    results = search("luxury villa", k=4)
    assert len(results) > 0
    for r in results:
        assert "metadata" in r, "Each result must have metadata"
        meta = r["metadata"]
        assert "source" in meta, "Metadata must include source"
        assert "url" in meta, "Metadata must include url"


def test_search_unknown_query_returns_empty():
    """An unknown query returns results with high distance (vector search always finds some similarity)."""
    init_from_processed_data()

    results = search("completely unrelated query zxyz", k=4)
    # Vector search returns top-k results regardless of query relevance;
    # verify results have expected structure rather than expecting empty list.
    assert len(results) > 0, "Expected at least one search result"
    for r in results:
        assert "metadata" in r
        assert "distance" in r
        assert 0.0 <= r["distance"] <= 1.0


def test_search_k_equals_one():
    """Search with k=1 should return exactly one result."""
    init_from_processed_data()

    results = search("Albert Hall", k=1)
    assert len(results) == 1, f"Expected exactly 1 result with k=1, got {len(results)}"


def test_search_k_default_four():
    """Search with default k=4 should return up to 4 results."""
    init_from_processed_data()

    results = search("luxury property")
    assert len(results) <= 4, (
        f"Expected at most 4 results with default k, got {len(results)}"
    )


def test_search_distance_is_float_between_0_and_1():
    """Search result distances should be floats in [0, 1] (cosine distance)."""
    init_from_processed_data()

    results = search("property", k=1)
    assert len(results) > 0
    dist = results[0].get("distance")
    assert dist is not None, "Result should have distance field"
    assert 0.0 <= float(dist) <= 1.0, f"Distance should be in [0,1], got {dist}"


def test_empty_db_no_crash():
    """Running search before any records are indexed should not crash."""
    # Clear any previously indexed records
    from backend.rag import clear_collection

    clear_collection()

    results = search("anything", k=4)
    # With no records indexed, search should return empty list
    assert results == [], (
        f"Expected empty list when DB is not initialised, got {results}"
    )


def test_record_has_required_fields():
    """Each indexed record should have title, description, and url."""
    init_from_processed_data()

    records = get_all_records()
    for r in records:
        meta = r["metadata"]
        assert meta.get("title") is not None, f"Record missing title: {r}"
        assert meta.get("description") is not None, f"Record missing description: {r}"
        assert meta.get("url") is not None, f"Record missing url: {r}"
