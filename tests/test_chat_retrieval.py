"""Actual reviewed-document API coverage, configuration failures, and guarded collection setup."""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import chromadb
import pytest
from fastapi.testclient import TestClient

from backend import chatbot, rag
from backend.collection_setup import (
    execute_approved_plan,
    proposed_collection,
    reviewed_chunks,
)
from backend.embedding import cached_encoder
from backend.indexing import IngestionApproval, index_chunks
from backend.main import app

CASES = [
    ("What information is available about THE ALBERT HALL MANSION?", "London", "darglobal", "individual_property"),
    ("Where is Albert Hall Mansions located?", "Royal Albert Hall", "darglobal", "individual_property"),
    ("Tell me about The Astera project.", "Aston Martin", "darglobal", "individual_property"),
    ("What bedroom configurations are available at The Astera?", "3", "darglobal", "individual_property"),
    ("What is the scheduled handover date for The Astera?", "December 2028", "darglobal", "individual_property"),
    ("What services does Wasalt provide?", "Wasalt", "wasalt", "company"),
    ("What types of properties can users find on Wasalt?", "villas", "wasalt", None),
    ("Does Wasalt provide property auction services?", "auction", "wasalt", "auction"),
    ("What information is available about properties for sale and rent in Saudi Arabia?", "Saudi", None, None),
    ("Compare the real estate services described by DarGlobal and Wasalt.", "DarGlobal", None, "company"),
]


@pytest.fixture(scope="session")
def reviewed_collection(tmp_path_factory):
    chunks, profile, _ = reviewed_chunks()
    client = chromadb.EphemeralClient(settings=chromadb.Settings(anonymized_telemetry=False))
    collection = client.create_collection("api_actual_" + uuid4().hex, embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}})
    encoder = cached_encoder()
    index_chunks(chunks, collection=collection, profile=profile, encoder=encoder, dry_run=False,
        approval=IngestionApproval(str(collection.id), "Isolated API tests"),
        lock_directory=tmp_path_factory.mktemp("api_locks"))
    return collection, encoder, chunks


@pytest.mark.parametrize("question,evidence,source,page_type", CASES)
def test_actual_questions_through_frontend_api_endpoint(reviewed_collection, monkeypatch,
    question, evidence, source, page_type):
    collection, encoder, chunks = reviewed_collection
    monkeypatch.setattr(rag, "_collection", collection)
    monkeypatch.setattr(rag, "_encoder", encoder)
    captured = {}
    original = chatbot.chatbot

    def handler(*args, **kwargs):
        captured.update(original(*args, **kwargs))
        return captured

    generator = Mock(return_value="Available source information: " + evidence)
    monkeypatch.setattr(chatbot, "generate", generator)
    monkeypatch.setattr("backend.api.routes.chatbot", handler)
    response = TestClient(app).post("/api/chat", json={"question": question})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] and result["sources"]
    assert evidence.casefold() in captured["context"].casefold()
    assert evidence.casefold() in result["answer"].casefold()
    assert captured["retrieved_count"] >= len(captured["records"]) > 0
    assert captured["context_tokens"] <= 1500 and captured["context_bytes"] <= 6000
    stored = {chunk.id: chunk for chunk in chunks}
    for record in captured["records"]:
        assert stored[record["id"]].body == record["body"]
        assert record["body"] in captured["context"]
        if source:
            assert record["metadata"]["source"] == source
        if page_type:
            assert record["metadata"]["page_type"] == page_type
    if "Compare" in question:
        assert {item["source"] for item in result["sources"]} == {"darglobal", "wasalt"}
    assert {item["url"] for item in result["sources"]} == {record["metadata"]["url"] for record in captured["records"]}
    if generator.called:
        assert captured["context"] in generator.call_args.args[0][1]["content"]


def test_all_prepared_chunks_and_source_filters_are_discoverable(reviewed_collection):
    collection, _, chunks = reviewed_collection
    rows = rag.get_all_records(collection=collection)
    assert len(rows) == 84
    assert {row["id"] for row in rows} == {chunk.id for chunk in chunks}
    for source, count in (("darglobal", 46), ("wasalt", 38)):
        filtered = rag.get_all_records(collection=collection, sources=[source])
        assert len(filtered) == count
        assert all(row["metadata"]["source"] == source for row in filtered)


