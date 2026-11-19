"""Shared fixtures: actual authorized CSVs, local models, and isolated in-memory databases."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import chromadb
import numpy as np
import pytest

from backend import llm, rag
from backend.csv_importer import import_directory
from backend.embedding import cached_encoder, cached_profile
from backend.retrieval import invalidate_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeEncoder:
    def __init__(self, dimension=384):
        self.dimension = dimension
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        vector = np.zeros(self.dimension, dtype=np.float32)
        vector[0 if isinstance(texts, str) else 1] = 1.0
        return vector if isinstance(texts, str) else np.tile(vector, (len(texts), 1))


@pytest.fixture(autouse=True)
def protect_persistent_data(monkeypatch, tmp_path):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Persistent ChromaDB and real LLM requests are forbidden in tests.")
    monkeypatch.setattr(chromadb, "PersistentClient", blocked)
    monkeypatch.setattr(llm, "get_client", blocked)
    monkeypatch.setenv("REALTYAI_VECTOR_DB_DIR", str(tmp_path / "absent_vector_db"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr(rag, "_collection", None)
    monkeypatch.setattr(rag, "_chroma_client", None)
    monkeypatch.setattr(rag, "_encoder", None)
    monkeypatch.setattr(rag, "_client_target", None)
    invalidate_catalog()


@pytest.fixture(scope="session")
def profile():
    return cached_profile()


@pytest.fixture(scope="session")
def real_encoder():
    return cached_encoder()


@pytest.fixture
def fake_encoder(profile):
    return FakeEncoder(profile.dimension)


@pytest.fixture(scope="session")
def actual_imports():
    return {source: import_directory(PROJECT_ROOT / "data" / "raw" / source, source) for source in ("darglobal", "wasalt")}


@pytest.fixture(scope="session")
def actual_documents(actual_imports):
    return [record for result in actual_imports.values() for record in result.records]


@pytest.fixture
def collection_factory():
    client = chromadb.EphemeralClient(settings=chromadb.Settings(anonymized_telemetry=False))
    def create(metric="cosine"):
        return client.create_collection("phase611_" + uuid4().hex, embedding_function=None, configuration={"hnsw": {"space": metric}})
    return create


@pytest.fixture
def collection(collection_factory):
    return collection_factory()
