"""Readiness for an existing, approved collection and bundled offline model."""

from __future__ import annotations

import os
from collections import Counter

from backend.embedding import cached_profile
from backend.rag import RetrievalError, _resolve_collection


def readiness() -> dict:
    collection = _resolve_collection()
    if collection is None:
        raise RetrievalError("The approved collection is not available.")
    expected_uuid = os.getenv("REALTYAI_COLLECTION_ID")
    if expected_uuid and str(collection.id) != expected_uuid:
        raise RetrievalError("The configured collection UUID does not match the approved target.")
    if collection.count() != 84:
        raise RetrievalError("The approved 84 chunks are not available.")
    if (collection.configuration.get("hnsw") or {}).get("space") != "cosine":
        raise RetrievalError("The approved cosine collection configuration is not available.")
    rows = collection.get(include=["metadatas"])
    metadata = rows["metadatas"]
    if Counter(item["source"] for item in metadata) != {"darglobal": 46, "wasalt": 38}:
        raise RetrievalError("The approved source counts are not available.")
    if len({item["document_id"] for item in metadata}) != 12:
        raise RetrievalError("The approved source documents are not available.")
    profile = cached_profile()
    if profile.revision != "1110a243fdf4706b3f48f1d95db1a4f5529b4d41" or profile.dimension != 384:
        raise RetrievalError("The approved offline embedding model is not available.")
    required = ["model.safetensors", "config.json", "sentence_bert_config.json", "tokenizer.json", "1_Pooling/config.json"]
    if any(not (profile.snapshot / filename).is_file() for filename in required):
        raise RetrievalError("The offline model cache is incomplete.")
    return {"status": "ready", "service": "RealtyAI", "collection": collection.name,
        "collection_id": str(collection.id), "chunks": 84}
