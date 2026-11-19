"""Reusable multi-source RAG API; normal reads never create or ingest a collection."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.errors import ChromaError, NotFoundError

from backend.data_access import (
    DEFAULT_POLICY,
    PAGE_TYPES,
    SourcePolicy,
    normalize_source,
)
from backend.document_preparation import prepare_documents
from backend.embedding import EmbeddingProfile, cached_profile
from backend.indexing import IngestionApproval, index_chunks
from backend.models import ExtractedRecord
from backend.retrieval import catalog, hybrid_search, invalidate_catalog

COLLECTION_NAME = "realtyai_properties"
_chroma_client = None
_collection = None
_encoder = None
_client_target = None


class RetrievalError(RuntimeError):
    """Search/configuration failed; this is distinct from no matching source evidence."""


def _get_client():
    """Open only an existing collection; never create directories, collections, or vectors."""
    global _chroma_client, _collection, _client_target
    name = os.getenv("REALTYAI_COLLECTION_NAME", COLLECTION_NAME)
    directory = Path(os.getenv("REALTYAI_VECTOR_DB_DIR") or Path(__file__).resolve().parents[1] / "data" / "vector_db").resolve()
    target = (str(directory), name)
    if _client_target is not None and _client_target != target:
        _chroma_client = _collection = None
        invalidate_catalog()
    _client_target = target
    if _collection is not None:
        return _chroma_client
    if not (directory / "chroma.sqlite3").is_file():
        if name != COLLECTION_NAME:
            raise RetrievalError("The configured source collection has not been indexed.")
        return None
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(directory), settings=chromadb.Settings(anonymized_telemetry=False))
    try:
        _collection = _chroma_client.get_collection(name, embedding_function=None)
    except NotFoundError as error:
        _collection = None
        if name != COLLECTION_NAME:
            raise RetrievalError("The configured source collection is missing.") from error
    if _collection is not None and name != COLLECTION_NAME:
        metadata = _collection.metadata or {}
        if any(metadata.get(key) != value for key, value in cached_profile().provenance().items()):
            _collection = None
            raise RetrievalError("The configured collection has incompatible embedding provenance.")
    return _chroma_client


def _resolve_collection(collection=None):
    if collection is not None:
        return collection
    _get_client()
    return _collection


def index_records(
    records: list[ExtractedRecord | dict], *, collection=None, dry_run: bool = True,
    approval: IngestionApproval | None = None, profile: EmbeddingProfile | None = None,
    encoder=None, policy: SourcePolicy = DEFAULT_POLICY, manifest_path: Path | None = None,
    batch_size: int = 64, lock_directory: Path | None = None,
) -> dict:
    """Prepare nested records and return a review manifest unless execution is explicitly approved."""
    chunks = prepare_documents(records, profile=profile, policy=policy)
    manifest = index_chunks(chunks, collection=collection, dry_run=dry_run, approval=approval,
        profile=profile, encoder=encoder, policy=policy, manifest_path=manifest_path,
        batch_size=batch_size, lock_directory=lock_directory)
    if collection is not None and not dry_run:
        invalidate_catalog(str(collection.id))
    return manifest


def search(
    query: str, k: int = 4, *, source: str | None = None, sources: list[str] | None = None,
    page_types: list[str] | None = None, property_name: str | None = None, document_id: str | None = None,
    collection=None, encoder=None, policy: SourcePolicy = DEFAULT_POLICY, max_distance: float | None = None,
) -> list[dict]:
    """Hybrid retrieval across both sources, retaining original Chroma distances."""
    if not query or not query.strip() or sources == []:
        return []
    if not 1 <= k <= 50:
        raise ValueError("Retrieval k must be between 1 and 50.")
    if source is not None:
        if sources is not None:
            raise ValueError("Specify source or sources, not both.")
        sources = [source]
    if sources is not None:
        sources = list(dict.fromkeys(normalize_source(name) for name in sources))
    if page_types is not None and any(page_type not in PAGE_TYPES for page_type in page_types):
        raise ValueError("Unsupported page-type filter.")
    if max_distance is not None and max_distance < 0:
        raise ValueError("A raw distance cutoff cannot be negative.")
    try:
        target = _resolve_collection(collection)
        if target is None or target.count() == 0:
            return []
        return hybrid_search(target, query, encoder=encoder or _encoder, k=k, sources=sources,
            page_types=page_types, property_name=property_name, parent_id=document_id,
            policy=policy, max_distance=max_distance)
    except (ChromaError, OSError) as error:
        raise RetrievalError("Source retrieval failed; please retry after checking the database and local model.") from error


def get_all_records(*, collection=None, sources: list[str] | None = None, policy: SourcePolicy = DEFAULT_POLICY) -> list[dict]:
    """Read existing authorized records without implicit initialization or indexing."""
    target = _resolve_collection(collection)
    if target is None or target.count() == 0:
        return []
    return list(catalog(target, sources, policy))


def clear_collection() -> None:
    raise PermissionError("Collection clearing is disabled; existing RealtyAI records must be preserved.")


def init_from_processed_data() -> None:
    raise PermissionError("Implicit ingestion is disabled. Use the CSV review and explicitly approved indexing workflow.")
