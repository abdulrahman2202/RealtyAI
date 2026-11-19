"""Review and explicitly approve a separate collection without touching legacy storage."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError
from filelock import FileLock

from backend.data_access import PROJECT_ROOT
from backend.document_preparation import PREPARATION_VERSION, prepare_documents
from backend.embedding import cached_profile
from backend.indexing import IngestionApproval, index_chunks

NEW_COLLECTION_NAME = "realtyai_multisource_v1"
NEW_DATABASE_DIR = PROJECT_ROOT / "data" / "vector_db_multisource"
REVIEW_PATH = PROJECT_ROOT / "data" / "import_review" / "chunk_review.json"
PLAN_PATH = PROJECT_ROOT / "data" / "import_review" / "phase6112_collection_plan.json"
RECEIPT_PATH = PROJECT_ROOT / "data" / "import_review" / "phase6112_ingestion_receipt.json"


def reviewed_chunks(review_path: Path = REVIEW_PATH):
    raw = review_path.read_bytes()
    preview = json.loads(raw)
    profile = cached_profile()
    if preview["embedding_provenance"] != profile.provenance():
        raise ValueError("The cached embedding profile differs from the reviewed profile.")
    chunks = prepare_documents(preview["documents"], profile=profile)
    actual = {chunk.id: chunk.to_dict() for chunk in chunks}
    reviewed = {chunk["id"]: chunk for chunk in preview["chunks"]}
    if len(reviewed) != len(preview["chunks"]) or actual != reviewed:
        raise ValueError("Prepared chunks differ from the reviewed text, IDs, or provenance.")
    return chunks, profile, sha256(raw).hexdigest()


def proposed_collection(*, review_path: Path = REVIEW_PATH, database_dir: Path = NEW_DATABASE_DIR,
    collection_name: str = NEW_COLLECTION_NAME) -> dict:
    directory = database_dir.resolve()
    if directory == (PROJECT_ROOT / "data" / "vector_db").resolve():
        raise PermissionError("The multisource workflow cannot open or modify legacy storage.")
    chunks, profile, review_hash = reviewed_chunks(review_path)
    return {
        "state": "awaiting_persistent_ingestion_approval",
        "database_dir": str(directory), "collection_name": collection_name,
        "distance_metric": "cosine", "embedding_provenance": profile.provenance(),
        "preparation_version": PREPARATION_VERSION,
        "review_path": str(review_path.resolve()), "review_sha256": review_hash,
        "chunk_ids": sorted(chunk.id for chunk in chunks), "chunk_count": len(chunks),
        "document_count": len({chunk.metadata["document_id"] for chunk in chunks}),
        "source_counts": dict(Counter(chunk.metadata["source"] for chunk in chunks)),
        "preserve_legacy_database": True,
    }


def execute_approved_plan(plan: dict, *, approval_reference: str, create_collection: bool = False,
    collection_id: str | None = None, client=None, encoder=None,
    receipt_path: Path = RECEIPT_PATH, lock_directory: Path | None = None) -> dict:
    """Creation is explicit; appends retain the original actual-UUID-bound safeguards."""
    if not approval_reference.strip():
        raise PermissionError("A user approval reference is required for persistent ingestion.")
    current = proposed_collection(review_path=Path(plan["review_path"]),
        database_dir=Path(plan["database_dir"]), collection_name=plan["collection_name"])
    if plan != current:
        raise ValueError("The collection plan has changed; obtain approval for the current plan.")
    chunks, profile, _ = reviewed_chunks(Path(plan["review_path"]))
    directory = Path(plan["database_dir"])
    if client is None and not create_collection and not (directory / "chroma.sqlite3").is_file():
        raise PermissionError("Collection creation requires the explicit create-collection option.")
    lock_root = lock_directory or PROJECT_ROOT / ".tmp" / "rag_index_locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    key = sha256((str(directory) + "\n" + plan["collection_name"]).encode()).hexdigest()
    with FileLock(str(lock_root / (key + ".creation.lock")), timeout=30):
        client = client or chromadb.PersistentClient(path=str(directory),
            settings=chromadb.Settings(anonymized_telemetry=False))
        created = False
        try:
            collection = client.get_collection(plan["collection_name"], embedding_function=None)
        except NotFoundError:
            if not create_collection:
                raise PermissionError("Collection creation was not explicitly approved.") from None
            collection = client.create_collection(plan["collection_name"], embedding_function=None,
                metadata={**profile.provenance(), "preparation_version": PREPARATION_VERSION,
                    "review_sha256": plan["review_sha256"]},
                configuration={"hnsw": {"space": "cosine"}})
            created = True
        if not created and str(collection.id) != collection_id:
            raise PermissionError("An existing collection retry requires its explicitly approved UUID.")
        if created and collection_id is not None and str(collection.id) != collection_id:
            raise PermissionError("The created collection UUID differs from the supplied target.")
        metadata = collection.metadata or {}
        expected_metadata = {**profile.provenance(), "preparation_version": PREPARATION_VERSION,
            "review_sha256": plan["review_sha256"]}
        if any(metadata.get(key) != value for key, value in expected_metadata.items()):
            raise ValueError("Existing collection metadata is incompatible with the approved plan.")
        if (collection.configuration.get("hnsw") or {}).get("space") != "cosine":
            raise ValueError("The target collection must use the approved cosine distance metric.")
        # Approved creation identifies name/path; the returned UUID binds every protected append.
        result = index_chunks(chunks, collection=collection, profile=profile, encoder=encoder,
            dry_run=False, approval=IngestionApproval(str(collection.id), approval_reference),
            manifest_path=receipt_path, lock_directory=lock_root)
        result.update({"database_dir": str(directory), "review_sha256": plan["review_sha256"],
            "distance_metric": "cosine", "approval_reference": approval_reference})
        receipt_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result
