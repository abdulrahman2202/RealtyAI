"""Review outputs for both actual CSV datasets; never open the persistent vector database."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from backend.csv_importer import ImportResult, import_directory
from backend.data_access import (
    DEFAULT_POLICY,
    SEARCHABLE_PAGE_TYPES,
    SourcePolicy,
    document_id,
    validate_record,
)
from backend.document_preparation import content_fingerprint, prepare_documents
from backend.embedding import EmbeddingProfile, cached_profile
from backend.indexing import preflight_chunks


def preserve_review_timestamps(result: ImportResult, approved_path: Path | None) -> None:
    if result.source != "darglobal" or approved_path is None or not approved_path.is_file():
        return
    archive = json.loads(approved_path.read_text(encoding="utf-8"))
    approved = {}
    for payload in archive["records"]:
        record = validate_record(payload)
        approved[document_id(record.source, record.url)] = record
    for index, record in enumerate(result.records):
        previous = approved.get(document_id(record.source, record.url))
        if previous and content_fingerprint(previous) == content_fingerprint(record):
            result.records[index] = record.model_copy(update={"extracted_at": previous.extracted_at,
                "data": {**record.data, "timestamp_origin": "preserved_approved_review"}})
            result.review_metadata[index]["timestamp_origin"] = "preserved_approved_review"


def _report(result: ImportResult, chunks: list, manifest: dict, authorization_reference: str) -> str:
    summary = result.summary()
    own_chunks = [chunk for chunk in chunks if chunk.metadata["source"] == result.source]
    lines = [f"# {result.source.title()} CSV Import Review — Phase 6.11", "",
        f"Data-use permission: {authorization_reference}", "",
        "Actual CSV files were read recursively in deterministic full-path order. This is review output; the persistent ChromaDB collection was not opened or changed.", "",
        "| Measure | Count |", "| --- | ---: |",
        *[f"| {key} | {summary[key]} |" for key in ("csv_files", "rows_read", "records_retained", "empty_skipped", "duplicates_skipped", "invalid_skipped")],
        f"| prepared_chunks | {len(own_chunks)} |", "", "## Classifications", "",
        *[f"- {kind}: {count}" for kind, count in sorted(summary["classification_counts"].items())],
        "", "## Retained records", "", "| Title | Page type | Original URL | Timestamp origin |", "| --- | --- | --- | --- |",
    ]
    for record, metadata in zip(result.records, result.review_metadata, strict=True):
        title = record.data["title"].replace("|", r"\|")
        lines.append(f"| {title} | {record.data['page_type']} | <{record.url}> | {metadata['timestamp_origin']} |")
        if metadata.get("original_csv_title"):
            lines.append(f"\nOriginal CSV title retained in review metadata: `{metadata['original_csv_title']}`.\n")
    lines.extend(["", "## Files processed", ""])
    for entry in result.files:
        lines.append(f"- {entry['file']}: {entry['rows_read']} rows; {entry['status']}")
    lines.extend(["", "## Validation and deduplication", ""])
    if result.issues:
        for issue in result.issues:
            lines.append(f"- {json.dumps(issue, ensure_ascii=False)}")
    else:
        lines.append("No malformed, duplicate, or empty rows were found.")
    lines.extend(["", "## Preparation and ingestion status", "",
        "Nested ExtractedRecord documents retain source, original URL, title, page type, full extracted text, and timestamp. Canonical URLs and CSV title provenance remain separate review metadata.", "",
        "Each useful section is prepared with the cached tokenizer, a 200-token body target and 32-token overlap. Complete embedding inputs, including prefixes and special tokens, are at most 256 tokens. Short sections remain whole. Known navigation/registration sections are omitted from prepared text while original normalized content remains available in chunk_review.json.", "",
        "CSV timestamps are preserved when supplied. Where the export has no extraction timestamp, the model's UTC import-time fallback is explicitly labeled. Unchanged DarGlobal records retain their approved Phase 6.10 extraction timestamps.", "",
        "Legal-reference and unknown records are normalized and reported, but excluded from searchable chunks. Auction catalogs retain the auction page type. Directories are not converted into individual properties.", "",
        f"Manifest state: {manifest['state']}. Existing collection IDs, embedding provenance, and conflicts are unverified until the approved ingestion preflight. No new records were added.", ""])
    return "\n".join(lines)


def generate_review(
    darglobal_root: Path, wasalt_root: Path, output_directory: Path, *,
    approved_darglobal_review: Path | None = None, profile: EmbeddingProfile | None = None,
    policy: SourcePolicy = DEFAULT_POLICY,
) -> dict:
    imported_at = datetime.now(UTC)
    results = [import_directory(root, source, imported_at=imported_at, policy=policy) for root, source in (
        (darglobal_root, "darglobal"), (wasalt_root, "wasalt"),
    )]
    preserve_review_timestamps(results[0], approved_darglobal_review)
    profile = profile or cached_profile()
    records = [record for result in results for record in result.records]
    chunks = prepare_documents(records, profile=profile, policy=policy)
    manifest = preflight_chunks(chunks, profile=profile, policy=policy)
    manifest["data_use_authorization"] = {"darglobal": True, "wasalt": True, "reference": policy.authorization_reference}
    manifest["excluded_documents"] = [
        {"source": record.source, "url": record.url, "title": record.data["title"], "page_type": record.data["page_type"]}
        for record in records if record.data["page_type"] not in SEARCHABLE_PAGE_TYPES
    ]
    preview = {
        "generated_at": imported_at.isoformat(), "state": "review_only", "production_ingestion_performed": False,
        "embedding_provenance": profile.provenance(), "max_chunk_tokens": max((chunk.token_count for chunk in chunks), default=0),
        "documents": [record.model_dump(mode="json") for record in records],
        "review_metadata": [metadata for result in results for metadata in result.review_metadata],
        "source_summaries": [result.summary() for result in results],
        "chunks": [chunk.to_dict() for chunk in chunks], "excluded_documents": manifest["excluded_documents"],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "chunk_review.json").write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_directory / "proposed_ingestion_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for result in results:
        (output_directory / f"{result.source}_import_report.md").write_text(_report(result, chunks, manifest, policy.authorization_reference), encoding="utf-8")
    totals = Counter(record.source for record in records)
    combined = ["# Combined DarGlobal + Wasalt Import Review — Phase 6.11", "",
        policy.authorization_reference, "",
        "Both actual datasets use the same normalization, preparation, indexing, retrieval, and citation architecture. No Wasalt quarantine remains. Production ingestion is pending explicit approval.", "",
        "| Source | CSV files | Rows read | Retained records | Searchable documents | Chunks |", "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        combined.append(f"| {result.source} | {len(result.files)} | {result.rows_read} | {totals[result.source]} | {sum(record.data['page_type'] in SEARCHABLE_PAGE_TYPES for record in result.records)} | {sum(chunk.metadata['source'] == result.source for chunk in chunks)} |")
    combined.extend(["", f"Maximum complete chunk length: {preview['max_chunk_tokens']} / {profile.max_sequence_length} tokens.", "",
        "All CSV files, including legal/reference files, were processed. Records unsuitable for property retrieval are listed in the manifest as exclusions. Empty and duplicate rows are documented in the source reports.", "",
        "The original seven-record DarGlobal extracted_records.json and import_report.md were not overwritten. New normalized records for both sources are included in chunk_review.json.documents.", "",
        "The proposed manifest contains deterministic document/chunk IDs, content fingerprints, preparation version, source lineage, and embedding provenance. Its IDs have not been checked against the existing database. Actual indexing requires target-bound IngestionApproval, verified legacy embedding provenance, and a successful conflict preflight; it only adds absent chunks.", "",
        "Semantic vector search is combined with lexical/entity matching and source/page-type scopes. Exact individual-property names narrow retrieval to their own source identity. Company pages, directories, and auction catalogs remain separate knowledge kinds. Context contains complete selected chunks within tokenizer and byte budgets, with property identities and original-source citations. Missing attribute information is reported as unavailable; attribute answers quote source evidence.", "",
        "Limitations: no individual-property Wasalt documents are fabricated from directories; coverage is limited to the actual provided CSV rows. The cached encoder is English-oriented, and Arabic semantic quality needs an authorized benchmark; Unicode lexical matching is supported. Persistent collection configuration and historical encoder provenance remain unverified because this phase did not open the database.", "",
        "Tests and Ruff results are recorded in docs/multi_source_rag.md after final verification.", ""])
    (output_directory / "combined_import_report.md").write_text("\n".join(combined), encoding="utf-8")
    return {"sources": preview["source_summaries"], "documents": len(records), "chunks": len(chunks), "max_chunk_tokens": preview["max_chunk_tokens"], "manifest_state": manifest["state"]}
