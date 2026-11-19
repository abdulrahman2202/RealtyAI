"""Inspect actual prepared chunks using an isolated collection; never open production Chroma."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb

from backend.context import build_context
from backend.document_preparation import PreparedChunk
from backend.embedding import cached_encoder, cached_profile
from backend.indexing import IngestionApproval, index_chunks
from backend.rag import search

QUESTIONS = [
    "What information is available about THE ALBERT HALL MANSION?",
    "Where is Albert Hall Mansions located?",
    "Tell me about The Astera project.",
    "What bedroom configurations are available at The Astera?",
    "What is the scheduled handover date for The Astera?",
    "What services does Wasalt provide?",
    "What types of properties can users find on Wasalt?",
    "Does Wasalt provide property auction services?",
    "What information is available about properties for sale and rent in Saudi Arabia?",
    "Compare the real estate services described by DarGlobal and Wasalt.",
]


def isolated_collection():
    preview = json.loads(Path("data/import_review/chunk_review.json").read_text(encoding="utf-8"))
    profile = cached_profile()
    encoder = cached_encoder()
    client = chromadb.EphemeralClient(settings=chromadb.Settings(anonymized_telemetry=False))
    collection = client.create_collection("diagnostic_" + uuid4().hex, embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}})
    chunks = [PreparedChunk(**item) for item in preview["chunks"]]
    index_chunks(chunks, collection=collection, profile=profile, encoder=encoder, dry_run=False,
        approval=IngestionApproval(str(collection.id), "User-requested isolated actual-document verification"),
        lock_directory=Path(".tmp/phase6112/locks"))
    return collection, profile, encoder


def main():
    collection, profile, encoder = isolated_collection()
    output = []
    for question in QUESTIONS:
        records = search(question, k=8, collection=collection, encoder=encoder)
        bundle = build_context(records, query=question, profile=profile)
        result = {"question": question, "retrieved_count": len(records), "context_count": len(bundle.records),
            "context_tokens": bundle.token_count, "context_bytes": bundle.byte_count, "context": bundle.text,
            "records": records, "sources": bundle.sources}
        output.append(result)
        print(json.dumps({"question": question, "retrieved": len(records), "context": len(bundle.records),
            "chunks": [{"title": record["metadata"]["title"], "section": record["metadata"]["section"],
                "distance": record["distance"], "body_preview": record["body"][:150]} for record in bundle.records]}), flush=True)
    Path(".tmp/phase6112/retrieval_diagnosis.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
