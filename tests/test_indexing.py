"""Append-only indexing, provenance conflicts, explicit approval, and retry safety."""

import json

import pytest

from backend.document_preparation import prepare_documents
from backend.indexing import (
    IndexingConflict,
    IngestionApproval,
    index_chunks,
    preflight_chunks,
)
from backend.rag import index_records


def _approval(collection, profile, *, legacy=False):
    provenance = {**profile.provenance(), "evidence": "This isolated test wrote the legacy vector using the same test encoder."} if legacy else None
    return IngestionApproval(str(collection.id), "pytest isolated in-memory collection", provenance)


def test_unapproved_indexing_is_pure_and_does_not_open_the_persistent_db(actual_documents, profile):
    manifest = index_records(actual_documents, profile=profile)
    assert manifest["state"] == "review_only"
    assert manifest["persistent_collection_accessed"] is False
    assert manifest["source_counts"]["darglobal"] > 0 and manifest["source_counts"]["wasalt"] > 0
    assert manifest["added_count"] == 0
    assert manifest["pending_count"] is None


def test_execution_requires_approval_for_the_exact_collection(actual_documents, collection, profile, fake_encoder, tmp_path):
    with pytest.raises(PermissionError):
        index_records(actual_documents, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder)
    with pytest.raises(PermissionError):
        index_records(actual_documents, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
            approval=IngestionApproval("wrong-uuid", "test approval"), lock_directory=tmp_path / "locks")
    assert collection.count() == 0
    assert fake_encoder.calls == []


def test_both_actual_sources_append_and_identical_retry_adds_nothing(actual_documents, collection, profile, fake_encoder, tmp_path):
    approval = _approval(collection, profile)
    first = index_records(actual_documents, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
        approval=approval, manifest_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    count = collection.count()
    assert first["state"] == "complete"
    assert first["added_count"] == count > 0
    assert {meta["source"] for meta in collection.get(include=["metadatas"])["metadatas"]} == {"darglobal", "wasalt"}
    before_calls = len(fake_encoder.calls)
    second = index_records(actual_documents, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
        approval=approval, manifest_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    assert second["added_count"] == 0
    assert second["identical_count"] == count
    assert collection.count() == count
    assert len(fake_encoder.calls) == before_calls
    assert json.loads((tmp_path / "receipt.json").read_text())["state"] == "complete"


def test_legacy_records_and_metric_are_preserved_and_provenance_is_required(actual_imports, collection, profile, fake_encoder, tmp_path):
    record = next(item for item in actual_imports["darglobal"].records if "/the-astera?" in item.url)
    legacy_metadata = {"source": "darglobal.co.uk", "url": record.url.split("?")[0], "title": "Historical Astera title", "description": "Historical summary"}
    collection.add(ids=["legacy-id"], documents=["Historical summary"], metadatas=[legacy_metadata],
        embeddings=fake_encoder.encode(["Historical summary"]))
    original = collection.get(ids=["legacy-id"], include=["documents", "metadatas"])
    configuration = collection.configuration
    with pytest.raises(IndexingConflict) as error:
        index_records([record], collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
            approval=_approval(collection, profile), lock_directory=tmp_path / "locks")
    assert any("provenance" in conflict["reason"] for conflict in error.value.manifest["conflicts"])
    assert collection.count() == 1
    result = index_records([record], collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
        approval=_approval(collection, profile, legacy=True), lock_directory=tmp_path / "locks")
    assert result["added_count"] > 0
    assert collection.get(ids=["legacy-id"], include=["documents", "metadatas"]) == original
    assert collection.configuration == configuration


def test_changed_document_is_a_conflict_and_is_not_silently_appended(actual_imports, collection, profile, fake_encoder, tmp_path):
    record = actual_imports["darglobal"].records[-1]
    approval = _approval(collection, profile)
    index_records([record], collection=collection, dry_run=False, profile=profile, encoder=fake_encoder, approval=approval, lock_directory=tmp_path / "locks")
    before = collection.count()
    changed = record.model_copy(update={"data": {**record.data, "content": record.data["content"] + "\nChanged source text."}})
    with pytest.raises(IndexingConflict):
        index_records([changed], collection=collection, dry_run=False, profile=profile, encoder=fake_encoder, approval=approval, lock_directory=tmp_path / "locks")
    assert collection.count() == before


def test_corrupted_existing_chunk_stops_before_any_new_write(actual_imports, collection, profile, fake_encoder, tmp_path):
    chunks = prepare_documents([actual_imports["darglobal"].records[-1]], profile=profile)
    chunk = chunks[0]
    collection.add(ids=[chunk.id], documents=["Conflicting stored text"], metadatas=[chunk.metadata], embeddings=fake_encoder.encode(["Conflicting stored text"]))
    manifest = preflight_chunks(chunks, collection=collection, profile=profile)
    assert manifest["state"] == "conflict"
    with pytest.raises(IndexingConflict):
        index_chunks(chunks, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
            approval=_approval(collection, profile), lock_directory=tmp_path / "locks")
    assert collection.count() == 1


def test_partial_failure_can_resume_without_duplicate_chunks(actual_imports, collection, profile, fake_encoder, tmp_path):
    record = next(item for item in actual_imports["darglobal"].records if "/the-astera?" in item.url)
    chunks = prepare_documents([record], profile=profile)
    assert len(chunks) > 2

    class InterruptedCollection:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.calls = 0

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def add(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("Simulated interruption")
            return self.wrapped.add(**kwargs)

    interrupted = InterruptedCollection(collection)
    with pytest.raises(RuntimeError, match="Simulated"):
        index_chunks(chunks, collection=interrupted, dry_run=False, profile=profile, encoder=fake_encoder,
            approval=_approval(collection, profile), batch_size=1, manifest_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    assert collection.count() == 1
    assert json.loads((tmp_path / "receipt.json").read_text())["state"] == "interrupted"
    result = index_chunks(chunks, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
        approval=_approval(collection, profile), batch_size=1, lock_directory=tmp_path / "locks")
    assert result["identical_count"] == 1
    assert result["added_count"] == len(chunks) - 1
    assert collection.count() == len(chunks)


def test_duplicate_input_chunks_are_counted_once(actual_imports, collection, profile, fake_encoder, tmp_path):
    chunks = prepare_documents([actual_imports["darglobal"].records[0]], profile=profile)
    manifest = index_chunks(chunks + chunks, collection=collection, dry_run=False, profile=profile, encoder=fake_encoder,
        approval=_approval(collection, profile), lock_directory=tmp_path / "locks")
    assert manifest["duplicate_input_chunks"] == len(chunks)
    assert collection.count() == len(chunks)


def test_encoder_dimension_mismatch_cannot_write_vectors(actual_imports, collection, profile, tmp_path):
    class BadEncoder:
        def encode(self, texts, **_kwargs):
            return [[1.0, 0.0] for _ in texts]
    with pytest.raises(ValueError, match="dimension"):
        index_records([actual_imports["darglobal"].records[0]], collection=collection, dry_run=False,
            profile=profile, encoder=BadEncoder(), approval=_approval(collection, profile), lock_directory=tmp_path / "locks")
    assert collection.count() == 0
