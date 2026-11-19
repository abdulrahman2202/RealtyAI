from __future__ import annotations

import json
import os
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from typing import Any, Optional

from backend.models import DarGlobalProperty, WasaltProperty, ExtractedRecord


# ── Module-level singletons (created on first use) ──────────────

_chroma_client: Optional[chromadb.Client] = None
_collection: Optional[chromadb.Collection] = None
_encoder: Optional[SentenceTransformer] = None


def _get_client() -> chromadb.Client:
    """Lazy-initialise the ChromaDB client and collection."""
    global _chroma_client, _collection, _encoder

    if _chroma_client is not None:
        return _chroma_client

    # Allow overriding the vector DB directory via environment variable
    # (useful for test isolation without affecting the development database).
    env_db_dir = os.getenv("REALTYAI_VECTOR_DB_DIR")
    if env_db_dir:
        vector_db_dir = Path(env_db_dir)
    else:
        # Persist under the project data/vector_db directory
        vector_db_dir = Path(__file__).resolve().parent.parent / "data" / "vector_db"
    vector_db_dir.mkdir(parents=True, exist_ok=True)

    _chroma_client = chromadb.PersistentClient(
        path=str(vector_db_dir),
        settings=chromadb.Settings(anonymized_telemetry=False),
    )

    # Create (or reuse) the collection
    _collection = _chroma_client.get_or_create_collection(
        name="realtyai_properties",
        metadata={"hnw_distance_method": "cosine"},
    )

    _encoder = SentenceTransformer("all-MiniLM-L6-v2")

    return _chroma_client


def index_records(records: list[dict[Any, Any]]) -> None:
    """Index a list of property record dicts into ChromaDB.

    Each record should have at minimum ``title`` and ``description`` fields,
    plus a ``url`` for source tracking.

    Records with missing title or URL are skipped.
    """
    _ = _get_client()  # ensure initialised

    # Normalise and prepare texts for embedding
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for rec in records:
        # Skip records without a title or URL
        title = rec.get("title") or ""
        url = rec.get("url", "")
        if not title.strip() or not url.strip():
            continue

        # Generate a stable ID from the source URL
        rid = url.replace("https://", "").replace("http://", "").replace("/", "_")
        ids.append(rid)

        # Normalise title: strip trailing ", Residence X & Y" etc.
        norm_title = title
        if ", " in norm_title:
            potential_short = norm_title.rsplit(", ", 1)[0]
            if len(potential_short) < len(norm_title) - 3:
                norm_title = potential_short
        description = rec.get("description") or ""
        doc_text = f"{norm_title}. {description}".strip()
        if not doc_text:
            doc_text = title
        documents.append(doc_text)

        # Store metadata including source, url, title, and description.
        # ChromaDB 1.5.9 with embeddings supplied accepts str metadata values.
        metadata: dict[str, Any] = {
            "source": rec.get("source", ""),
            "url": url,
            "title": norm_title,  # normalised title
            "description": description,
        }
        metadatas.append(metadata)

    if not ids:
        # Nothing to index
        return

    # Compute embeddings for all documents (required for metadata to be
    # accepted by ChromaDB's Rust bindings in this version)
    embeddings = _encoder.encode(documents, convert_to_numpy=True)

    # Add to ChromaDB collection
    _collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def search(query: str, k: int = 4) -> list[dict[str, Any]]:
    """Search the vector store for the top-k most similar property records.

    Args:
        query: The user's natural language question or search term.
        k: Number of results to return (default 4).

    Returns:
        A list of dicts, each containing:
            - ``id``: the ChromaDB internal ID (derived from URL)
            - ``document``: the combined title+description text
            - ``metadata``: all stored metadata fields including ``source``, ``url``, and ``title``
            - ``distance``: cosine distance from the query embedding (range [0,2],
              normalised to [0,1] for consistency)
    """
    _ = _get_client()  # ensure initialised

    if not query or not query.strip():
        return []

    # Embed the query
    query_embedding = _encoder.encode(query.strip(), convert_to_numpy=True)

    # Retrieve top-k results
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
    )

    # Format results
    formatted: list[dict[str, Any]] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i in range(len(ids)):
        meta = metadatas[i] if i < len(metadatas) else {}
        dist = distances[i] if i < len(distances) else 1.0
        # ChromaDB cosine distance ranges [0, 2]; normalise to [0,1] for consistency
        norm_dist = float(dist) / 2.0 if float(dist) > 1.0 else float(dist)
        formatted.append(
            {
                "id": ids[i] if i < len(ids) else None,
                "document": documents[i] if i < len(documents) else "",
                "metadata": meta,
                "distance": norm_dist,
            }
        )

    return formatted


def clear_collection() -> None:
    """Reset the ChromaDB collection, removing all indexed records.

    Useful for test isolation or starting fresh.
    """
    global _collection, _chroma_client, _encoder
    # Ensure a client exists so we can delete the collection even in a fresh
    # process where the module-level singletons are still None.
    _ = _get_client()
    if _collection is not None:
        try:
            _chroma_client.delete_collection(name=_collection.name)
        except (chromadb.errors.NotFoundError, chromadb.errors.ChromaError):
            pass
    _collection = None
    _chroma_client = None
    _encoder = None

    # Re-initialise an empty collection
    _get_client()


def get_all_records() -> list[dict[str, Any]]:
    """Retrieve all indexed property records from the vector store."""
    _ = _get_client()  # ensure initialised

    results = _collection.get()
    records: list[dict[str, Any]] = []

    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    documents = results.get("documents", [])

    for i in range(len(ids)):
        records.append(
            {
                "id": ids[i] if i < len(ids) else None,
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
            }
        )

    return records


def init_from_processed_data() -> None:
    """Load the two DarGlobal processed JSON records and index them.

    This is the convenience entry-point used by the test suite and
    any initialization script.
    """
    processed_dir = (
        Path(__file__).resolve().parent.parent / "data" / "processed" / "darglobal"
    )

    records: list[dict[str, Any]] = []

    if processed_dir.is_dir():
        for json_file in sorted(processed_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                records.append(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Skip malformed JSON; do not block initialization
                continue

    if records:
        index_records(records)
