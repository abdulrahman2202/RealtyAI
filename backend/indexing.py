"""Explicit, append-only Chroma indexing with preflight manifests and safe retries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from chromadb.errors import ChromaError
from filelock import FileLock

from backend.data_access import (
    DEFAULT_POLICY,
    PROJECT_ROOT,
    SourcePolicy,
    document_id,
    normalize_source,
)
from backend.document_preparation import PreparedChunk
from backend.embedding import EmbeddingProfile, cached_encoder, cached_profile


@dataclass(frozen=True)
class IngestionApproval:
    """Explicit approval bound to the actual target collection UUID, separate from data-use permission."""

    collection_id: str
    reference: str
    verified_legacy_provenance: dict | None = None

    def require_target(self, collection) -> None:
        if not self.reference.strip() or str(collection.id) != self.collection_id:
            raise PermissionError("Ingestion approval must identify this collection and its approval reference.")


class IndexingConflict(ValueError):
    def __init__(self, manifest: dict):
        self.manifest = manifest
        super().__init__("Indexing conflicts require review; no conflicting records were written.")


def _write_manifest(path: Path | None, manifest: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _same_chunk(chunk: PreparedChunk, text: str, metadata: dict) -> bool:
    keys = (
        "source", "title", "page_type", "document_id", "content_fingerprint", "chunk_fingerprint",
        "preparation_version", "embedding_model", "embedding_revision", "embedding_dimension", "section", "chunk_index",
    )
    return text == chunk.text and all(metadata.get(key) == chunk.metadata.get(key) for key in keys)


def _all_metadata(collection) -> list[dict]:
    rows = []
    offset = 0
    while True:
        batch = collection.get(limit=500, offset=offset, include=["metadatas"])
        ids = batch.get("ids", [])
        rows.extend({"id": identity, "metadata": metadata or {}} for identity, metadata in zip(ids, batch.get("metadatas", []), strict=True))
        if len(ids) < 500:
            break
        offset += len(ids)
    return rows


def preflight_chunks(
    chunks: list[PreparedChunk], *, collection=None, profile: EmbeddingProfile | None = None,
    policy: SourcePolicy = DEFAULT_POLICY, verified_legacy_provenance: dict | None = None,
) -> dict:
    """Without an injected collection this is a pure, explicitly unverified review plan."""
    unique = {}
    conflicts = []
    for chunk in chunks:
        policy.require_url(chunk.metadata["source"], chunk.metadata["url"], chunk.metadata.get("data_origin", "raw"))
        if chunk.metadata["document_id"] != document_id(chunk.metadata["source"], chunk.metadata["url"]):
            conflicts.append({"id": chunk.id, "reason": "Document identity does not match the source URL"})
        if sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.metadata["chunk_fingerprint"]:
            conflicts.append({"id": chunk.id, "reason": "Prepared chunk fingerprint does not match its text"})
        if chunk.id in unique and not _same_chunk(chunk, unique[chunk.id].text, unique[chunk.id].metadata):
            conflicts.append({"id": chunk.id, "reason": "Conflicting duplicate IDs in the proposed batch"})
        unique.setdefault(chunk.id, chunk)
    entries = [{
        "id": chunk.id, "metadata": dict(chunk.metadata), "token_count": chunk.token_count,
        "status": "unverified" if collection is None else "pending",
    } for chunk in unique.values()]
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "state": "review_only" if collection is None else "preflight",
        "collection_id": str(collection.id) if collection is not None else None,
        "collection_name": collection.name if collection is not None else "realtyai_properties",
        "persistent_collection_accessed": False if collection is None else None,
        "requires_ingestion_approval": True,
        "data_use_authorization_reference": policy.authorization_reference,
        "document_count": len({chunk.metadata["document_id"] for chunk in unique.values()}),
        "proposed_chunk_count": len(entries), "duplicate_input_chunks": len(chunks) - len(unique),
        "pending_count": None if collection is None else len(entries), "identical_count": 0,
        "added_count": 0, "conflicts": conflicts, "chunks": entries,
        "source_counts": {source: sum(chunk.metadata["source"] == source for chunk in unique.values()) for source in ("darglobal", "wasalt")},
    }
    if collection is None or not entries:
        if conflicts:
            manifest["state"] = "conflict"
        return manifest
    profile = profile or cached_profile()
    expected = profile.provenance()
    for chunk in unique.values():
        if any(chunk.metadata.get(key) != value for key, value in expected.items()) or chunk.token_count != profile.count(chunk.text) or chunk.token_count > profile.max_sequence_length:
            conflicts.append({"id": chunk.id, "reason": "Incompatible embedding provenance or token limit"})
    existing = _all_metadata(collection)
    incoming_documents = {chunk.metadata["document_id"]: chunk.metadata for chunk in unique.values()}
    legacy_verified = bool(verified_legacy_provenance and verified_legacy_provenance.get("evidence")) and all(
        verified_legacy_provenance.get(key) == value for key, value in expected.items()
    )
    for row in existing:
        metadata = row["metadata"]
        if metadata.get("embedding_model"):
            if any(metadata.get(key) != value for key, value in expected.items()):
                conflicts.append({"id": row["id"], "reason": "Existing collection contains incompatible embedding provenance"})
        elif not legacy_verified:
            conflicts.append({"id": row["id"], "reason": "Legacy embedding provenance has not been verified; dimensions alone are insufficient"})
        identity = metadata.get("document_id")
        if not identity and metadata.get("url") and metadata.get("source"):
            try:
                identity = document_id(normalize_source(metadata["source"]), metadata["url"])
            except ValueError:
                identity = None
        incoming = incoming_documents.get(identity)
        if incoming and metadata.get("content_fingerprint") and (
            metadata["content_fingerprint"] != incoming["content_fingerprint"]
            or metadata.get("preparation_version") != incoming["preparation_version"]
        ):
            conflicts.append({"id": row["id"], "reason": "Existing document content/preparation version differs; automatic replacement is disabled"})
    ids = list(unique)
    for start in range(0, len(ids), 500):
        batch = collection.get(ids=ids[start:start + 500], include=["documents", "metadatas"])
        for identity, text, metadata in zip(batch["ids"], batch["documents"], batch["metadatas"], strict=True):
            if _same_chunk(unique[identity], text or "", metadata or {}):
                next(entry for entry in entries if entry["id"] == identity)["status"] = "identical"
            else:
                conflicts.append({"id": identity, "reason": "Existing chunk ID has conflicting content or metadata"})
    manifest["identical_count"] = sum(entry["status"] == "identical" for entry in entries)
    manifest["pending_count"] = sum(entry["status"] == "pending" for entry in entries)
    if conflicts:
        manifest["state"] = "conflict"
    return manifest


def index_chunks(
    chunks: list[PreparedChunk], *, collection=None, dry_run: bool = True,
    approval: IngestionApproval | None = None, profile: EmbeddingProfile | None = None,
    encoder=None, policy: SourcePolicy = DEFAULT_POLICY, manifest_path: Path | None = None,
    batch_size: int = 64, lock_directory: Path | None = None,
) -> dict:
    """Append absent chunks only. No collection creation, update, upsert, clearing, or deletion."""
    if not 1 <= batch_size <= 500:
        raise ValueError("Indexing batch size must be between 1 and 500.")
    if not dry_run:
        if collection is None or approval is None:
            raise PermissionError("Execution requires an injected collection and explicit ingestion approval.")
        approval.require_target(collection)
    if dry_run:
        manifest = preflight_chunks(chunks, collection=collection, profile=profile, policy=policy,
            verified_legacy_provenance=approval.verified_legacy_provenance if approval else None)
        _write_manifest(manifest_path, manifest)
        return manifest
    lock_root = lock_directory or PROJECT_ROOT / ".tmp" / "rag_index_locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_name = sha256(str(collection.id).encode("utf-8")).hexdigest() + ".lock"
    with FileLock(str(lock_root / lock_name), timeout=30):
        manifest = preflight_chunks(chunks, collection=collection, profile=profile, policy=policy,
            verified_legacy_provenance=approval.verified_legacy_provenance)
        _write_manifest(manifest_path, manifest)
        if manifest["conflicts"]:
            raise IndexingConflict(manifest)
        pending_ids = {entry["id"] for entry in manifest["chunks"] if entry["status"] == "pending"}
        pending = list({chunk.id: chunk for chunk in chunks if chunk.id in pending_ids}.values())
        profile = profile or cached_profile()
        encoder = encoder or (cached_encoder() if pending else None)
        try:
            for start in range(0, len(pending), batch_size):
                batch = pending[start:start + batch_size]
                vectors = encoder.encode([chunk.text for chunk in batch], convert_to_numpy=True, normalize_embeddings=True)
                if len(vectors) != len(batch) or any(len(vector) != profile.dimension for vector in vectors):
                    raise ValueError("Encoder output does not match the declared vector dimension.")
                collection.add(ids=[chunk.id for chunk in batch], documents=[chunk.text for chunk in batch],
                    metadatas=[chunk.metadata for chunk in batch], embeddings=vectors)
                verified = collection.get(ids=[chunk.id for chunk in batch], include=["documents", "metadatas"])
                stored = {identity: (text, metadata) for identity, text, metadata in zip(verified["ids"], verified["documents"], verified["metadatas"], strict=True)}
                if any(chunk.id not in stored or not _same_chunk(chunk, *stored[chunk.id]) for chunk in batch):
                    raise ValueError("The batch was not fully confirmed; retry through the manifest preflight.")
                for entry in manifest["chunks"]:
                    if entry["id"] in stored:
                        entry["status"] = "added"
                manifest["added_count"] += len(batch)
                _write_manifest(manifest_path, manifest)
        except (ChromaError, OSError, RuntimeError, ValueError):
            manifest["state"] = "interrupted"
            _write_manifest(manifest_path, manifest)
            raise
        manifest["state"] = "complete"
        manifest["pending_count"] = 0
        _write_manifest(manifest_path, manifest)
        return manifest
