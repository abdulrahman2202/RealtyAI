"""Shared-source retrieval against isolated Chroma collections and actual CSV documents."""

from datetime import UTC, datetime

from backend import rag
from backend.data_access import DEFAULT_POLICY, SourcePolicy
from backend.indexing import IngestionApproval
from backend.models import ExtractedRecord


def _index(records, collection, profile, encoder, tmp_path, policy=DEFAULT_POLICY):
    return rag.index_records(records, collection=collection, dry_run=False, profile=profile, encoder=encoder,
        approval=IngestionApproval(str(collection.id), "pytest isolated collection"), policy=policy, lock_directory=tmp_path / "locks")


def test_actual_sources_share_one_collection_and_support_source_filters(actual_documents, collection, profile, fake_encoder, tmp_path):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    for source in ("darglobal", "wasalt"):
        rows = rag.get_all_records(collection=collection, sources=[source])
        assert rows and all(row["metadata"]["source"] == source for row in rows)
    combined = rag.search("Compare DarGlobal and Wasalt services", sources=["darglobal", "wasalt"],
        collection=collection, encoder=fake_encoder)
    assert {record["metadata"]["source"] for record in combined} == {"darglobal", "wasalt"}


def test_exact_property_name_is_not_overwhelmed_by_company_or_directory_content(actual_documents, collection, profile, fake_encoder, tmp_path):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    results = rag.search("What is The Astera handover date?", collection=collection, encoder=fake_encoder)
    assert results
    assert all(record["metadata"]["page_type"] == "individual_property" for record in results)
    assert all("/the-astera?" in record["metadata"]["url"] for record in results)
    assert any("December 2028" in record["body"] for record in results)
    assert all(record["metadata"]["title"] == "The Astera, Interiors by Aston Martin | Al Marjan Island RAK" for record in results)


def test_page_type_scopes_keep_directories_and_auctions_separate(actual_documents, collection, profile, fake_encoder, tmp_path):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    directories = rag.search("Wasalt properties for sale in Saudi Arabia", sources=["wasalt"], page_types=["project_directory"],
        collection=collection, encoder=fake_encoder)
    assert directories and all(row["metadata"]["page_type"] == "project_directory" for row in directories)
    auctions = rag.search("Wasalt auctions", page_types=["auction"], collection=collection, encoder=fake_encoder)
    assert auctions and all(row["metadata"]["page_type"] == "auction" for row in auctions)
    assert rag.search("Wasalt villa bedrooms", sources=["wasalt"], collection=collection, encoder=fake_encoder) == []


def test_property_id_filters_and_exact_size_identifiers(actual_documents, collection, profile, fake_encoder, tmp_path):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    record = next(item for item in rag.get_all_records(collection=collection) if "/the-astera?" in item["metadata"]["url"])
    results = rag.search("61 to 265 sqm", document_id=record["metadata"]["document_id"], collection=collection, encoder=fake_encoder)
    assert results and all(item["metadata"]["document_id"] == record["metadata"]["document_id"] for item in results)
    assert any("61 to 265 sqm" in item["body"] for item in results)


def test_longer_exact_entity_wins_over_a_nested_property_name(actual_documents, collection, profile, fake_encoder, tmp_path):
    synthetic = ExtractedRecord(source="darglobal", url="https://darglobal.example/one-of-one/top-of-the-astera",
        extracted_at=datetime(2026, 11, 19, tzinfo=UTC), data={"title": "Top of the Astera", "page_type": "individual_property",
            "content": "Distinct synthetic property evidence, bedrooms: 5.", "description": "", "data_origin": "synthetic"})
    policy = SourcePolicy(allow_synthetic=True)
    _index([*actual_documents, synthetic], collection, profile, fake_encoder, tmp_path, policy)
    results = rag.search("Tell me about Top of the Astera", collection=collection, encoder=fake_encoder, policy=policy)
    assert results and all(record["metadata"]["title"] == "Top of the Astera" for record in results)


def test_unrelated_query_is_rejected_with_no_keyword_or_vector_relevance(actual_documents, collection, profile, fake_encoder, tmp_path):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    assert rag.search("neutrino entanglement xyzzy", collection=collection, encoder=fake_encoder) == []


def test_empty_collection_and_blank_queries_never_load_or_ingest(collection, fake_encoder):
    assert rag.search("What is available?", collection=collection, encoder=fake_encoder) == []
    assert rag.search(" ", collection=collection, encoder=fake_encoder) == []
    assert rag.get_all_records(collection=collection) == []
    assert fake_encoder.calls == []


def test_real_cached_embeddings_retrieve_actual_property_evidence(actual_documents, collection, profile, real_encoder, tmp_path):
    _index(actual_documents, collection, profile, real_encoder, tmp_path)
    results = rag.search("beach residences with Aston Martin interiors", sources=["darglobal"],
        page_types=["individual_property"], collection=collection, encoder=real_encoder)
    assert results and "/the-astera?" in results[0]["metadata"]["url"]
    assert "semantic" in results[0]["retrieval_methods"]
    assert results[0]["distance"] is not None
    assert any("Aston Martin" in result["body"] for result in results)


def test_raw_chroma_distances_are_preserved(actual_documents, collection, profile, fake_encoder, tmp_path, monkeypatch):
    _index(actual_documents, collection, profile, fake_encoder, tmp_path)
    target = next(record for record in rag.get_all_records(collection=collection) if "/the-astera?" in record["metadata"]["url"])
    monkeypatch.setattr(collection, "query", lambda **_kwargs: {"ids": [[target["id"]]], "distances": [[1.2]]})
    results = rag.search("The Astera", collection=collection, encoder=fake_encoder)
    matched = next(result for result in results if result["id"] == target["id"])
    assert matched["distance"] == 1.2
