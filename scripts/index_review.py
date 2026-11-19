#!/usr/bin/env python3
"""Review indexing by default. Execute only with explicit, collection-bound approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.document_preparation import prepare_documents
from backend.indexing import IngestionApproval
from backend.rag import _resolve_collection, index_records


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=Path("data/import_review/chunk_review.json"))
    parser.add_argument("--manifest", type=Path, default=Path("data/import_review/proposed_ingestion_manifest.json"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--collection-id")
    parser.add_argument("--approval-reference")
    parser.add_argument("--verified-legacy-provenance", type=Path)
    args = parser.parse_args(argv)
    if args.execute and (not args.collection_id or not args.approval_reference):
        parser.error("Execution requires the explicitly approved collection UUID and approval reference.")
    preview = json.loads(args.review.read_text(encoding="utf-8"))
    documents = preview["documents"]
    if args.execute:
        reviewed_ids = {chunk["id"] for chunk in preview["chunks"]}
        current_ids = {chunk.id for chunk in prepare_documents(documents)}
        if reviewed_ids != current_ids:
            raise ValueError("Preparation differs from the reviewed chunks; regenerate the review and obtain approval.")
    target = _resolve_collection() if args.execute else None
    if args.execute and target is None:
        raise ValueError("The existing target collection is unavailable; it will not be created or rebuilt.")
    legacy = json.loads(args.verified_legacy_provenance.read_text(encoding="utf-8")) if args.verified_legacy_provenance else None
    approval = IngestionApproval(args.collection_id, args.approval_reference, legacy) if args.execute else None
    result = index_records(documents, collection=target, dry_run=not args.execute,
        approval=approval, manifest_path=args.manifest)
    print({key: result[key] for key in ("state", "document_count", "proposed_chunk_count", "added_count")})
    return result


if __name__ == "__main__":
    main()
