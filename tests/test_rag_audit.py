"""Current architecture safety contracts superseding the Phase 6.10 characterization tests."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend import chatbot, rag
from backend.document_preparation import prepare_documents
from backend.retrieval import tokens

ROOT = Path(__file__).resolve().parents[1]


def test_normal_chat_has_no_implicit_ingestion_path():
    tree = ast.parse((ROOT / "backend/chatbot.py").read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "index_records" not in called
    assert "init_from_processed_data" not in called
    assert "get_all_records" not in called


def test_blank_query_and_absent_db_do_not_open_a_persistent_client(monkeypatch):
    blocked = Mock(side_effect=AssertionError("No persistent database access"))
    monkeypatch.setattr(rag.chromadb, "PersistentClient", blocked)
    assert rag.search(" ") == []
    assert rag.search("source information") == []
    blocked.assert_not_called()


def test_legacy_clear_and_implicit_ingestion_are_disabled():
    with pytest.raises(PermissionError):
        rag.clear_collection()
    with pytest.raises(PermissionError):
        rag.init_from_processed_data()


def test_prepared_metadata_contains_full_title_page_kind_and_model_provenance(actual_documents, profile):
    chunks = prepare_documents(actual_documents, profile=profile)
    assert all(chunk.metadata["title"] and chunk.metadata["page_type"] for chunk in chunks)
    assert all(chunk.metadata["embedding_revision"] == profile.revision for chunk in chunks)
    assert all(chunk.metadata["source"] in {"darglobal", "wasalt"} for chunk in chunks)


def test_unicode_numeric_and_identifier_matching_preserve_exact_values():
    assert tokens("1,200,000 SAR") == tokens("١٬٢٠٠٬٠٠٠ SAR")
    assert "2028" in tokens("December 2028")
    assert "sqm" in tokens("220 m²")
    assert "location" in tokens("LocationAl Marjan Island")


def test_request_filters_are_forwarded_without_changing_credential_configuration(monkeypatch):
    search = Mock(return_value=[])
    monkeypatch.setattr(chatbot, "search", search)
    chatbot.chatbot("Wasalt information", sources=["wasalt"], page_types=["company"], document_id="target")
    search.assert_called_once_with("Wasalt information", k=8, sources=["wasalt"], page_types=["company"], document_id="target", property_name=None)