def test_generated_list_and_citation_numbers_do_not_erase_useful_answer(reviewed_collection, monkeypatch):
    collection, encoder, _ = reviewed_collection
    monkeypatch.setattr(rag, "_collection", collection)
    monkeypatch.setattr(rag, "_encoder", encoder)
    answer = "1. Albert Hall Mansions is in London. [1]\n2. It overlooks the Royal Albert Hall. [2]"
    monkeypatch.setattr(chatbot, "generate", Mock(return_value=answer))
    result = chatbot.chatbot(CASES[0][0])
    assert "It overlooks the Royal Albert Hall." in result["answer"]
    assert "[1]" not in result["answer"] and result["sources"][0]["url"] in result["answer"]


def test_unicode_and_document_identity_citations_are_not_numeric_facts(reviewed_collection, monkeypatch):
    collection, encoder, chunks = reviewed_collection
    monkeypatch.setattr(rag, "_collection", collection)
    monkeypatch.setattr(rag, "_encoder", encoder)
    identity = next(chunk.metadata["document_id"] for chunk in chunks if chunk.metadata["title"] == "THE ALBERT HALL MANSION")
    answer = f"Albert Hall Mansions is in London.【{identity} - THE ALBERT HALL MANSION】 It overlooks Royal Albert Hall.【1】"
    monkeypatch.setattr(chatbot, "generate", Mock(return_value=answer))
    result = chatbot.chatbot(CASES[0][0])
    assert "It overlooks Royal Albert Hall." in result["answer"]
    assert identity not in result["answer"] and "【1】" not in result["answer"]


def test_configured_missing_collection_is_failed_retrieval(monkeypatch):
    monkeypatch.setenv("REALTYAI_COLLECTION_NAME", "explicitly_missing_collection")
    with pytest.raises(rag.RetrievalError):
        rag.search("Wasalt services")
    response = TestClient(app).post("/api/chat", json={"question": "Wasalt services"})
    assert response.status_code == 503
    assert "Source retrieval" in response.json()["detail"]


def test_collection_proposal_does_not_access_persistent_clients():
    plan = proposed_collection()
    assert plan["chunk_count"] == 84 and plan["distance_metric"] == "cosine"
    assert plan["state"] == "awaiting_persistent_ingestion_approval"
    assert plan["source_counts"] == {"darglobal": 46, "wasalt": 38}
    with pytest.raises(PermissionError):
        execute_approved_plan(plan, approval_reference="")
    with pytest.raises(ValueError):
        execute_approved_plan({**plan, "distance_metric": "l2"}, approval_reference="test")


def test_separate_collection_creation_and_retry_remain_protected(profile, fake_encoder, tmp_path):
    plan = proposed_collection(collection_name="approved_" + uuid4().hex)
    client = chromadb.EphemeralClient(settings=chromadb.Settings(anonymized_telemetry=False))
    with pytest.raises(PermissionError):
        execute_approved_plan(plan, approval_reference="test", client=client,
            receipt_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    result = execute_approved_plan(plan, approval_reference="test isolated collection", client=client,
        create_collection=True, encoder=fake_encoder, receipt_path=tmp_path / "receipt.json",
        lock_directory=tmp_path / "locks")
    assert result["added_count"] == 84
    with pytest.raises(PermissionError):
        execute_approved_plan(plan, approval_reference="test", client=client, create_collection=True,
            collection_id="wrong-uuid", receipt_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    retry = execute_approved_plan(plan, approval_reference="test isolated retry", client=client,
        collection_id=result["collection_id"], encoder=fake_encoder,
        receipt_path=tmp_path / "receipt.json", lock_directory=tmp_path / "locks")
    assert retry["added_count"] == 0 and retry["identical_count"] == 84
    assert client.get_collection(plan["collection_name"]).count() == 84


def test_separate_workflow_refuses_legacy_database():
    from backend.data_access import PROJECT_ROOT
    with pytest.raises(PermissionError):
        proposed_collection(database_dir=PROJECT_ROOT / "data" / "vector_db")
